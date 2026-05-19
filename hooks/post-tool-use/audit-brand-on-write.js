#!/usr/bin/env node
/**
 * Post-tool-use sub-hook — run brand-auditor when BRAND.md is written.
 *
 * Fires `scripts/audit-brand.py` whenever a Write/Edit tool touches
 * ~/.agent-os/BRAND.md. The audit output goes to stdout so Claude (and
 * the user, in a Claude Code session) see it immediately.
 *
 * Spec: ~/.agent-os/agents/brand-auditor.md
 * Loaded by: ~/.agent-os/hooks/post-tool-use/dispatcher.js
 */

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const AGENT_OS_ROOT = path.resolve(process.env.HOME, '.agent-os');
const BRAND_MD = path.join(AGENT_OS_ROOT, 'BRAND.md');
const AUDIT_SCRIPT = path.join(AGENT_OS_ROOT, 'scripts', 'audit-brand.py');
const ERR_LOG = path.join(AGENT_OS_ROOT, '.hook-errors.log');

function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

function isWriteTool(toolName) {
  return ['Write', 'Edit', 'MultiEdit', 'NotebookEdit'].includes(toolName);
}

function logError(message) {
  try {
    fs.appendFileSync(
      ERR_LOG,
      `[${new Date().toISOString()}] audit-brand-on-write: ${message}\n`
    );
  } catch {
    // swallow
  }
}

function main() {
  let payload;
  try {
    payload = JSON.parse(readStdin());
  } catch {
    return; // malformed payload — silently exit
  }

  const tool = payload.tool_name || payload.tool;
  if (!isWriteTool(tool)) return;

  const filePath =
    payload.tool_args?.file_path ||
    payload.tool_args?.path ||
    payload.file_path ||
    payload.path;
  if (!filePath) return;

  let resolved;
  try {
    resolved = path.resolve(filePath);
  } catch {
    return;
  }
  if (resolved !== BRAND_MD) return;

  if (!fs.existsSync(AUDIT_SCRIPT)) {
    logError(`audit script missing: ${AUDIT_SCRIPT}`);
    return;
  }

  try {
    const result = spawnSync('python3', [AUDIT_SCRIPT], {
      stdio: ['ignore', 'pipe', 'pipe'],
      timeout: 8000,
    });

    const stdout = (result.stdout || Buffer.from('')).toString();
    const stderr = (result.stderr || Buffer.from('')).toString();
    const exitCode = result.status;

    console.log('');
    console.log('━━━ BRAND.md edit detected · brand-auditor fired ━━━');
    if (stdout) console.log(stdout.trimEnd());
    if (stderr) console.error(stderr.trimEnd());
    if (exitCode === 0) {
      console.log('━━━ ✓ audit clean (12 of 12 sections present) ━━━');
    } else if (exitCode === 1) {
      console.log('━━━ ⚠ audit found gaps — see above for routing ━━━');
    } else {
      console.log(`━━━ audit exited ${exitCode} (unexpected) ━━━`);
    }
    console.log('');
  } catch (err) {
    logError(err.message || String(err));
  }
}

main();
process.exit(0);
