#!/usr/bin/env node
/**
 * Post-tool-use hook — auto-stage newly-created files to git.
 *
 * Claude Code invokes this hook after a successful tool call.
 * If the tool was a file write to a path inside ~/.agent-os/, stage it.
 *
 * Configure in ~/.agent-os/settings.json under hooks.post_tool_use.
 */

const fs = require('fs');
const { execSync } = require('child_process');
const path = require('path');

const STDIN_FD = 0;
const AGENT_OS_ROOT = path.resolve(process.env.HOME, '.agent-os');

function readStdin() {
  return fs.readFileSync(STDIN_FD, 'utf8');
}

function isInsideAgentOS(p) {
  if (!p) return false;
  const abs = path.resolve(p);
  return abs.startsWith(AGENT_OS_ROOT + path.sep) || abs === AGENT_OS_ROOT;
}

function isWriteTool(toolName) {
  return ['Write', 'Edit', 'MultiEdit', 'NotebookEdit'].includes(toolName);
}

function main() {
  let payload;
  try {
    payload = JSON.parse(readStdin());
  } catch {
    return; // malformed — silently exit
  }

  const tool = payload.tool_name || payload.tool;
  if (!isWriteTool(tool)) return;

  const filePath = payload.tool_args?.file_path || payload.tool_args?.path || payload.file_path;
  if (!filePath || !isInsideAgentOS(filePath)) return;

  try {
    const isGitRepo = fs.existsSync(path.join(AGENT_OS_ROOT, '.git'));
    if (!isGitRepo) return;

    execSync(`git -C "${AGENT_OS_ROOT}" add "${filePath}"`, { stdio: 'pipe' });

    // Optional: log to a daily journal
    const today = new Date().toISOString().split('T')[0];
    const journalPath = path.join(AGENT_OS_ROOT, 'memory', 'obsidian-vault', 'daily', `${today}.md`);
    const journalDir = path.dirname(journalPath);

    if (!fs.existsSync(journalDir)) fs.mkdirSync(journalDir, { recursive: true });

    const journalLine = `- [${new Date().toISOString()}] auto-staged: \`${path.relative(AGENT_OS_ROOT, filePath)}\`\n`;
    fs.appendFileSync(journalPath, journalLine);
  } catch (err) {
    // Hook failures should never break Claude Code — log silently to a hook error file
    const errLog = path.join(AGENT_OS_ROOT, '.hook-errors.log');
    fs.appendFileSync(errLog, `[${new Date().toISOString()}] auto-stage error: ${err.message}\n`);
  }
}

main();
process.exit(0);
