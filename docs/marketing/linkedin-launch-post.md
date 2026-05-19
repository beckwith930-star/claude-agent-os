Claude Code sessions don't remember. Close the tab, open a new one, and you re-explain your project, your tools, and yesterday's decisions from scratch. The chat window holds the state — and the chat window is disposable.

claude-agent-os moves that state out of the chat. It runs as a directory-scoped persistent layer underneath Claude Code: long-lived agents on a cadence, a hook layer wrapping every tool call, and a memory file the agents read on session start.

Three agents run on their own clocks:

- Reply Handler classifies new mail every 30 minutes and queues drafts for review.
- Calendar Booking sweeps every 15 minutes for hold-and-confirm windows.
- Morning Brief runs Mon–Fri at 7AM and writes the day's working file.

Two hooks sit under every tool call: a pre-tool-use hook (block-dangerous-commands.js) refuses destructive shell commands before they run; a post-tool-use hook (dispatcher.js) routes events to logs and memory.

What it doesn't do: nothing sends without you. Every email, calendar invite, and write action lands as a draft. macOS only for now — the cadence is run by launchd, so Linux and Windows wait their turn.

MIT licensed. Built for one operator, shaped so others can fork it.

github.com/beckwith930-star/claude-agent-os

→ curl -fsSL https://raw.githubusercontent.com/beckwith930-star/claude-agent-os/main/install.sh | bash
