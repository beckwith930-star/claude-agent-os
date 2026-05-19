#!/bin/bash
# monthly-audit.sh — wrapper that runs the brand-doc audit + logs to MEMORY.md.
# Invoked by launchd job io.<NS>.brand-audit on the 1st of each month.
#
# Spec: ~/.agent-os/agents/brand-auditor.md
# Loaded by: ~/Library/LaunchAgents/io.<NS>.brand-audit.plist

set -u
LANG="en_US.UTF-8"
LC_ALL="en_US.UTF-8"

AGENT_OS="$HOME/.agent-os"
AUDIT="$AGENT_OS/scripts/audit-brand.py"
MEMORY="$AGENT_OS/MEMORY.md"
TODAY=$(date +"%Y-%m-%d")
BRAND_SIZE=$(stat -f%z "$AGENT_OS/BRAND.md" 2>/dev/null || echo "0")

AUDIT_OUTPUT=$(/usr/bin/env python3 "$AUDIT" 2>&1)
EXIT_CODE=$?

case $EXIT_CODE in
  0)
    cat >> "$MEMORY" <<ENTRY

## [$TODAY] Monthly brand-doc audit — clean (launchd)
**Result:** \`scripts/audit-brand.py\` exit 0. All 12 canonical sections present and have content. Source: ~/.agent-os/BRAND.md ($BRAND_SIZE bytes). Fired by launchd job \`io.<NS>.brand-audit\`.
**Next step:** Next audit fires 1st of next month per launchd. No action required.
ENTRY
    ;;
  1)
    cat >> "$MEMORY" <<ENTRY

## [$TODAY] Monthly brand-doc audit — gaps flagged (launchd)
**Result:** \`scripts/audit-brand.py\` exit 1. Gaps found in BRAND.md. Audit output below.

\`\`\`
$AUDIT_OUTPUT
\`\`\`

**Next step:** Invoke the recommended persona(s) and commit drafted content to BRAND.md. Re-run \`python3 scripts/audit-brand.py\` until exit 0.
ENTRY
    # macOS notification — quiet failure if osascript not available
    /usr/bin/osascript -e 'display notification "Gaps found in BRAND.md — see MEMORY.md" with title "<VENTURE> Brand Audit" sound name "Tink"' 2>/dev/null || true
    ;;
  *)
    cat >> "$MEMORY" <<ENTRY

## [$TODAY] Monthly brand-doc audit — FAILED (launchd)
**Result:** \`scripts/audit-brand.py\` exit $EXIT_CODE (unexpected). Output:

\`\`\`
$AUDIT_OUTPUT
\`\`\`

**Next step:** Investigate manually. Check BRAND.md path resolution in the audit script and that python3 is on PATH for launchd's environment.
ENTRY
    /usr/bin/osascript -e 'display notification "Brand audit FAILED — see MEMORY.md" with title "<VENTURE> Brand Audit" sound name "Sosumi"' 2>/dev/null || true
    ;;
esac

exit 0
