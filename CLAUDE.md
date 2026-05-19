# CLAUDE.md — Routing Brain (template)

This file is the dispatcher. When Claude Code receives a request inside this workspace, route it to the right skill, agent, or persona using the rules below.

Fork this file and edit the routing table to match your work. The architecture below is what every claude-agent-os install ships with — the rest is yours to customize.

## Defaults

- **Default model:** opus (override in `settings.json`)
- **Default permissions:** see `settings.json`
- **Pre-tool-use hook** runs before any destructive operation (`hooks/pre-tool-use/block-dangerous-commands.js`)
- **Post-tool-use hook** routes to sub-hooks via `hooks/post-tool-use/dispatcher.js`
- **Notification hook** surfaces approval requests (`hooks/notification/notify-permission.js`)

## Intent → routing (built-in)

The shipped agents:

| Intent signal | Route to |
|---|---|
| "audit brand", "BRAND.md gaps", "/audit-brand" | `agents/brand-auditor.md` + run `scripts/audit-brand.py` |
| "/handle-replies", "check for replies", "process inbox queue" | `agents/reply-handler.md` + check `~/.agent-os/inbox-queue.jsonl` (run `scripts/fetch-replies.py` first if stale) |
| "/process-bookings", "any new bookings?", "prep for [name]" | `agents/calendar-booking.md` + check `~/.agent-os/bookings-queue.jsonl` (run `scripts/fetch-bookings.py` first if stale) |
| "/morning-brief", "what's on tap today", "brief me" | `agents/morning-brief.md` + run `scripts/morning-brief.py` |

Add your own rows below — map your intents to your skill files.

## Persona routing (template)

If a request implies a role identity, load a persona FIRST then route to the skill. Edit the personas in `agents/personas/` to fit your context:

| Signal | Persona |
|---|---|
| Selling, prospect conversation, demo call | `agents/personas/enterprise-ae.md` |
| Building tools, automation, technical work | `agents/personas/gtm-engineer.md` |
| Strategic call, pricing, GTM direction | `agents/personas/solo-founder.md` |

## Memory rules

- **BRAND.md** — positioning reference. Audit via `scripts/audit-brand.py`. Run after every edit.
- **SOUL.md** — voice reference. Read-only.
- **MEMORY.md** — append-only campaign log. Add dated entries; never edit prior entries.
- **CONNECTIONS.md** — auth-boundary rules. Read at session start; append-only history.

## Proactive audits

Run on demand or wire to launchd / scheduled-tasks:

| Auditor | What it checks | How to run |
|---|---|---|
| `agents/brand-auditor.md` | `BRAND.md` for canonical sections | `python3 scripts/audit-brand.py` |
| `agents/reply-handler.md` | Inbox for replies; classifies; queues for processing | `python3 scripts/fetch-replies.py` + `/handle-replies` |
| `agents/calendar-booking.md` | Inbox for new bookings; cross-refs against `outbox/sent-tracking.json` | `python3 scripts/fetch-bookings.py` + `/process-bookings` |
| `agents/morning-brief.md` | Aggregates state into a Mon–Fri 07:00 draft with top-3 priority actions | launchd `io.<NS>.morning-brief` + `/morning-brief` on-demand |

## Auth boundary (CONNECTIONS.md)

Before any Chrome, Gmail, or CRM action, verify the active connection is on the right side of any boundary you've defined in `CONNECTIONS.md` (e.g., venture vs day-job).

## Hard safety rules (never override)

- **Never send** an email, DM, or message without explicit human approval in the chat.
- **Never push** to a public git repo without confirmation.
- **Never run** destructive DB writes without showing the diff first.
- **Never run** `rm -rf`, `git push --force` on main, or anything matched by `hooks/pre-tool-use/block-dangerous-commands.js`.

## Drafts only

Every outbound artifact (email, DM, post, CRM write) lands in a draft state by default. The human pulls every send trigger.
