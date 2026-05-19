#!/usr/bin/env bash
# install.sh — bootstrap claude-agent-os into ~/.agent-os/
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/beckwith930-star/claude-agent-os/main/install.sh | bash
#   OR after cloning:
#   ./install.sh
#
# Requires: macOS, python3, git, gh (optional, for plugin stats)

set -euo pipefail

REPO_URL="https://github.com/beckwith930-star/claude-agent-os.git"
AGENT_OS="${HOME}/.agent-os"
LA="${HOME}/Library/LaunchAgents"

GREEN="\033[92m"; YELLOW="\033[93m"; RED="\033[91m"; BOLD="\033[1m"; RESET="\033[0m"

ok()   { echo -e "  ${GREEN}✓${RESET} $1"; }
warn() { echo -e "  ${YELLOW}⚠${RESET} $1"; }
fail() { echo -e "  ${RED}✗${RESET} $1"; exit 1; }
sect() { echo -e "\n${BOLD}$1${RESET}"; }

sect "claude-agent-os installer"

# ─── 1. Prereqs ──────────────────────────────────────────────
command -v python3 >/dev/null 2>&1 || fail "python3 not found — install via brew or python.org"
command -v git     >/dev/null 2>&1 || fail "git not found"
ok "python3 + git available"

# ─── 2. Clone or update ──────────────────────────────────────
sect "Cloning to ${AGENT_OS}"
if [ -d "${AGENT_OS}/.git" ]; then
  warn "${AGENT_OS} already a git repo — pulling latest"
  (cd "${AGENT_OS}" && git pull --ff-only)
elif [ -d "${AGENT_OS}" ]; then
  fail "${AGENT_OS} exists but isn't a git repo. Back it up and remove, then re-run."
else
  git clone "${REPO_URL}" "${AGENT_OS}"
  ok "cloned"
fi

# ─── 3. Pick a namespace ─────────────────────────────────────
sect "Choose a namespace"
echo "  The namespace (NS) is used for Gmail labels (<NS>/reply, <NS>/booking, <NS>/morning-brief),"
echo "  launchd job labels (io.<NS>.morning-brief), and the gmail-mcp server name (gmail-<NS>)."
echo "  Suggestions: your venture short-name, your initials, your handle. Lowercase, alphanumeric + hyphen."
read -r -p "  NS = " NS
[ -z "${NS}" ] && fail "namespace cannot be empty"
echo "${NS}" | grep -Eq '^[a-z0-9-]+$' || fail "namespace must be lowercase alphanumeric + hyphen"
ok "namespace = ${NS}"

# Replace <NS> across the tree (just the canonical doc + settings templates we shipped)
echo "  Replacing <NS> tokens in canonical docs + settings.json"
for f in "${AGENT_OS}/CLAUDE.md" "${AGENT_OS}/CONNECTIONS.md" "${AGENT_OS}/settings.json"; do
  [ -f "${f}" ] && sed -i '' "s|<NS>|${NS}|g" "${f}"
done

# ─── 4. Secrets dir ──────────────────────────────────────────
sect "Setting up ${AGENT_OS}/secrets/ (700 perms)"
mkdir -p "${AGENT_OS}/secrets"
chmod 700 "${AGENT_OS}/secrets"
ok "secrets/ created"
warn "Gmail OAuth + Hunter.io API key are NOT bundled — see docs/setup-secrets.md for the manual setup."

# ─── 5. Make scripts + hooks executable ──────────────────────
sect "Making scripts + hooks executable"
chmod +x "${AGENT_OS}/scripts/"*.py "${AGENT_OS}/scripts/"*.sh 2>/dev/null || true
chmod +x "${AGENT_OS}/hooks/"*/*.js 2>/dev/null || true
ok "scripts + hooks executable"

# ─── 6. Install launchd plists ───────────────────────────────
sect "Installing launchd plists (Mon–Fri 7AM brief + 15/30-min fetchers)"
mkdir -p "${LA}"
USERNAME="$(whoami)"
for tpl in "${AGENT_OS}/launchd/"*.plist.template; do
  base="$(basename "${tpl}" .template)"
  out="${LA}/$(echo "${base}" | sed "s|NS|${NS}|g")"
  sed -e "s|{{NS}}|${NS}|g" -e "s|{{HOME}}|${HOME}|g" -e "s|{{USERNAME}}|${USERNAME}|g" "${tpl}" > "${out}"
  # Try load — non-fatal if already loaded
  launchctl unload "${out}" 2>/dev/null || true
  launchctl load   "${out}" && ok "loaded $(basename "${out}")" || warn "could not load $(basename "${out}") (will retry on next login)"
done

# ─── 7. Health check ─────────────────────────────────────────
sect "Running health check"
python3 "${AGENT_OS}/scripts/os-health.py" || warn "Some checks failed — expected on first install (Gmail OAuth not wired yet). Re-run after secrets/ is populated."

# ─── 8. Next steps ───────────────────────────────────────────
sect "Next steps"
cat <<EOF

  1. Edit ${AGENT_OS}/BRAND.md — fill the 12 canonical sections.
  2. Edit ${AGENT_OS}/SOUL.md — describe your voice.
  3. Set up Gmail OAuth: see ${AGENT_OS}/docs/setup-secrets.md
  4. (Optional) Add Hunter.io API key to ${AGENT_OS}/secrets/hunter-api-key.txt (chmod 600)
  5. Open a Claude Code session in any directory and try:
       /morning-brief       — generate today's brief on-demand
       /handle-replies      — process inbox replies
       /process-bookings    — generate prep docs for new bookings
       /audit-brand         — check BRAND.md for gaps

  Repo: ${REPO_URL}
EOF

echo -e "\n${GREEN}${BOLD}✓ install complete${RESET}\n"
