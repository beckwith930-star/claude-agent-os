Claude Code is great in a single session and forgets you exist the moment you close the window.

That gap — between a powerful chat tool and an actual operating layer — is what claude-agent-os fills. Open-sourcing it today.

It's a directory that sits at `~/.agent-os/` and turns Claude Code into something that runs whether you're at the keyboard or not. Three pieces do most of the work:

— A routing brain (`CLAUDE.md`) that maps intent to the right skill, persona, or agent. No more re-explaining your stack every session.

— Three always-on agents wired to launchd. A reply handler classifies inbox replies every 30 minutes and drafts responses. A calendar agent watches for new bookings every 15 minutes and writes prep docs. A morning brief lands in your inbox Mon–Fri at 7 AM with the top-3 things to do that day.

— A hook layer that blocks dangerous commands before they run and auto-stages git changes after. Safety isn't a feature you remember to use; it's enforced.

What it is: a persistence pattern for solo operators and small teams who already live in Claude Code and want one source of truth across sessions.

What it isn't: a hosted SaaS, an agent framework, or a replacement for Claude Code itself. It runs on your machine, reads your files, writes drafts you approve.

Built for one operator. Sharable to many.

Clone, run the install script, you're up in 60 seconds.

→ github.com/beckwith930-star/claude-agent-os
