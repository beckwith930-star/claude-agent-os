# Setting up secrets/

The `~/.agent-os/secrets/` directory holds OAuth credentials and API keys. It is created with `700` perms by `install.sh` and is **gitignored** — the secrets themselves never ship.

You need to manually wire each integration. None of them are required to run claude-agent-os — but the always-on agents (reply-fetcher, booking-fetcher, morning-brief) won't be useful until at least Gmail OAuth is set up.

## 1. Gmail OAuth — required for reply/booking/brief agents

The three always-on agents read your Gmail inbox and write Gmail drafts via the Gmail API. You need:

- `~/.agent-os/secrets/gmail-credentials.json` — your Google Cloud OAuth client credentials
- `~/.agent-os/secrets/gmail-oauth-keys.json` — the refresh tokens generated on first auth

### Steps

1. **Create a Google Cloud project** at https://console.cloud.google.com/
2. **Enable Gmail API** for the project.
3. **Create OAuth credentials**:
   - Type: Desktop app
   - Download the JSON, save as `~/.agent-os/secrets/gmail-credentials.json`
   - `chmod 600 ~/.agent-os/secrets/gmail-credentials.json`
4. **Run the first-auth flow** (each script does this on first run, or use a helper):
   ```bash
   python3 -c "
   from google_auth_oauthlib.flow import InstalledAppFlow
   SCOPES = ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.settings.basic']
   flow = InstalledAppFlow.from_client_secrets_file('$HOME/.agent-os/secrets/gmail-credentials.json', SCOPES)
   creds = flow.run_local_server(port=0)
   import json
   with open('$HOME/.agent-os/secrets/gmail-oauth-keys.json', 'w') as f:
       f.write(creds.to_json())
   import os; os.chmod('$HOME/.agent-os/secrets/gmail-oauth-keys.json', 0o600)
   print('✓ saved')
   "
   ```
5. **Test:** `python3 ~/.agent-os/scripts/morning-brief.py` should now drop a draft to your inbox.

## 2. Hunter.io API key — optional, for email verification

If you want the outbound layer to verify email addresses before sending, drop your Hunter.io API key at `~/.agent-os/secrets/hunter-api-key.txt` (chmod 600). The free tier (75 searches + 100 verifications/month) is enough for one operator.

Without it, the OS still works — outbound drafts use pattern-guess emails and rely on the reply-fetcher to catch bounces.

## 3. Python deps

```bash
pip3 install --user google-auth google-auth-oauthlib google-api-python-client
```

## Verification

```bash
python3 ~/.agent-os/scripts/os-health.py
```

Should return `ALL GREEN`. If secrets aren't wired yet, you'll see failures on the auth-boundary section — that's expected until step 1 is complete.
