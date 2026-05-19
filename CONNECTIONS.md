# CONNECTIONS.md — Auth Boundary (template)

Read at the start of every session. The router enforces these boundaries before any Chrome, Gmail, GitHub, or CRM action. Append-only history below the boundary table.

## Identity table

| Surface | Allowed | Forbidden | Notes |
|---|---|---|---|
| Chrome profile | `<YOUR_CHROME_DEVICE_ID>` | `<DAYJOB_CHROME_DEVICE_ID>`, `<PERSONAL_CHROME_DEVICE_ID>` | Verify before any browser action |
| Gmail account | `<YOUR_EMAIL>` | `<DAYJOB_EMAIL>`, `<PERSONAL_EMAIL>` | MCP server name: `gmail-<NS>` |
| GitHub | `<YOUR_GITHUB>` | (anything not yours) | Push only after confirmation |
| CRM | (your tenant) | (employer tenant) | Drafts only — never auto-execute destructive writes |

## Enforcement rules

1. If a tool would route to a forbidden surface, **HALT** and re-prompt for the correct account.
2. The pre-tool-use hook (`hooks/pre-tool-use/block-dangerous-commands.js`) is the last line of defense — never disable it.
3. Drafts-only is non-negotiable for any outbound action. The human pulls every send trigger.

## History

*(Append dated entries below as boundaries change — e.g., adding a new account, rotating an OAuth token, deprecating a forbidden surface. Never edit prior entries.)*

---

### YYYY-MM-DD — Initial setup

Replace with first real entry.
