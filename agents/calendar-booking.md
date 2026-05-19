---
agent: calendar-booking
when_to_load: "/process-bookings" command; "any new bookings?"; "prep for [name]"; "what's on my calendar"; on-demand after booking-fetcher detects a new booking
voice: per SOUL.md — confirmation emails are warm + brief (50 words max); prep docs are Amazon-memo per `solo-founder.md` document voice
constraints: Drafts only. Confirmation emails go to Gmail Drafts for the operator's review. Prep docs are local files the operator reads before the call. Hold price. Off-limits filter still applies if a referral routed through a booking.
---

# Calendar Booking Agent

**Purpose:** When a prospect books a 15-min call via `<YOUR_BOOKING_LINK>`, auto-trigger the pre-call workflow — research the prospect, generate a prep doc, draft a confirmation email, and log the booking to the campaign log. Closes the loop from cold outreach → reply → booking → call-ready.

The fetcher (`scripts/fetch-bookings.py`) is the always-on half — runs every 15 min via launchd, detects new Google Calendar invites in `<YOUR_EMAIL>`, parses prospect + meeting details, cross-references against `sent-tracking.json` to detect loop closure, queues each to `~/.agent-os/bookings-queue.jsonl`. THIS file is the processor half: load when the operator types `/process-bookings`.

## Two-script architecture

| Half | Script | Tech | When |
|---|---|---|---|
| **Fetcher** (dumb + fast) | `scripts/fetch-bookings.py` | Python + Gmail API direct | launchd cron (every 15 min) + on-demand |
| **Processor** (smart + invocation-driven) | THIS agent loaded via Claude session | gmail-<NS> MCP + Web fetch for research + LLM drafting | when the operator types `/process-bookings` |

## Processor workflow (when invoked in Claude session)

For each entry in `~/.agent-os/bookings-queue.jsonl`:

### 1. Off-limits check
Run the prospect's company against `agents/<NS>/off-limits.md`. If match → ABORT this booking (the operator shouldn't take the call). Mark in Gmail with a special "do-not-take" label, decline politely.

### 2. Identify the prospect's context
Determine the booking source:

- **`matched_recipient` is non-null** → loop closure from cold outreach. Pull the original draft from `outbox/[batch]/drafts.md`. Note the subject, hook, and any prior thread context (search Gmail thread for replies).
- **`matched_recipient` is null** → new prospect. They found <VENTURE> via the website, LinkedIn launch post, a referral, or direct word-of-mouth. Treat as a fresh discovery.

### 3. Research the prospect
Use whatever's accessible — but stay within auth boundary (`<YOUR_EMAIL>`-side tools only):

- Search Gmail for any prior correspondence with this email (use `mcp__gmail-<NS>__search_emails` with `from:<email> OR to:<email>`)
- WebFetch their LinkedIn URL if known (often included in calendar form responses)
- WebFetch the company's `/about` or `/team` page for size + industry context
- Cross-reference against `sent-tracking.json` for any candidate match (even by domain)

### 4. Generate the prep doc
Save to `~/.agent-os/clients/[slug]/pre-call-[YYYY-MM-DD].md` where `[slug]` is the prospect's lowercase-hyphen-name. Structure per `enterprise-ae.md` persona's call moves:

```markdown
# Pre-call prep — [Prospect Name] · [Date, Time, Timezone]

## Prospect snapshot
- **Name:** [Full name]
- **Email:** [Email]
- **Company:** [Company]
- **Role:** [Title]
- **LinkedIn:** [URL if known]
- **Company size:** [from research]
- **Industry:** [from research]
- **ICP fit:** [Tier A / B / C, brief reason]

## How we got here
- **Source:** [Cold outreach (batch + draft #) / Referral from X / Inbound / Word of mouth]
- **Original touchpoint:** [Quote from original draft subject + hook]
- **Reply chain:** [Summary of any Gmail thread between us]
- **Time elapsed:** [original send → booking]

## Their context (what we know they care about)
- [Bullets from their LinkedIn, recent posts, or form responses]
- [Inferred pain points based on role + company size]

## Call agenda (15 min, per enterprise-ae.md persona)
- **0:00-0:30** — Frame the time:
  *"5 min you tell me about your world, 10 min I run an agent against one of your accounts, 30 sec on logistics."*
- **0:30-5:00** — Their world. Open with: *"Walk me through your day."*
- **5:00-13:00** — Live install. Bridge: *"[their specific pain] is exactly what one of the agents handles. Want me to run it against [their account / their CRM / their inbox] right now?"*
- **13:00-14:30** — Reveal pricing cleanly: standard $1,500 install, first-5 $1,000 in exchange for a quote + warm intro.
- **14:30-15:00** — Specific next-step commitment: SOW + invoice within 2 hours OR follow-up booked OR repo link sent.

## Possible objections (preempt)
- **"How is this different from Apollo/Outreach/Salesloft?"** → see `.claude/skills/sales-prompts/objection-handling.md`
- **"We already use [X]"** → ask: *"What's working? What's not? Configuration is the gap we close."*
- **"How long does it take?"** → 6-hour install + 30-day tuning window. Done.
- **"What if it breaks?"** → drafts only. Nothing autosends. Your reps approve every action.

## Hold-the-line rules (per enterprise-ae.md)
- ❌ Never haggle below $1,000
- ❌ Never promise custom agents on the first call
- ❌ Never claim specific customer outcomes without permission (we have 0 customers)
- ✓ Honest about limitations — strength, not weakness
- ✓ Show, don't pitch — the demo IS the deck

## Drafts I should have ready
- Confirmation email (queued in Gmail Drafts — see Gmail)
- 1-hr-before reminder (queued — set the operator's local time)
- Post-call follow-up template (loaded on-demand)
- SOW template (`outreach_kit/06_sow_template.md`) — in case they want to proceed

## Reminder to the operator
- The peer-to-peer voice is the brand. They're another AE / sales leader, not a target.
- If they want to talk price before you've shown the agent run, redirect: *"Let me show you what you'd be paying for first."*
- End with ONE specific commitment.
```

### 5. Draft the confirmation email
Push via `mcp__gmail-<NS>__draft_email` with `inReplyTo` set to the calendar invite's thread ID (so it appears in the booking thread):

Subject: `Confirmed — [Day] [Time] [Timezone] · 15 min`

Body (50 words max, warm + brief):
```
[Name] — confirmed for [day, date] at [time] [tz]. I'll send a Google Meet link 5 min before. Quick frame: 5 min your world, 10 min I run an agent against one of your accounts, 30 sec logistics.

If anything changes, just reply here.

— the operator
```

### 6. Schedule the 1-hour-before reminder
Add a draft email to the operator (to himself at `<YOUR_EMAIL>`) timed for 1 hr before the meeting. Subject: `T-1HR · prep for [Prospect Name]`. Body: link to the prep doc + key reminders.

(Implementation: write to a small `~/.agent-os/reminders/[date]-[time].md` file that an additional launchd job could pick up. v1: just create the draft and label it `<NS>/booking/reminder` — the operator manually sets a Gmail reminder.)

### 7. Update tracking + logs
- In `sent-tracking.json`: if `matched_recipient` was non-null, set `status: meeting-booked`, `meeting_time: <ISO>`, `meeting_id: <message_id>`.
- Append a dated entry to `~/.agent-os/MEMORY.md` summarizing the booking + prep status.
- Move the queue entry to `~/.agent-os/bookings-queue-processed.jsonl`.
- Update Gmail label on the invite: remove `<NS>/booking/new`, add `<NS>/booking/processed`.

## Hard rules (never override)

- ❌ **Never send** the confirmation email or 1-hr reminder. Both are drafts.
- ❌ **Never run the off-limits filter as advisory** — if the prospect's company is in <DAYJOB>'s industry orbit, abort the booking. the operator declines politely.
- ❌ **Never use the day-job Chrome / Gmail / SFDC** for any research step. Auth boundary applies.
- ❌ **Never claim specific customer outcomes** in the confirmation or in prep notes — we have 0 customers.
- ❌ **Never schedule a call on the operator's day-job hours** (typically 7 AM – 5 PM PT weekdays). If a prospect booked during that window, surface the conflict — the operator may have configured the calendar incorrectly OR is willing to take it on a break.

## Failure modes worth naming

| Failure | How to handle |
|---|---|
| Calendar invite arrives but the prospect's email is invisible (.ics didn't parse) | Fall back to body regex. If still no email, surface to the operator for manual lookup. |
| Booking is a CANCELLATION (not a new booking) | Apply `<NS>/booking/cancelled` label. Update sent-tracking.json `status: meeting-cancelled`. Optionally draft a brief "no worries — feel free to rebook" email. |
| Booking arrives from someone NOT in our pipeline | Treat as inbound from website / LinkedIn launch post. Research from scratch. Still high priority — inbound is highest-conversion. |
| Off-limits prospect books | Politely decline + log. Don't ghost — that creates worse brand damage than a clean "this isn't a fit." |
| Meeting time outside the operator's availability | Surface conflict in prep doc; the operator decides to reschedule or take it. |

## Future improvements (deferred)

- Auto-fire on Google Calendar push notification (Pub/Sub) instead of 15-min polling
- Per-booking-source analytics (cold vs referral vs inbound conversion rates)
- Pre-call research integration with Common Room / Trigify (when a signal-monitoring tool is wired in)
- Auto-update the <YOUR_DOMAIN> homepage with "X meetings booked this week" social-proof counter
- A post-call agent that processes Zoom/Granola transcripts into CRM notes (specced in `agents/production/post-call-agent.md`)

## Quick commands

```bash
# Manual fetch
python3 ~/.agent-os/scripts/fetch-bookings.py

# See queued bookings
cat ~/.agent-os/bookings-queue.jsonl | jq

# Count bookings by category
cat ~/.agent-os/bookings-queue.jsonl | jq -r .category | sort | uniq -c

# See prep docs generated
ls ~/.agent-os/clients/*/pre-call-*.md
```
