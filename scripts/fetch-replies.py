#!/usr/bin/env python3
"""
fetch-replies.py — find new replies to <VENTURE> outbound, classify, label, queue.

Reads ~/.agent-os/outbox/sent-tracking.json to know which senders count as
"replies to our cold outreach." Searches the <YOUR_EMAIL> inbox for
unread messages from those senders in the last 30 days. Classifies each
via keyword heuristics, applies the appropriate Gmail label, and appends
to ~/.agent-os/inbox-queue.jsonl for the processor (Claude-in-session) to
pick up.

Spec: ~/.agent-os/agents/reply-handler.md

Auth: reuses ~/.agent-os/secrets/gmail-oauth-keys.json (Desktop OAuth
client) + ~/.agent-os/secrets/gmail-credentials.json (refresh token).

Run on demand:
  python3 ~/.agent-os/scripts/fetch-replies.py

Or via launchd: io.<NS>.reply-fetcher (every 30 min, 9 AM–6 PM weekdays).

Safety: read-only on messages (only adds labels, never deletes / sends /
replies). The processor (separate, invocation-driven) handles drafting.
"""

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

SECRETS_DIR = Path.home() / ".agent-os" / "secrets"
TRACKING_FILE = Path.home() / ".agent-os" / "outbox" / "sent-tracking.json"
QUEUE_FILE = Path.home() / ".agent-os" / "inbox-queue.jsonl"
SEEN_FILE = Path.home() / ".agent-os" / ".reply-fetcher-seen.json"
LOG_FILE = Path.home() / ".agent-os" / ".reply-fetcher.log"

# Label names → IDs (must match the labels created by the gmail-<NS> MCP)
LABELS = {
    "all":         "<NS>/reply",
    "bounce":      "<NS>/reply/bounce",
    "ooo":         "<NS>/reply/ooo",
    "unsubscribe": "<NS>/reply/unsubscribe",
    "interested":  "<NS>/reply/interested",
    "objection":   "<NS>/reply/objection",
    "polite-no":   "<NS>/reply/polite-no",
    "referral":    "<NS>/reply/referral",
    "needs-review":"<NS>/reply/needs-review",
}


def log(msg):
    ts = datetime.now().isoformat(timespec="seconds")
    line = f"[{ts}] {msg}\n"
    sys.stderr.write(line)
    try:
        LOG_FILE.open("a").write(line)
    except Exception:
        pass


def load_seen():
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text()))
        except Exception:
            return set()
    return set()


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(sorted(seen)))
    SEEN_FILE.chmod(0o600)


def load_tracking():
    if not TRACKING_FILE.exists():
        log(f"✗ tracking missing: {TRACKING_FILE}")
        return []
    data = json.loads(TRACKING_FILE.read_text())
    return data.get("recipients", [])


def load_gmail_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    keys = json.loads((SECRETS_DIR / "gmail-oauth-keys.json").read_text())
    creds_data = json.loads((SECRETS_DIR / "gmail-credentials.json").read_text())
    client = keys.get("installed") or keys.get("web") or keys
    scope = creds_data.get("scope", "")
    scopes = scope.split() if scope else ["https://www.googleapis.com/auth/gmail.modify"]
    creds = Credentials(
        token=creds_data.get("access_token"),
        refresh_token=creds_data["refresh_token"],
        token_uri=client["token_uri"],
        client_id=client["client_id"],
        client_secret=client["client_secret"],
        scopes=scopes,
    )
    if not creds.valid:
        creds.refresh(Request())
        creds_data["access_token"] = creds.token
        (SECRETS_DIR / "gmail-credentials.json").write_text(json.dumps(creds_data, indent=2))
    return build("gmail", "v1", credentials=creds)


def classify(subject: str, body: str, sender: str) -> str:
    """Lightweight keyword classification. Returns the label key."""
    s = (subject or "").lower()
    b = (body or "").lower()
    snd = (sender or "").lower()

    # 1. Bounce (highest signal)
    if "mailer-daemon" in snd or "postmaster" in snd or "mail-daemon" in snd:
        return "bounce"
    if "delivery status notification" in s or "undeliverable" in s or "mail delivery failed" in s:
        return "bounce"
    if "address not found" in b or "no such user" in b or "550" in s:
        return "bounce"

    # 2. Out of office
    ooo_patterns = [
        r"\bout of (the )?office\b", r"\bautomatic reply\b", r"\bauto[\s-]?reply\b",
        r"\bcurrently (away|out)\b", r"\bon (vacation|holiday|leave|pto)\b",
        r"\bwill return\b", r"\blimited (access to email|email access)\b",
    ]
    if any(re.search(p, s) for p in ooo_patterns) or any(re.search(p, b) for p in ooo_patterns):
        return "ooo"

    # 3. Unsubscribe / hard no
    unsub_patterns = [
        r"\bunsubscribe\b", r"\bremove me\b", r"\bdo not contact\b",
        r"\bopt[\s-]?out\b", r"\bstop emailing\b", r"\btake me off\b",
    ]
    if any(re.search(p, b) for p in unsub_patterns):
        return "unsubscribe"

    # 4. Referral (must be substantive)
    referral_patterns = [
        r"\bintroduc(e|ing)\s+you\b", r"\blet me connect you\b",
        r"\byou should (talk|speak|reach out) to\b",
        r"\bcc[':]?ing\b", r"\bloop(ing)? in\b",
    ]
    if any(re.search(p, b) for p in referral_patterns):
        return "referral"

    # 5. Interested (positive engagement)
    interested_patterns = [
        r"\b(yes|sure|absolutely|definitely)\b.*\b(call|meeting|chat|talk|book|interested|learn more|tell me more)\b",
        r"\bsend (me|over) (the|a)\b", r"\bschedul(e|ing) (a|the) call\b",
        r"\b(i'?d like|i'?d love) to (chat|talk|learn|meet|discuss)\b",
        r"\bbook(ed)? (a|the|some) time\b", r"\bgrab 15\b", r"\b15 ?(min|minutes)\b.*\b(works|sounds good|good for me)\b",
    ]
    if any(re.search(p, b) for p in interested_patterns):
        return "interested"

    # 6. Polite no (short, declining)
    if len(b.strip()) < 400:  # short messages
        polite_no_patterns = [
            r"\bnot (interested|for me|a fit|right now|the right time)\b",
            r"\bwe'?re (good|all set|set|fine)\b",
            r"\bno thanks\b", r"\bpass\b", r"\balready (have|using|on)\b",
            r"\bnot at this time\b", r"\bthanks (but|however)\b",
        ]
        if any(re.search(p, b) for p in polite_no_patterns):
            return "polite-no"

    # 7. Objection (engagement with pushback) — longer responses with skeptical language
    objection_patterns = [
        r"\bhow (does|is) (this|that|<NS>) different\b", r"\bwhy not (use|try)\b",
        r"\bwe (already|currently) (use|have)\b.*\b(apollo|outreach|salesloft|gong|chatgpt)\b",
        r"\bsounds (interesting|expensive|risky|too good)\b",
        r"\bquestion(s)?\b.*\?", r"\bhow much\b", r"\bwhat'?s the (catch|cost|price)\b",
    ]
    if any(re.search(p, b) for p in objection_patterns):
        return "objection"

    # 8. Default — needs human review
    return "needs-review"


def get_label_ids(service):
    """Resolve label names → Gmail label IDs."""
    res = service.users().labels().list(userId="me").execute()
    name_to_id = {l["name"]: l["id"] for l in res.get("labels", [])}
    return {key: name_to_id.get(name) for key, name in LABELS.items()}


def extract_body(payload):
    """Walk Gmail message payload tree to extract plain-text body."""
    import base64

    def _walk(p):
        if p.get("mimeType") == "text/plain" and p.get("body", {}).get("data"):
            try:
                return base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", errors="ignore")
            except Exception:
                return ""
        for sub in p.get("parts", []) or []:
            t = _walk(sub)
            if t:
                return t
        # Fallback: text/html stripped
        if p.get("mimeType") == "text/html" and p.get("body", {}).get("data"):
            try:
                html = base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", errors="ignore")
                return re.sub(r"<[^>]+>", " ", html)
            except Exception:
                return ""
        return ""

    return _walk(payload).strip()


def header_value(headers, name):
    for h in headers or []:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def main():
    log("=== fetch-replies.py started ===")

    recipients = load_tracking()
    if not recipients:
        log("no recipients tracked — nothing to watch")
        return 0
    log(f"watching {len(recipients)} tracked recipients")

    tracked_emails = set()
    email_to_recipient = {}
    for r in recipients:
        for em in (r.get("candidate_emails") or []) + [r.get("recipient_email", "")]:
            em = em.lower().strip()
            if em:
                tracked_emails.add(em)
                email_to_recipient[em] = r
    log(f"resolved {len(tracked_emails)} unique watch-addresses")

    # Also watch the DOMAINS — if a colleague at the same domain replies on
    # behalf of the prospect, we want to catch it.
    tracked_domains = set()
    for em in tracked_emails:
        if "@" in em:
            tracked_domains.add(em.split("@", 1)[1])

    try:
        service = load_gmail_service()
    except Exception as e:
        log(f"✗ gmail auth failed: {e}")
        return 2

    seen = load_seen()

    # Search: inbox, unread, last 30 days, from any tracked domain
    # Gmail query syntax: from:(a OR b OR c) newer_than:30d in:inbox
    if not tracked_domains:
        log("no tracked domains — nothing to query")
        return 0
    domain_query = " OR ".join(f"from:{d}" for d in sorted(tracked_domains))
    # Bonus: also catch mailer-daemon bounces of mail TO our tracked recipients
    bounce_query = f"from:mailer-daemon@googlemail.com OR from:postmaster"
    query = f"({domain_query} OR {bounce_query}) newer_than:30d in:inbox"
    log(f"Gmail query: {query[:140]}{'…' if len(query) > 140 else ''}")

    try:
        results = service.users().messages().list(userId="me", q=query, maxResults=100).execute()
    except Exception as e:
        log(f"✗ Gmail search failed: {e}")
        return 2

    messages = results.get("messages") or []
    log(f"Gmail returned {len(messages)} candidate message(s)")

    label_ids = get_label_ids(service)
    new_queued = 0

    for m in messages:
        mid = m["id"]
        if mid in seen:
            continue

        try:
            msg = service.users().messages().get(userId="me", id=mid, format="full").execute()
        except Exception as e:
            log(f"  · {mid}: fetch failed: {e}")
            continue

        headers = msg.get("payload", {}).get("headers", [])
        from_addr = header_value(headers, "From")
        to_addr   = header_value(headers, "To")
        subject   = header_value(headers, "Subject")
        date_hdr  = header_value(headers, "Date")
        sender_email_match = re.search(r"<([^>]+)>", from_addr) or re.search(r"([\w._%+-]+@[\w.-]+)", from_addr)
        sender_email = (sender_email_match.group(1) if sender_email_match else from_addr).lower().strip()

        # Match to a tracked recipient (best effort)
        rec = email_to_recipient.get(sender_email)
        if not rec:
            # Try domain-only match
            dom = sender_email.split("@", 1)[1] if "@" in sender_email else ""
            for em, r in email_to_recipient.items():
                if em.split("@", 1)[1] == dom:
                    rec = r
                    break

        body = extract_body(msg.get("payload", {}))
        category = classify(subject, body, sender_email)

        # Apply labels: parent + category
        try:
            label_to_add = [label_ids["all"], label_ids[category]]
            label_to_add = [l for l in label_to_add if l]
            if label_to_add:
                service.users().messages().modify(
                    userId="me", id=mid, body={"addLabelIds": label_to_add}
                ).execute()
        except Exception as e:
            log(f"  · {mid}: label failed: {e}")

        # Queue it
        entry = {
            "message_id": mid,
            "thread_id": msg.get("threadId"),
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "from": from_addr,
            "sender_email": sender_email,
            "subject": subject,
            "date": date_hdr,
            "category": category,
            "body_preview": body[:600],
            "matched_recipient": rec,
        }
        with QUEUE_FILE.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        seen.add(mid)
        new_queued += 1
        log(f"  ✓ queued {mid} · {category:14s} · {sender_email}")

    save_seen(seen)
    log(f"=== done · {new_queued} new reply/replies queued ===")
    return 0 if new_queued >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
