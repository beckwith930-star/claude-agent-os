#!/usr/bin/env node
/**
 * Notification hook — send Slack notification when an agent needs human approval.
 *
 * Triggered by Claude Code when an agent completes a task that needs human
 * approval (e.g., outreach drafts awaiting send, SF writes awaiting confirm).
 *
 * Requires SLACK_WEBHOOK_URL environment variable.
 * Set in ~/.zshrc or ~/.bashrc:
 *   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T.../B.../X..."
 *
 * Configure in ~/.agent-os/settings.json under hooks.notification.
 */

const fs = require('fs');
const https = require('https');

const STDIN_FD = 0;

function readStdin() {
  return fs.readFileSync(STDIN_FD, 'utf8');
}

function postToSlack(webhook, payload) {
  return new Promise((resolve, reject) => {
    const url = new URL(webhook);
    const body = JSON.stringify(payload);
    const req = https.request({
      hostname: url.hostname,
      path: url.pathname + url.search,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
      },
    }, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => res.statusCode === 200 ? resolve(data) : reject(new Error(`Slack ${res.statusCode}: ${data}`)));
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

function buildPayload(input) {
  const agentName = input.agent || input.tool_name || 'unknown-agent';
  const action = input.action || input.event || 'task complete';
  const detail = input.detail || input.message || '';
  const url = input.review_url || input.gmail_drafts_url || '';

  return {
    text: `🔔 ${agentName}: ${action}`,
    blocks: [
      {
        type: 'section',
        text: { type: 'mrkdwn', text: `*${agentName}* — ${action}` },
      },
      ...(detail ? [{
        type: 'section',
        text: { type: 'mrkdwn', text: detail },
      }] : []),
      ...(url ? [{
        type: 'actions',
        elements: [{
          type: 'button',
          text: { type: 'plain_text', text: 'Review' },
          url,
          style: 'primary',
        }],
      }] : []),
      {
        type: 'context',
        elements: [{
          type: 'mrkdwn',
          text: `_${new Date().toISOString()}_`,
        }],
      },
    ],
  };
}

async function main() {
  const webhook = process.env.SLACK_WEBHOOK_URL;
  if (!webhook) {
    // No Slack configured — silent no-op
    return;
  }

  let input;
  try {
    input = JSON.parse(readStdin());
  } catch {
    return;
  }

  try {
    await postToSlack(webhook, buildPayload(input));
  } catch (err) {
    // Notification failures should never break Claude Code
    fs.appendFileSync(
      `${process.env.HOME}/.agent-os/.hook-errors.log`,
      `[${new Date().toISOString()}] notify-permission error: ${err.message}\n`
    );
  }
}

main().then(() => process.exit(0));
