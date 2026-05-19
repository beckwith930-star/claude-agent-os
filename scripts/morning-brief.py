#!/usr/bin/env python3
"""
morning-brief.py — daily aggregator that drops a tight brief in the operator's
Gmail every weekday at 7 AM (via launchd) or on demand.

Reads state from across the Agent OS:
  • ~/.agent-os/inbox-queue.jsonl                — unprocessed replies
  • ~/.agent-os/inbox-queue-processed.jsonl      — handled replies (last 24 hr)
  • ~/.agent-os/bookings-queue.jsonl             — pending bookings
  • ~/.agent-os/outbox/sent-tracking.json        — pipeline + bounce status
  • ~/.agent-os/MEMORY.md                        — yesterday's wins (tail)
  • scripts/audit-brand.py                       — brand-doc health
  • scripts/os-health.py                         — full OS health
  • gh CLI                                       — GitHub plugin activity

Synthesizes:
  1. TOP 3 PRIORITY ACTIONS (heuristic-derived from pending state)
  2. Inbox state (reply queue, booking queue, bounce status)
  3. Pipeline (drafts sent, retry-available, dead, conversion rates)
  4. Plugin activity (GitHub stars/forks/clones/issues this week)
  5. Brand-doc health (audit pass/fail)
  6. OS health (checks green vs failing)
  7. Yesterday's activity (MEMORY.md tail digest)

Output: a Gmail draft TO <YOUR_EMAIL> (memo to self). Label:
  <NS>/morning-brief

Spec: ~/.agent-os/agents/morning-brief.md

Auth: reuses ~/.agent-os/secrets/gmail-{oauth-keys,credentials}.json.

Run on demand:
  python3 ~/.agent-os/scripts/morning-brief.py

Or via launchd: io.<NS>.morning-brief (Mon-Fri @ 07:00 local).
"""

import base64
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path

HOME = Path.home()
AGENT_OS = HOME / ".agent-os"
SECRETS_DIR = AGENT_OS / "secrets"

# State sources
INBOX_QUEUE          = AGENT_OS / "inbox-queue.jsonl"
INBOX_PROCESSED      = AGENT_OS / "inbox-queue-processed.jsonl"
BOOKINGS_QUEUE       = AGENT_OS / "bookings-queue.jsonl"
BOOKINGS_PROCESSED   = AGENT_OS / "bookings-queue-processed.jsonl"
TRACKING_FILE        = AGENT_OS / "outbox" / "sent-tracking.json"
MEMORY               = AGENT_OS / "MEMORY.md"
AUDIT_SCRIPT         = AGENT_OS / "scripts" / "audit-brand.py"
HEALTH_SCRIPT        = AGENT_OS / "scripts" / "os-health.py"
LOG_FILE             = AGENT_OS / ".morning-brief.log"

GITHUB_REPO = "<YOUR_GITHUB>/<YOUR_REPO>"
RECIPIENT = "<YOUR_EMAIL>"


def log(msg):
    ts = datetime.now().isoformat(timespec="seconds")
    line = f"[{ts}] {msg}\n"
    sys.stderr.write(line)
    try:
        LOG_FILE.open("a").write(line)
    except Exception:
        pass


def jsonl(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


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


# ─── State gatherers ────────────────────────────────────────────────────


def gather_inbox_state():
    queue = jsonl(INBOX_QUEUE)
    processed = jsonl(INBOX_PROCESSED)
    yesterday = datetime.now() - timedelta(days=1)
    handled_24hr = [
        p for p in processed
        if p.get("processed_at") and datetime.fromisoformat(p["processed_at"]) > yesterday
    ]
    by_cat = {}
    for q in queue:
        c = q.get("category", "unknown")
        by_cat[c] = by_cat.get(c, 0) + 1
    return {
        "unprocessed_total": len(queue),
        "by_category": by_cat,
        "handled_last_24hr": len(handled_24hr),
    }


def gather_bookings_state():
    queue = jsonl(BOOKINGS_QUEUE)
    processed = jsonl(BOOKINGS_PROCESSED)
    upcoming = []
    for q in queue:
        if q.get("category") == "new":
            upcoming.append({
                "prospect": q.get("prospect_name") or q.get("prospect_email"),
                "when": q.get("meeting_dtstart") or q.get("when_text_fallback"),
                "summary": q.get("meeting_summary"),
            })
    return {
        "unprocessed_total": len(queue),
        "upcoming": upcoming,
        "processed_total": len(processed),
    }


def gather_pipeline_state():
    if not TRACKING_FILE.exists():
        return {"total_recipients": 0, "by_status": {}}
    data = json.loads(TRACKING_FILE.read_text())
    recipients = data.get("recipients", [])
    by_status = {}
    retry_available = []
    dead_no_alt = []
    for r in recipients:
        status = r.get("status", "queued")
        by_status[status] = by_status.get(status, 0) + 1
        if status == "bounced-retry-available":
            retry_available.append({
                "name": r["name"],
                "from": r.get("bounced_address"),
                "to": r.get("resend_to") or r.get("recipient_email"),
            })
        elif status == "bounced-no-alt":
            dead_no_alt.append({"name": r["name"], "from": r.get("bounced_address")})
    return {
        "total_recipients": len(recipients),
        "by_status": by_status,
        "retry_available": retry_available,
        "dead_no_alt": dead_no_alt,
    }


def gather_github_state():
    """Pull plugin repo stats via gh CLI. Returns None if gh isn't available."""
    try:
        out = subprocess.run(
            ["gh", "api", f"repos/{GITHUB_REPO}",
             "--jq", "{stars: .stargazers_count, forks: .forks_count, watchers: .subscribers_count, open_issues: .open_issues_count}"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return json.loads(out.stdout)
    except Exception as e:
        log(f"github stats failed: {e}")
    return None


def gather_brand_audit():
    if not AUDIT_SCRIPT.exists():
        return {"status": "missing", "summary": "audit-brand.py not present"}
    try:
        r = subprocess.run(["python3", str(AUDIT_SCRIPT)], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return {"status": "clean", "summary": "12 / 12 canonical sections present"}
        else:
            # Extract first ⚠ line for the summary
            for line in r.stdout.splitlines():
                if "⚠" in line or "Missing" in line:
                    return {"status": "gaps", "summary": line.strip()}
            return {"status": "gaps", "summary": "audit returned non-zero — run manually"}
    except Exception as e:
        return {"status": "error", "summary": str(e)}


def gather_os_health():
    if not HEALTH_SCRIPT.exists():
        return {"status": "missing"}
    try:
        r = subprocess.run(["python3", str(HEALTH_SCRIPT)], capture_output=True, text=True, timeout=15)
        # Strip ANSI codes for cleaner parsing
        plain = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout)
        m = re.search(r"(\d+)\s+(?:checks|of)\s+(\d+)?\s*(?:passed|checks)?", plain)
        all_green = "ALL GREEN" in plain
        # Extract a quick counter from the summary line
        m2 = re.search(r"(\d+)\s+failure", plain)
        m3 = re.search(r"(\d+)\s+warning", plain)
        return {
            "all_green": all_green,
            "failures": int(m2.group(1)) if m2 else 0,
            "warnings": int(m3.group(1)) if m3 else 0,
            "exit_code": r.returncode,
            "raw_summary_line": next((l for l in plain.splitlines() if "GREEN" in l or "failure" in l or "warning" in l), ""),
        }
    except Exception as e:
        return {"status": "error", "summary": str(e)}


def gather_yesterday_activity():
    """Pull MEMORY.md entries with today's or yesterday's date as a quick digest."""
    if not MEMORY.exists():
        return []
    text = MEMORY.read_text()
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    headings = []
    for line in text.splitlines():
        if line.startswith("## [") and (today in line or yesterday in line):
            m = re.search(r"\[\d{4}-\d{2}-\d{2}\]\s+(.+)", line)
            if m:
                headings.append(m.group(1).strip())
    return headings[-8:]  # last 8 entries from today/yesterday


# ─── Priority-action heuristics ─────────────────────────────────────────


def derive_top_actions(inbox, bookings, pipeline, audit, health):
    """Return the top 3 (or fewer) prioritized action items as strings."""
    actions = []

    # Order matters — most-time-sensitive first
    if bookings["unprocessed_total"] > 0:
        n = bookings["unprocessed_total"]
        names = [b["prospect"] for b in bookings["upcoming"][:3] if b.get("prospect")]
        when = bookings["upcoming"][0]["when"] if bookings["upcoming"] else "—"
        actions.append(
            f"**PREP FOR {n} BOOKING(S)** — type `/process-bookings` in Claude. "
            f"First up: {names[0] if names else 'unknown'} ({when})."
        )

    inbox_actionable = sum(v for k, v in inbox["by_category"].items() if k in ("interested", "objection", "referral"))
    if inbox_actionable > 0:
        actions.append(
            f"**RESPOND TO {inbox_actionable} HOT REPL(IES)** — type `/handle-replies`. "
            f"Categories: {', '.join(f'{v} {k}' for k, v in inbox['by_category'].items() if k in ('interested', 'objection', 'referral'))}."
        )

    if pipeline["retry_available"]:
        n = len(pipeline["retry_available"])
        names = ", ".join(r["name"] for r in pipeline["retry_available"][:4])
        actions.append(
            f"**SEND {n} RETRY DRAFT(S)** — bounced on pattern-guess, Hunter-verified versions waiting in your Gmail Drafts. "
            f"Names: {names}."
        )

    if audit["status"] == "gaps":
        actions.append(f"**CLOSE BRAND-DOC GAPS** — {audit['summary']}")

    if health.get("failures", 0) > 0:
        actions.append(
            f"**FIX OS HEALTH** — {health['failures']} failure(s). Run `python3 scripts/os-health.py` for the fix commands."
        )

    if not actions:
        actions.append(
            "**SOURCE / OUTREACH / CONTENT** — inbox is clean, no bookings pending. "
            "Pick one: source a new batch, write a LinkedIn post, follow up on warm leads."
        )

    return actions[:3]


# ─── Brief rendering ────────────────────────────────────────────────────


def render_brief(inbox, bookings, pipeline, github, audit, health, yesterday, actions):
    today = datetime.now().strftime("%a %b %d")
    today_iso = datetime.now().strftime("%Y-%m-%d")

    # Compact subject line — scannable at a glance from the inbox list
    subject_parts = [f"<VENTURE> · {today}"]
    if inbox["unprocessed_total"]:
        subject_parts.append(f"{inbox['unprocessed_total']} repl{'y' if inbox['unprocessed_total'] == 1 else 'ies'}")
    if bookings["unprocessed_total"]:
        subject_parts.append(f"{bookings['unprocessed_total']} booking{'s' if bookings['unprocessed_total'] != 1 else ''}")
    if pipeline["retry_available"]:
        subject_parts.append(f"{len(pipeline['retry_available'])} retr{'y' if len(pipeline['retry_available']) == 1 else 'ies'} pending")
    if len(subject_parts) == 1:
        subject_parts.append("inbox quiet · pick something to ship")
    subject = " · ".join(subject_parts)

    body_lines = [
        f"# {today} — your morning brief",
        "",
        "## What needs you today",
        "",
    ]
    for i, action in enumerate(actions, 1):
        body_lines.append(f"{i}. {action}")
    body_lines.extend([
        "",
        "---",
        "",
        "## Inbox state",
        f"- **Reply queue:** {inbox['unprocessed_total']} unprocessed"
        + (f" — {', '.join(f'{v} {k}' for k, v in inbox['by_category'].items())}" if inbox['by_category'] else ""),
        f"- **Handled last 24 hr:** {inbox['handled_last_24hr']}",
        f"- **Booking queue:** {bookings['unprocessed_total']} pending · {bookings['processed_total']} processed (lifetime)",
        "",
        "## Pipeline",
        f"- **Total recipients tracked:** {pipeline['total_recipients']}",
    ])
    for status, count in sorted(pipeline["by_status"].items()):
        body_lines.append(f"  - {status}: {count}")
    if pipeline["retry_available"]:
        body_lines.append("")
        body_lines.append("### Retry-available (Hunter-verified versions in Drafts folder)")
        for r in pipeline["retry_available"]:
            body_lines.append(f"  - {r['name']}: was `{r['from']}` → SEND `{r['to']}`")
    if pipeline["dead_no_alt"]:
        body_lines.append("")
        body_lines.append("### Dead-end (no Hunter alternative)")
        for d in pipeline["dead_no_alt"]:
            body_lines.append(f"  - {d['name']}: `{d['from']}` — manual lookup or defer until Hunter quota resets")

    body_lines.extend([
        "",
        "## Plugin activity (GitHub)",
    ])
    if github:
        body_lines.extend([
            f"- Stars: {github.get('stars', '?')}",
            f"- Forks: {github.get('forks', '?')}",
            f"- Watchers: {github.get('watchers', '?')}",
            f"- Open issues: {github.get('open_issues', '?')}",
        ])
    else:
        body_lines.append("- (gh CLI unavailable — run `gh auth status` to verify)")

    body_lines.extend([
        "",
        "## Brand-doc health",
        f"- **Audit status:** {audit['status']}",
        f"- {audit['summary']}",
        "",
        "## OS health",
    ])
    if health.get("all_green"):
        body_lines.append(f"- ✓ ALL GREEN — {health.get('raw_summary_line', '')}")
    else:
        body_lines.extend([
            f"- {health.get('failures', '?')} failure(s), {health.get('warnings', '?')} warning(s)",
            f"- {health.get('raw_summary_line', '(no summary)')}",
            "- Run `python3 ~/.agent-os/scripts/os-health.py` for the full report",
        ])

    body_lines.extend([
        "",
        "## Yesterday's activity (MEMORY.md)",
    ])
    if yesterday:
        for h in yesterday:
            body_lines.append(f"- {h}")
    else:
        body_lines.append("- (no MEMORY.md entries from yesterday — quiet day)")

    body_lines.extend([
        "",
        "---",
        "",
        "_Generated by `scripts/morning-brief.py` · runs Mon–Fri at 07:00 PT via launchd `io.<NS>.morning-brief`._",
        "",
        f"_To run again on demand:_ `python3 ~/.agent-os/scripts/morning-brief.py`",
    ])

    return subject, "\n".join(body_lines)


def markdown_to_html(md):
    """Light MD→HTML for the email body. Keeps it readable in Gmail."""
    lines = md.splitlines()
    out = []
    in_list = False
    for line in lines:
        # Headings
        if line.startswith("# "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h2 style='color:#0a0e1a; margin: 24px 0 10px;'>{line[2:]}</h2>")
        elif line.startswith("## "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h3 style='color:#0a0e1a; margin: 20px 0 8px; font-size: 16px;'>{line[3:]}</h3>")
        elif line.startswith("### "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h4 style='color:#475569; margin: 14px 0 6px; font-size: 14px;'>{line[4:]}</h4>")
        elif line.startswith("---"):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append("<hr style='border:0; border-top:1px solid #e5e7eb; margin: 20px 0;'>")
        elif line.startswith("  - "):
            # nested list — inline as second-level
            content = line[4:]
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", content)
            content = re.sub(r"`([^`]+)`", r"<code style='background:#f1f5f9;padding:1px 5px;border-radius:3px;font-size:12px;'>\1</code>", content)
            out.append(f"<li style='margin-left:24px;color:#64748b;font-size:13px;'>{content}</li>")
        elif line.startswith("- "):
            if not in_list:
                out.append("<ul style='padding-left:20px; margin: 6px 0;'>")
                in_list = True
            content = line[2:]
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", content)
            content = re.sub(r"`([^`]+)`", r"<code style='background:#f1f5f9;padding:1px 5px;border-radius:3px;font-size:12px;'>\1</code>", content)
            out.append(f"<li style='margin-bottom:4px;'>{content}</li>")
        elif re.match(r"^\d+\.\s", line):
            # numbered priority action
            if in_list:
                out.append("</ul>")
                in_list = False
            num_match = re.match(r"^(\d+)\.\s+(.+)", line)
            num, content = num_match.group(1), num_match.group(2)
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", content)
            content = re.sub(r"`([^`]+)`", r"<code style='background:#f1f5f9;padding:1px 5px;border-radius:3px;font-size:12px;'>\1</code>", content)
            out.append(
                f"<div style='margin:8px 0;padding:10px 14px;background:#0a0e1a;color:#f0f4f8;border-radius:6px;border-left:3px solid #00d4ff;'>"
                f"<strong style='color:#00d4ff;'>{num}.</strong> {content}</div>"
            )
        elif line.strip().startswith("_") and line.strip().endswith("_"):
            out.append(f"<p style='color:#94a3b8;font-size:11px;font-style:italic;margin:6px 0;'>{line.strip().strip('_')}</p>")
        elif line.strip() == "":
            if in_list:
                out.append("</ul>")
                in_list = False
        else:
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            content = re.sub(r"`([^`]+)`", r"<code>\1</code>", content)
            out.append(f"<p style='margin:6px 0;'>{content}</p>")
    if in_list:
        out.append("</ul>")
    inner = "\n".join(out)
    return (
        "<div style='font-family:-apple-system, BlinkMacSystemFont, Inter, sans-serif; "
        "max-width:680px; margin:0 auto; color:#1f2937; font-size:14px; line-height:1.5;'>"
        + inner +
        "</div>"
    )


def push_draft_to_gmail(service, subject, body_md):
    from email.mime.multipart import MIMEMultipart

    body_html = markdown_to_html(body_md)
    msg = MIMEMultipart("alternative")
    msg["to"] = RECIPIENT
    msg["from"] = RECIPIENT
    msg["subject"] = subject
    msg.attach(MIMEText(body_md, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    return result["id"], result.get("message", {}).get("id")


def apply_brief_label(service, message_id):
    try:
        labels = service.users().labels().list(userId="me").execute().get("labels", [])
        target = next((l for l in labels if l["name"] == "<NS>/morning-brief"), None)
        if target:
            service.users().messages().modify(
                userId="me", id=message_id, body={"addLabelIds": [target["id"]]}
            ).execute()
    except Exception as e:
        log(f"label apply failed: {e}")


def main():
    log("=== morning-brief.py started ===")

    inbox     = gather_inbox_state()
    bookings  = gather_bookings_state()
    pipeline  = gather_pipeline_state()
    github    = gather_github_state()
    audit     = gather_brand_audit()
    health    = gather_os_health()
    yesterday = gather_yesterday_activity()
    actions   = derive_top_actions(inbox, bookings, pipeline, audit, health)

    subject, body = render_brief(inbox, bookings, pipeline, github, audit, health, yesterday, actions)
    log(f"subject: {subject}")
    log(f"body length: {len(body)} chars")
    log(f"top actions: {len(actions)}")

    try:
        service = load_gmail_service()
        draft_id, message_id = push_draft_to_gmail(service, subject, body)
        log(f"✓ draft created: {draft_id} (message {message_id})")
        if message_id:
            apply_brief_label(service, message_id)
        print(f"✓ Morning brief drafted to Gmail (draft {draft_id})")
        print(f"  Subject: {subject}")
        print(f"  Open Gmail Drafts to review.")
    except Exception as e:
        log(f"✗ gmail draft failed: {e}")
        print(f"✗ failed to create draft: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
