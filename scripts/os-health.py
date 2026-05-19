#!/usr/bin/env python3
"""
os-health.py — verify every component of the <VENTURE> Agent OS is wired up.

Checks: canonical docs · settings.json hook references · user-level bootstrap ·
hook executability · script executability · brand-doc audit pass · launchd job
registered · auth boundary file perms · scheduled tasks present.

Run on demand:
  python3 ~/.agent-os/scripts/os-health.py

Exit 0 if all green; 1 if any check failed; warnings don't fail the run.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
AGENT_OS = HOME / ".agent-os"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg):
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg):
    print(f"  {RED}✗{RESET} {msg}")


def warn(msg):
    print(f"  {YELLOW}⚠{RESET} {msg}")


def section(name):
    print(f"\n{BOLD}{name}{RESET}")


def main():
    failures = 0
    warnings = 0
    total = 0

    print(f"{BOLD}=== <VENTURE> Agent OS — Health Check ==={RESET}")

    # ─── Canonical docs ──────────────────────────────────────────────
    section("Canonical docs")
    for doc in ["BRAND.md", "SOUL.md", "MEMORY.md", "CLAUDE.md", "CONNECTIONS.md", "settings.json"]:
        total += 1
        path = AGENT_OS / doc
        if path.exists() and path.stat().st_size > 0:
            ok(f"{doc} present ({path.stat().st_size:,} bytes)")
        else:
            fail(f"{doc} MISSING or empty at {path}")
            failures += 1

    # ─── settings.json hook references ───────────────────────────────
    section("settings.json hook references")
    try:
        settings = json.loads((AGENT_OS / "settings.json").read_text())
        for k, v in (settings.get("hooks") or {}).items():
            total += 1
            p = AGENT_OS / v
            if p.exists() and os.access(p, os.X_OK):
                ok(f"hooks.{k} → {v}")
            elif p.exists():
                fail(f"hooks.{k} → {v} present but NOT executable (run chmod +x)")
                failures += 1
            else:
                fail(f"hooks.{k} → {v} MISSING")
                failures += 1
    except Exception as e:  # noqa: BLE001
        total += 1
        fail(f"settings.json parse error: {e}")
        failures += 1

    # ─── Directory-scoped bootstrap ──────────────────────────────────
    # User-level CLAUDE.md is INTENTIONALLY ABSENT — it would mix <VENTURE>
    # context into Work day-job sessions. The OS engages only when
    # cwd is inside a <VENTURE> work tree.
    section("Directory-scoped bootstrap (<VENTURE> engages only in venture dirs)")

    total += 1
    user_claude = HOME / ".claude" / "CLAUDE.md"
    if user_claude.exists():
        fail(
            f"~/.claude/CLAUDE.md EXISTS — this leaks <VENTURE> OS into every session "
            "including Work work. DELETE this file."
        )
        failures += 1
    else:
        ok("~/.claude/CLAUDE.md absent (correct — no user-level mixing)")

    total += 1
    venture_bootstrap = HOME / "Documents" / "AgentBeckVenture" / "CLAUDE.md"
    if venture_bootstrap.exists() and "agent-os" in venture_bootstrap.read_text().lower():
        ok(f"~/Documents/AgentBeckVenture/CLAUDE.md bootstraps Agent OS in venture tree")
    else:
        fail(
            f"~/Documents/AgentBeckVenture/CLAUDE.md missing or doesn't reference agent-os — "
            "<VENTURE> work sessions won't auto-engage the OS"
        )
        failures += 1

    total += 1
    brain_optout = HOME / "Documents" / "Work" / "CLAUDE.md"
    if brain_optout.exists():
        text = brain_optout.read_text().lower()
        if "do not load" in text and "agent-os" in text:
            ok(f"Work opt-out CLAUDE.md present (belt-and-suspenders)")
        else:
            warn(f"Work dir has CLAUDE.md but doesn't explicitly opt out of Agent OS")
            warnings += 1
    else:
        warn(
            f"~/Documents/Work/CLAUDE.md missing — "
            "recommended as belt-and-suspenders opt-out for the day-job tree"
        )
        warnings += 1

    # ─── Sub-hooks ───────────────────────────────────────────────────
    section("Sub-hooks")
    hooks_dir = AGENT_OS / "hooks"
    if hooks_dir.exists():
        for js in sorted(hooks_dir.glob("*/*.js")):
            total += 1
            rel = js.relative_to(AGENT_OS)
            if os.access(js, os.X_OK):
                ok(f"{rel} executable")
            else:
                fail(f"{rel} NOT executable")
                failures += 1

    # ─── Scripts ─────────────────────────────────────────────────────
    section("Scripts")
    scripts_dir = AGENT_OS / "scripts"
    if scripts_dir.exists():
        for s in sorted(scripts_dir.glob("*")):
            if s.is_file():
                total += 1
                if os.access(s, os.X_OK):
                    ok(f"scripts/{s.name} executable")
                else:
                    fail(f"scripts/{s.name} NOT executable")
                    failures += 1

    # ─── Brand-doc audit ─────────────────────────────────────────────
    section("Brand-doc audit (should be 12/12)")
    total += 1
    audit_script = AGENT_OS / "scripts" / "audit-brand.py"
    if audit_script.exists():
        result = subprocess.run(
            ["python3", str(audit_script)], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            ok("BRAND.md audit clean (12 of 12 canonical sections)")
        else:
            fail(f"BRAND.md audit FAILED (exit {result.returncode}) — run audit-brand.py for details")
            failures += 1
    else:
        fail("scripts/audit-brand.py missing")
        failures += 1

    # ─── Launchd (true always-on) ────────────────────────────────────
    section("Launchd jobs (true always-on, fires when Claude Code is closed)")
    for plist_name, label in [
        ("io.<NS>.brand-audit.plist",     "io.<NS>.brand-audit"),
        ("io.<NS>.reply-fetcher.plist",   "io.<NS>.reply-fetcher"),
        ("io.<NS>.booking-fetcher.plist", "io.<NS>.booking-fetcher"),
        ("io.<NS>.morning-brief.plist",   "io.<NS>.morning-brief"),
    ]:
        total += 1
        plist = HOME / "Library" / "LaunchAgents" / plist_name
        if plist.exists():
            ok(f"plist present at ~/Library/LaunchAgents/{plist_name}")
            total += 1
            try:
                loaded = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=5)
                if label in loaded.stdout:
                    ok(f"{label} registered with launchctl")
                else:
                    fail(
                        f"{label} plist exists but NOT loaded — "
                        f"run `launchctl load ~/Library/LaunchAgents/{plist_name}`"
                    )
                    failures += 1
            except Exception as e:  # noqa: BLE001
                warn(f"could not check launchctl: {e}")
                warnings += 1
        else:
            warn(f"no plist at ~/Library/LaunchAgents/{plist_name}")
            warnings += 1

    # Reply handler artifacts
    total += 1
    reply_handler = AGENT_OS / "agents" / "reply-handler.md"
    if reply_handler.exists():
        ok("agents/reply-handler.md present (reply handler agent spec)")
    else:
        fail("agents/reply-handler.md MISSING — reply handler can't route")
        failures += 1

    # Calendar booking artifacts
    total += 1
    booking_handler = AGENT_OS / "agents" / "calendar-booking.md"
    if booking_handler.exists():
        ok("agents/calendar-booking.md present (booking agent spec)")
    else:
        fail("agents/calendar-booking.md MISSING — booking processor can't route")
        failures += 1

    total += 1
    tracking = AGENT_OS / "outbox" / "sent-tracking.json"
    if tracking.exists():
        try:
            t = json.loads(tracking.read_text())
            n = len(t.get("recipients", []))
            ok(f"outbox/sent-tracking.json present ({n} recipients tracked)")
        except Exception as e:
            fail(f"outbox/sent-tracking.json present but unreadable: {e}")
            failures += 1
    else:
        warn("outbox/sent-tracking.json missing — reply fetcher will no-op")
        warnings += 1

    # ─── Claude Code scheduled tasks ─────────────────────────────────
    section("Claude Code scheduled tasks (fire only when app is open)")
    total += 1
    sched_dir = HOME / ".claude" / "scheduled-tasks"
    if sched_dir.exists():
        tasks = [p.name for p in sched_dir.iterdir() if p.is_dir()]
        if "audit-brand-monthly" in tasks:
            ok(f"audit-brand-monthly registered ({len(tasks)} scheduled task(s) total)")
        else:
            warn("audit-brand-monthly missing from scheduled tasks")
            warnings += 1
    else:
        warn("~/.claude/scheduled-tasks/ does not exist")
        warnings += 1

    # ─── Auth boundary file perms ────────────────────────────────────
    section("Auth boundary — secrets directory + Gmail credentials")
    total += 1
    secrets = AGENT_OS / "secrets"
    if secrets.exists():
        mode = oct(secrets.stat().st_mode)[-3:]
        if mode == "700":
            ok(f"secrets/ exists with 700 perms")
        else:
            fail(f"secrets/ has loose perms ({mode}) — should be 700")
            failures += 1
    else:
        fail("secrets/ directory missing")
        failures += 1

    for cred in ["gmail-credentials.json", "gmail-oauth-keys.json"]:
        total += 1
        p = secrets / cred
        if p.exists():
            mode = oct(p.stat().st_mode)[-3:]
            if mode in ("600", "700"):
                ok(f"{cred} present with restrictive perms ({mode})")
            else:
                fail(f"{cred} has loose perms ({mode}) — should be 600")
                failures += 1
        else:
            fail(f"{cred} MISSING")
            failures += 1

    # Hunter.io key (optional — warn-not-fail if absent)
    total += 1
    hunter_key = secrets / "hunter-api-key.txt"
    if hunter_key.exists():
        mode = oct(hunter_key.stat().st_mode)[-3:]
        if mode in ("600", "700"):
            ok(f"hunter-api-key.txt present with restrictive perms ({mode})")
        else:
            fail(f"hunter-api-key.txt has loose perms ({mode}) — should be 600")
            failures += 1
    else:
        warn("hunter-api-key.txt absent — outbound drafts use pattern-guess only (no Hunter verification)")
        warnings += 1

    # ─── Summary ─────────────────────────────────────────────────────
    print(f"\n{BOLD}=== Summary ==={RESET}")
    if failures == 0 and warnings == 0:
        print(f"{GREEN}✓ ALL GREEN — {total} checks passed.{RESET}")
        return 0
    if failures == 0:
        print(f"{YELLOW}⚠ {warnings} warning(s), {total - warnings} clean. No failures.{RESET}")
        return 0
    print(
        f"{RED}✗ {failures} failure(s), {warnings} warning(s), "
        f"{total - failures - warnings} clean.{RESET}"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
