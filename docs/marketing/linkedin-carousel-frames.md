# LinkedIn carousel — claude-agent-os launch

Five frames, 1080x1350 each. Palette: dark navy `#0a1730` background, cyan `#00d4ff` accent (sparing), warm white `#f4f4f0` text. Monospace where it reads as code (`ui-monospace` / `SFMono-Regular` / `Menlo`); clean sans (system-ui) for body. No emojis. No exclamation points.

A single thin cyan rule runs across the top of every frame at y≈100 — visual continuity. Slide number `01 / 05` etc. lives in the top-right corner in 14pt mono at 50% opacity. `github.com/beckwith930-star/claude-agent-os` runs along the bottom in 13pt mono on every frame.

---

## Frame 1 — Title

**Layout:** Centered. Lots of negative space.

**Title (top third, 72pt, warm white):**
`what is claude-agent-os?`

**Subtitle (below, 28pt, 80% opacity):**
A persistent operating layer for Claude Code.

**Visual element (bottom third):** ASCII directory tree, 18pt monospace, cyan-tinted, left-aligned, centered horizontally as a block:

```
~/.agent-os/
├── CLAUDE.md
├── MEMORY.md
├── agents/
├── skills/
├── hooks/
└── scripts/
```

**Footer line:** `open source · MIT · 2026`

---

## Frame 2 — The problem

**Title (32pt, warm white):**
`Chat sessions = amnesia.`

**Body (22pt, ~70% opacity, 3 short paragraphs separated by line breaks):**

You open Claude Code. You explain your stack, your voice, your last decision, your three open threads.

You close the tab. Tomorrow, you do it again.

Multiply by 200 working days a year.

**Visual element (right side or bottom):** Two terminal windows side-by-side, identical contents, both showing `$ claude` followed by `> who am I again?`. The repetition is the joke.

**Bottom line (16pt mono, cyan):**
`# the tool is powerful. the session is disposable.`

---

## Frame 3 — The architecture

**Title (32pt, warm white):**
`Three always-on agents.`

**Body (20pt, intro line):**
Wired to launchd. Runs whether you're at the keyboard or not.

**Visual element — a three-row table, monospace, generous row spacing:**

```
reply-handler      every 30m       classify inbox · draft replies
calendar-booking   every 15m       watch new bookings · write prep
morning-brief      Mon–Fri 7AM     top-3 priorities, one email
```

Row dividers are 1px cyan at 20% opacity. Cadence column is highlighted in cyan.

**Bottom line (16pt mono, 70% opacity):**
`# all output lands as drafts. you pull every send trigger.`

---

## Frame 4 — The hook layer

**Title (32pt, warm white):**
`Safety isn't a feature. It's enforced.`

**Body (22pt, two short paragraphs):**

A pre-tool-use hook intercepts every command before Claude runs it. Dangerous shell, force-pushes, writes outside the scope — blocked at the gate.

A post-tool-use hook auto-stages git changes so nothing edits silently. You see every diff.

**Visual element (center):** A schematic — a Claude shape on the left, a hook gate (cyan bracket `[ ]`) in the middle, the filesystem on the right. Arrows pass through the bracket. One arrow is red and blocked at the bracket; a small label reads `rm -rf ~` crossed out.

**Bottom line (16pt mono):**
`# pre-tool-use · post-tool-use · directory-scoped`

---

## Frame 5 — 60-second install

**Title (44pt, warm white, centered):**
`Clone. Run install.sh. Done.`

**Body (24pt, centered):**
60 seconds to a persistent Claude Code layer.

**Visual element — a code block, 22pt monospace, cyan prompt characters:**

```
$ git clone github.com/beckwith930-star/claude-agent-os ~/.agent-os
$ cd ~/.agent-os && ./install.sh
$ claude
```

Below the code block, in 16pt mono, 70% opacity:
`# launchd agents installed · hooks registered · routing brain live`

**CTA line (28pt, cyan, centered, bottom-quarter):**
`→ github.com/beckwith930-star/claude-agent-os`

**Footer (16pt, 60% opacity):**
Built for one operator. Sharable to many. MIT.
