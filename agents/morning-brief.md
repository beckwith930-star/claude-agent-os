---
agent: morning-brief
when_to_load: "/morning-brief" command; "what's on tap today"; "brief me"; "what should I work on"; on-demand after the launchd Mon–Fri 07:00 run drops the day's draft
voice: per SOUL.md — Amazon-memo terse, no fluff, ranked priorities first, evidence under each. The brief speaks TO the operator, not for him. Never marketing copy.
constraints: Drafts only. The brief lands in Gmail Drafts as a memo to self (<YOUR_EMAIL> → <YOUR_EMAIL>). Never sends. Never claims customer outcomes. Auth boundary applies to every data source it reads.
---

# Morning Brief Agent

**Purpose:** Each weekday morning, aggregate the state of the venture into a single decision-ready memo so the operator opens his inbox and sees one email that tells him exactly what to work on first. Closes the loop between always-on inbox agents (reply-handler, calendar-booking) and human attention.

The script (`scripts/morning-brief.py`) is the whole thing — no fetcher/processor split. Single Python runner triggered by launchd Mon–Fri @ 07:00 local. THIS file is the on-demand companion: load when the operator types `/morning-brief` to regenerate the brief mid-day or to inspect / tune the priority heuristics.

## Single-script architecture (why no split)

The reply-handler and calendar-booking agents are two-script (fetcher + processor) because they react to external events that may need LLM judgment. Morning Brief is different:

- **All data sources are already on disk** (queues, sent-tracking.json, MEMORY.md, plist state).
- **The aggregation is deterministic** — counts, file mtimes, JSON status fields. No classification required.
- **The output is a single email draft per run** — no per-item queue.

So one script does the whole job: gather → derive priorities → render markdown → convert to HTML → push Gmail draft → label it. Idempotent (re-running just creates a new draft).

## What the brief aggregates

| Source | What it pulls |
|---|---|
| `~/.agent-os/inbox-queue.jsonl` | Unprocessed replies (count + per-category breakdown) |
| `~/.agent-os/inbox-queue-processed.jsonl` | Replies processed in last 24 hours |
| `~/.agent-os/bookings-queue.jsonl` | New bookings awaiting prep |
| `~/.agent-os/bookings-queue-processed.jsonl` | Bookings with prep docs already generated |
| `~/.agent-os/outbox/sent-tracking.json` | Pipeline state — sent / bounced / replied / meeting-booked / dead per recipient; retry-available count |
| `~/.agent-os/MEMORY.md` (tail ~1500 chars) | Yesterday's decisions, what was tried, what's next |
| `scripts/audit-brand.py` (subprocess) | BRAND.md gap count (should be 12/12 canonical sections) |
| `scripts/os-health.py` (subprocess) | OS health failure/warning counts |
| `gh api repos/<YOUR_GITHUB>/<YOUR_REPO>` | Stars / forks / open issues on the plugin (proxy for inbound interest) |

Each gatherer is wrapped in try/except — if a source is unavailable (gh not authed, audit script broken, MEMORY.md missing), the brief skips that section rather than failing the whole run.

## Priority-action derivation

The brief's top section is **"Top 3 priority actions for today"** — derived deterministically from gathered state by `derive_top_actions()`. The ranking heuristic (highest precedence first):

1. **Bookings in `bookings-queue.jsonl` not yet processed** → "Run `/process-bookings` — N new booking(s) awaiting prep doc"
2. **Hot replies in `inbox-queue.jsonl` (categories: `interested`, `referral`, `objection`)** → "Run `/handle-replies` — N hot reply/replies need a response today"
3. **Retry-available bounces in `sent-tracking.json` (status: `retry-available`)** → "Send N retry-available bounce(s) — Hunter-verified addresses sitting in Gmail Drafts"
4. **Brand audit failures** → "Fill brand-doc gap: [missing canonical sections]"
5. **OS health failures** → "Repair OS: N check(s) failing — run `python3 ~/.agent-os/scripts/os-health.py`"
6. **Default (nothing urgent in any queue)** → "Ship something — write 1 outbound batch OR 1 LinkedIn post OR 1 plugin improvement"

Hard cap of 3 items. If more than 3 conditions trigger, the highest-precedence three win. The default fallback only appears if NO higher-precedence condition fires.

## Brief format

```
Subject: <VENTURE> · {Day Mon DD} · {N replies} · {M bookings} · {K retries pending}

# Today's brief — {Day, Mon DD YYYY}

## Top 3 priority actions
1. [Highest-precedence action with one-line evidence]
2. [Second action]
3. [Third action]

## Inbox state
- {N} unprocessed replies ({per-category breakdown})
- {M} replies processed in last 24h

## Pipeline
- {sent} sent · {replied} replied · {meeting-booked} booked · {bounced} bounced · {retry-available} retry-available · {dead} dead
- Batch rollup: [per-batch counts]

## Bookings
- {N} new bookings awaiting prep:
  - [Name] · [Company] · [Day Time TZ]
- {M} processed bookings on calendar this week

## Plugin (sales-ae-pro)
- {stars}★ · {forks} forks · {open_issues} open issues
- Recent issue activity: [titles of last 3 if any]

## Brand-doc health
- Audit: {12/12 ✓} OR [gaps listed]

## OS health
- {N} failures · {M} warnings · {K} clean

## Yesterday (from MEMORY.md tail)
{last 24h of MEMORY entries verbatim}
```

The rendered HTML wraps each section in inline-styled cards. The "Top 3 priority actions" block uses dark-navy (#0a1730) background + cyan (#00d4ff) accent border to match brand. Body font is system-ui stack for native rendering across mail clients.

## When to run on-demand (`/morning-brief`)

The launchd job fires Mon–Fri @ 07:00. the operator types `/morning-brief` when he wants to regenerate mid-day — e.g.:

- After processing the inbox queue at 9 AM, regenerate to see the post-cleanup state
- After a booking comes in midday, regenerate to surface the new prep doc requirement
- After fixing an OS health failure, regenerate to confirm clean
- Saturday/Sunday on-demand if the operator's working the weekend

On-demand invocation: just run `python3 ~/.agent-os/scripts/morning-brief.py`. Same script. New draft appended to Drafts folder, labeled `<NS>/morning-brief`.

## Customization (tune in `morning-brief.py`)

- **Change priority heuristics**: edit `derive_top_actions()`. Each `if` block is a precedence tier.
- **Add a new data source**: add a `gather_X()` function returning a dict, wrap in try/except, include in `render_brief()`.
- **Adjust HTML styling**: edit `markdown_to_html()`. Inline styles only (Gmail strips `<style>` blocks).
- **Change the schedule**: edit `~/Library/LaunchAgents/io.<NS>.morning-brief.plist` then `launchctl unload && launchctl load`.

## Hard rules (never override)

- ❌ **Never send** the brief. It lands in Drafts. the operator reads it; the draft auto-archives when he opens it (or stays in Drafts until manually purged).
- ❌ **Never claim specific customer outcomes** in the brief — we have 0 customers. Pipeline stats are honest counts (sent/replied/bounced), not "wins."
- ❌ **Never include Work day-job context** — the brief reads only from `~/.agent-os/` and the public plugin repo. Auth boundary applies.
- ❌ **Never derive priorities from `MEMORY.md` content** — MEMORY is for context display only. Priorities come from queues + tracking JSON (deterministic).
- ❌ **Never auto-execute** any of the priority actions. The brief surfaces what to do; the operator decides.

## Failure modes

| Failure | How to handle |
|---|---|
| `gh` CLI not authed | Skip plugin section; note "plugin stats unavailable" in brief |
| `audit-brand.py` exits non-zero | Surface the failure as a top-3 priority action ("Fill brand-doc gap") |
| `os-health.py` exits non-zero | Surface failure count; show in OS health section |
| `inbox-queue.jsonl` missing | Treat as 0 unprocessed; no error |
| `MEMORY.md` missing | Skip yesterday section; note "no recent memory entries" |
| Gmail draft push fails | Log error to `.morning-brief-stderr.log`; launchd will retry tomorrow |
| Brief generates but is empty (nothing in any queue) | Still drop the draft — the operator should see the "Ship something" default action |

## Quick commands

```bash
# Generate the brief now (on-demand)
python3 ~/.agent-os/scripts/morning-brief.py

# Check the launchd job is loaded
launchctl list | grep morning-brief

# Tail the brief's log
tail ~/.agent-os/.morning-brief-stderr.log
tail ~/.agent-os/.morning-brief-stdout.log

# See past briefs in Gmail (label search)
# (use gmail-<NS> MCP)  search_emails q="label:<NS>/morning-brief"
```

## Future improvements (deferred)

- Weekly "Friday rollup" variant — different priority heuristics (pipeline cleanup, weekly retro, next-week planning)
- Slack/Discord delivery alternative to Gmail draft (when the operator's on the road)
- "Brief diff" — what changed since yesterday's brief, to make weekly reading faster
- Auto-suggest the next outbound batch source (when no urgent inbox work exists and "Ship something" fires)
- Integration with calendar — pull today's meetings into the brief alongside bookings
