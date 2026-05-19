#!/usr/bin/env node
/**
 * Pre-tool-use hook — block dangerous commands before they execute.
 *
 * Claude Code invokes this hook before any tool call.
 * If the hook outputs `{ block: true, reason: "..." }`, the tool call is cancelled.
 *
 * Configure in ~/.agent-os/settings.json under hooks.pre_tool_use.
 */

const STDIN_FD = 0;
const fs = require('fs');

function readStdin() {
  return fs.readFileSync(STDIN_FD, 'utf8');
}

const DANGEROUS_PATTERNS = [
  // Filesystem
  { pattern: /\brm\s+-rf?\s+\/(?!\s*tmp)/, reason: 'rm -rf on root or non-/tmp path' },
  { pattern: /\brm\s+-rf?\s+~\s*$/, reason: 'rm -rf on home directory' },
  { pattern: /\bsudo\s+rm\b/, reason: 'sudo rm — destructive privileged delete' },

  // Git
  { pattern: /\bgit\s+push\s+(-f|--force)\b.*\b(main|master)\b/, reason: 'force-push to main/master' },
  { pattern: /\bgit\s+reset\s+--hard\s+(origin\/)?(main|master)/, reason: 'hard reset against main/master without confirmation' },
  { pattern: /\bgit\s+clean\s+-fdx?\b/, reason: 'git clean with force + remove untracked dirs' },

  // SQL
  { pattern: /\bDROP\s+(TABLE|DATABASE|SCHEMA)\b/i, reason: 'SQL DROP statement' },
  { pattern: /\bDELETE\s+FROM\s+\w+\s*(;|$)/i, reason: 'DELETE without WHERE clause' },
  { pattern: /\bUPDATE\s+\w+\s+SET\s+[^WHERE]*?(;|$)/i, reason: 'UPDATE without WHERE clause' },
  { pattern: /\bTRUNCATE\s+TABLE\b/i, reason: 'TRUNCATE — irreversible' },

  // Salesforce CLI
  { pattern: /\bsf\s+data\s+delete\b/, reason: 'Salesforce destructive delete via CLI' },
  { pattern: /\bsf\s+data\s+upsert\b.*--all/, reason: 'Salesforce bulk upsert with --all' },
  { pattern: /\bsf\s+apex\s+run\b.*Database\.(delete|hard.*delete)/, reason: 'Apex Database.delete called from CLI' },

  // Shell
  { pattern: /:\s*\(\s*\)\s*\{\s*:.*\|\s*:\s*&\s*\}\s*:/, reason: 'fork bomb' },
  { pattern: /\bmkfs\b/, reason: 'mkfs — disk format' },
  { pattern: /\bdd\b.*of=\/dev/, reason: 'dd write to device' },

  // Network
  { pattern: /\bcurl\b.*\|\s*(bash|sh|zsh)\b/, reason: 'curl piped to shell — install untrusted code' },
  { pattern: /\bwget\b.*\|\s*(bash|sh|zsh)\b/, reason: 'wget piped to shell' },
];

function check(input) {
  let payload;
  try {
    payload = JSON.parse(input);
  } catch {
    return { block: false }; // malformed input — let Claude Code handle
  }

  const command = payload.tool_args?.command || payload.command || '';
  if (!command) return { block: false };

  for (const { pattern, reason } of DANGEROUS_PATTERNS) {
    if (pattern.test(command)) {
      return {
        block: true,
        reason: `BLOCKED by pre-tool-use hook: ${reason}\nCommand: ${command}\nIf intentional, run it manually outside Claude Code.`,
      };
    }
  }

  return { block: false };
}

const input = readStdin();
const result = check(input);
process.stdout.write(JSON.stringify(result));
process.exit(0);
