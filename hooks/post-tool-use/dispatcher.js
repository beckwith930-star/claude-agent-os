#!/usr/bin/env node
/**
 * Post-tool-use hook dispatcher.
 *
 * Claude Code points to a SINGLE hook file per phase. This dispatcher
 * runs every sub-hook in sequence, passing the same stdin payload to
 * each. Hooks are independent — a failure in one doesn't stop the rest.
 *
 * To add a new sub-hook:
 *   1. Drop the file in `hooks/post-tool-use/`
 *   2. Add its filename to SUB_HOOKS below
 *
 * Configure in `~/.agent-os/settings.json`:
 *   hooks.post_tool_use = "hooks/post-tool-use/dispatcher.js"
 */

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const SUB_HOOKS = [
  'auto-stage.js',          // git-stages new files inside ~/.agent-os/
  'audit-brand-on-write.js', // runs brand auditor if BRAND.md was touched
];

const AGENT_OS_ROOT = path.resolve(process.env.HOME, '.agent-os');
const ERR_LOG = path.join(AGENT_OS_ROOT, '.hook-errors.log');

function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

function logError(hookName, message) {
  try {
    fs.appendFileSync(
      ERR_LOG,
      `[${new Date().toISOString()}] dispatcher → ${hookName}: ${message}\n`
    );
  } catch {
    // last resort — swallow; we never block Claude Code on a hook error
  }
}

function main() {
  const payload = readStdin();
  const dir = __dirname;

  for (const hook of SUB_HOOKS) {
    const hookPath = path.join(dir, hook);
    if (!fs.existsSync(hookPath)) continue;
    try {
      const result = spawnSync('node', [hookPath], {
        input: payload,
        stdio: ['pipe', 'inherit', 'inherit'],
        timeout: 10000, // 10s per sub-hook — hooks should be fast
      });
      if (result.status !== 0 && result.status !== null) {
        logError(hook, `non-zero exit: ${result.status}`);
      }
      if (result.signal) {
        logError(hook, `killed by signal: ${result.signal}`);
      }
    } catch (err) {
      logError(hook, err.message || String(err));
    }
  }
}

main();
process.exit(0);
