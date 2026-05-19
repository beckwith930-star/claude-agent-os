#!/usr/bin/env python3
"""
fetch-bookings.py — detect new Google Calendar bookings via Gmail.

When a prospect books a 15-min call via
https://calendar.app.google/mLTnDpPGmp9e4sou5, Google sends a calendar-
invite email to <YOUR_EMAIL>. This script polls Gmail for those
invites, extracts the prospect + meeting details, cross-references against
~/.agent-os/outbox/sent-tracking.json (so we know if this booking closes
a cold-outreach loop), and queues each to ~/.agent-os/bookings-queue.jsonl
for the processor (agents/calendar-booking.md) to pick up.

Spec: ~/.agent-os/agents/calendar-booking.md

Auth: reuses ~/.agent-os/secrets/gmail-{oauth-keys,credentials}.json.

Run on demand:
  python3 ~/.agent-os/scripts/fetch-bookings.py

Or via launchd: io.<NS>.booking-fetcher (every 15 min — bookings
are time-sensitive, prep should fire as soon as a booking lands).

Safety: read-only on messages (only adds Gmail labels, never deletes
or sends). The processor handles prep-doc generation + confirmation
drafting on-demand.
"""

import base64
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SECRETS_DIR = Path.home() / ".agent-os" / "secrets"
TRACKING_FILE = Path.home() / ".agent-os" / "outbox" / "sent-tracking.json"
QUEUE_FILE = Path.home() / ".agent-os" / "bookings-queue.jsonl"
SEEN_FILE = Path.home() / ".agent-os" / ".booking-fetcher-seen.json"
LOG_FILE = Path.home() / ".agent-os" / ".booking-fetcher.log"

LABELS = {
    "all":       "<NS>/booking",
    "new":       "<NS>/booking/new",
    "cancelled": "<NS>/booking/cancelled",
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
        return {"recipients": []}
    return json.loads(TRACKING_FILE.read_text())


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


def header_value(headers, name):
    for h in headers or []:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def extract_body(payload):
    """Walk Gmail message payload for plain text + .ics calendar attachments."""
    text_body = ""
    ics_body = ""

    def _walk(p):
        nonlocal text_body, ics_body
        mt = p.get("mimeType", "")
        if mt == "text/plain" and p.get("body", {}).get("data"):
            try:
                text_body += base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", errors="ignore") + "\n"
            except Exception:
                pass
        if mt in ("text/calendar", "application/ics") and p.get("body", {}).get("data"):
            try:
                ics_body += base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", errors="ignore") + "\n"
            except Exception:
                pass
        for sub in p.get("parts", []) or []:
            _walk(sub)

    _walk(payload)
    return text_body.strip(), ics_body.strip()


def parse_ics(ics_text):
    """Lightweight .ics parser — extracts what we need from the calendar event."""
    if not ics_text:
        return {}
    fields = {}
    # Multi-line ics fields can have continuation lines starting with whitespace
    lines = []
    for raw_line in ics_text.splitlines():
        if raw_line.startswith((" ", "\t")) and lines:
            lines[-1] += raw_line.lstrip()
        else:
            lines.append(raw_line)

    for line in lines:
        if line.startswith("SUMMARY:"):
            fields["summary"] = line[len("SUMMARY:"):].strip()
        elif line.startswith("DTSTART"):
            # DTSTART;TZID=America/Los_Angeles:20260520T100000 or DTSTART:20260520T170000Z
            m = re.search(r"DTSTART(?:;[^:]+)?:(.+)", line)
            if m:
                fields["dtstart"] = m.group(1).strip()
        elif line.startswith("DTEND"):
            m = re.search(r"DTEND(?:;[^:]+)?:(.+)", line)
            if m:
                fields["dtend"] = m.group(1).strip()
        elif line.startswith("ORGANIZER"):
            m = re.search(r"mailto:([^>\s;]+)", line, re.IGNORECASE)
            if m:
                fields["organizer_email"] = m.group(1)
        elif line.startswith("ATTENDEE"):
            m_email = re.search(r"mailto:([^>\s;]+)", line, re.IGNORECASE)
            m_cn = re.search(r"CN=([^;:]+)", line)
            attendee = {}
            if m_email:
                attendee["email"] = m_email.group(1)
            if m_cn:
                attendee["name"] = m_cn.group(1).strip()
            fields.setdefault("attendees", []).append(attendee)
        elif line.startswith("DESCRIPTION:"):
            fields["description"] = line[len("DESCRIPTION:"):].strip()
        elif line.startswith("LOCATION:"):
            fields["location"] = line[len("LOCATION:"):].strip()
        elif line.startswith("STATUS:"):
            fields["status"] = line[len("STATUS:"):].strip()
    return fields


def parse_body_fallback(text):
    """If .ics parsing fails, regex the email body for booking details."""
    fields = {}
    # Look for "When: Tue, May 20, 2026 10:00 AM PST"
    m = re.search(r"When:\s*(.+?)(?:\r?\n|$)", text)
    if m:
        fields["when_text"] = m.group(1).strip()
    # Look for "Guest:" / "Attendees:" / "With:"
    m = re.search(r"(?:Guests?|Attendees?|With):\s*(.+?)(?:\r?\n|$)", text)
    if m:
        fields["attendees_text"] = m.group(1).strip()
    # Email addresses in body
    emails = re.findall(r"[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    fields["emails_in_body"] = list(dict.fromkeys(emails))  # dedupe preserving order
    return fields


def is_venture_booking(subject, ics_fields, body_text):
    """Heuristic: is this a NEW booking for the operator's <VENTURE> calendar link?"""
    subj = (subject or "").lower()
    summary = (ics_fields.get("summary") or "").lower()
    body = (body_text or "").lower()
    # Match any of these signals
    signals = [
        "new appointment" in subj or "new event" in subj,
        "invitation:" in subj,
        "@google.com" in body and "calendar.app.google" in body,
        "<NS>" in summary,
        ics_fields.get("organizer_email", "").lower() == "<YOUR_EMAIL>",
        "15 min" in summary or "15-min" in summary,
    ]
    return any(signals)


def is_cancellation(subject, ics_fields):
    subj = (subject or "").lower()
    return (
        "cancel" in subj
        or "declined" in subj
        or (ics_fields.get("status") or "").upper() == "CANCELLED"
    )


def find_matched_recipient(prospect_email, tracking):
    """Cross-reference prospect_email against sent-tracking.json to detect cold-outreach loop closure."""
    if not prospect_email:
        return None
    pe = prospect_email.lower().strip()
    for r in tracking.get("recipients", []):
        candidates = (r.get("candidate_emails") or []) + [r.get("recipient_email", "")]
        if pe in [c.lower().strip() for c in candidates if c]:
            return r
    # Domain-level match
    if "@" in pe:
        dom = pe.split("@", 1)[1]
        for r in tracking.get("recipients", []):
            for c in (r.get("candidate_emails") or []) + [r.get("recipient_email", "")]:
                if c and "@" in c and c.split("@", 1)[1].lower() == dom:
                    return r
    return None


def get_label_ids(service):
    res = service.users().labels().list(userId="me").execute()
    name_to_id = {l["name"]: l["id"] for l in res.get("labels", [])}
    return {key: name_to_id.get(name) for key, name in LABELS.items()}


def main():
    log("=== fetch-bookings.py started ===")
    tracking = load_tracking()

    try:
        service = load_gmail_service()
    except Exception as e:
        log(f"✗ gmail auth failed: {e}")
        return 2

    seen = load_seen()

    # Search: Gmail messages from calendar-notification@google.com OR with calendar invite content
    # newer than 30 days
    query = (
        "(from:calendar-notification@google.com OR from:notifications-noreply@google.com OR "
        "has:attachment filename:ics) "
        "newer_than:30d in:inbox"
    )
    log(f"Gmail query: {query}")

    try:
        results = service.users().messages().list(userId="me", q=query, maxResults=50).execute()
    except Exception as e:
        log(f"✗ Gmail search failed: {e}")
        return 2

    messages = results.get("messages") or []
    log(f"Gmail returned {len(messages)} candidate message(s)")

    label_ids = get_label_ids(service)
    new_queued = 0
    skipped = 0

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
        subject = header_value(headers, "Subject")
        from_addr = header_value(headers, "From")
        date_hdr = header_value(headers, "Date")

        text_body, ics_text = extract_body(msg.get("payload", {}))
        ics_fields = parse_ics(ics_text)
        body_fields = parse_body_fallback(text_body)

        if not is_venture_booking(subject, ics_fields, text_body):
            log(f"  · {mid}: looks like calendar mail but not a <VENTURE> booking — skipping")
            seen.add(mid)
            skipped += 1
            continue

        # Identify the prospect (the attendee that ISN'T <YOUR_EMAIL>)
        prospect_email = None
        prospect_name = None
        for att in ics_fields.get("attendees", []):
            email = (att.get("email") or "").lower()
            if email and "<YOUR_EMAIL>" not in email and "<YOUR_DOMAIN>" not in email:
                prospect_email = email
                prospect_name = att.get("name") or ""
                break
        if not prospect_email:
            # Fallback to body emails
            for em in body_fields.get("emails_in_body", []):
                if "<YOUR_EMAIL>" not in em.lower() and "@google.com" not in em.lower():
                    prospect_email = em.lower()
                    break

        category = "cancelled" if is_cancellation(subject, ics_fields) else "new"

        matched_recipient = find_matched_recipient(prospect_email, tracking)

        # Apply labels
        try:
            add = [label_ids["all"], label_ids[category]]
            add = [l for l in add if l]
            if add:
                service.users().messages().modify(
                    userId="me", id=mid, body={"addLabelIds": add}
                ).execute()
        except Exception as e:
            log(f"  · {mid}: label failed: {e}")

        entry = {
            "message_id": mid,
            "thread_id": msg.get("threadId"),
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "category": category,
            "subject": subject,
            "from": from_addr,
            "date": date_hdr,
            "prospect_email": prospect_email,
            "prospect_name": prospect_name,
            "meeting_summary": ics_fields.get("summary"),
            "meeting_dtstart": ics_fields.get("dtstart"),
            "meeting_dtend": ics_fields.get("dtend"),
            "meeting_location": ics_fields.get("location"),
            "meeting_description": (ics_fields.get("description") or "")[:1000],
            "when_text_fallback": body_fields.get("when_text"),
            "matched_recipient": matched_recipient,  # null if NEW prospect, populated if cold-outreach loop closure
        }
        with QUEUE_FILE.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        seen.add(mid)
        new_queued += 1

        match_tag = f" → matches batch {matched_recipient['batch']} draft {matched_recipient['draft_id']}" if matched_recipient else " → NEW prospect"
        log(f"  ✓ queued {mid} · {category:9s} · {prospect_email}{match_tag}")

    save_seen(seen)
    log(f"=== done · {new_queued} new booking(s) queued · {skipped} skipped ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
