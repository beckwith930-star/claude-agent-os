# LinkedIn carousel — claude-agent-os

5 frames, 1080 x 1350 each. Visual language: Linear-style flat geometric, near-black background (#0B0E14), one accent color (#E2FF5C) used sparingly. System-ui or monospace fonts only. No 3D, no isometric scenes, no stock illustration, no emoji in image copy.

---

## Frame 1 — Identity

- **Title:** The persistent layer for Claude Code.
- **Body:** Three always-on agents. Two safety hooks. One memory file. MIT licensed.
- **Visual motif:** A single horizontal line dividing the frame into thirds. Upper third holds the title in tight kerning. Lower third holds the body in monospace. One small accent-color square sits at the line's midpoint — the only color in the frame.
- **Designer note:** Cursor-style direct identity claim. Resist the urge to add a logo lockup or a sub-tagline; the line and the square carry the composition.

---

## Frame 2 — Problem

- **Title:** Every Claude Code session starts at zero.
- **Body:** You re-explain who you are, what you're building, and yesterday's decisions. The chat window holds the state. The chat window is disposable.
- **Visual motif:** A horizontal row of seven identical small squares, evenly spaced. The leftmost square is filled in accent color; the other six are outline-only. Reads as "session 1, then six blanks."
- **Designer note:** The metaphor is loss across sessions. Keep the squares uniform — no animation, no fade gradient. Cold geometric repetition is the point.

---

## Frame 3 — Architecture

- **Title:** Three agents. Three cadences.
- **Body:** Reply Handler — every 30 min. Calendar Booking — every 15 min. Morning Brief — Mon–Fri 7AM.
- **Visual motif:** Three horizontal bars stacked vertically, left-aligned, each labeled with its agent name on the left and its cadence on the right in monospace. Bar widths differ — shortest is Calendar (15), longest is Morning Brief (the weekly anchor). Bars use the accent color at 40% opacity; labels are white.
- **Designer note:** Treat this like a Gantt chart with the dates stripped. The bar-length ratio communicates cadence without a chart axis.

---

## Frame 4 — Hook layer

- **Title:** Safety as architecture, not a setting.
- **Body:** Pre-tool-use hook refuses destructive shell commands before they run. Post-tool-use hook routes every event to logs and memory.
- **Visual motif:** Two horizontal rectangles, one above the other, with a narrow gap between them. Between the rectangles, a small accent-color diamond sits centered — the tool call passing through. Above and below rectangles are labeled "pre-tool-use" and "post-tool-use" in monospace.
- **Designer note:** The unsexy frame. The diamond is the only ornament — no shield icons, no lock icons, no checkmarks. The geometry is the argument.

---

## Frame 5 — Install

- **Title:** Install in 60 seconds.
- **Body:** curl -fsSL https://raw.githubusercontent.com/beckwith930-star/claude-agent-os/main/install.sh | bash
- **Visual motif:** Full-frame monospace block with the curl command set in white on the near-black background. A single accent-color `→` arrow sits in the upper-left corner. Repo URL `github.com/beckwith930-star/claude-agent-os` runs along the bottom edge in smaller monospace.
- **Designer note:** Vercel-style install card. The command IS the visual — do not wrap it in a fake terminal chrome or add a copy-to-clipboard icon. One line, one arrow, one URL.
