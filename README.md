# ErpNext-For-chat-BOT — AI Accountant for ERPNext

A chat window inside ERPNext (bottom-right **💬 AI Accountant** button) that works like a human
accountant with access to your books. It is powered by Claude (Anthropic).

**What it can do**
- Answer questions from your real data: sales, purchases, who owes you, what you owe,
  profit & loss, balance sheet, trial balance, general ledger, gross profit…
- Prepare **draft** Sales/Purchase Invoices, Journal Entries, Payment Entries, Quotations,
  Orders, Customers, Suppliers and Items. A human always reviews and submits them.

**Safety**
- Every lookup runs as the logged-in user, with that user's ERPNext permissions.
- It can never submit, cancel or delete a document.
- Only users with *System Manager*, *Accounts Manager* or *Accounts User* see the chat.
- The API key is stored encrypted in **AI Accountant Settings**.

## Code layout

| File | What it is |
|---|---|
| `ai_accountant/agent.py` | The Claude loop and the accountant's instructions (system prompt) |
| `ai_accountant/tools.py` | The tools Claude may use (search, read, reports, create draft) |
| `ai_accountant/api.py` | The endpoints the chat window calls |
| `ai_accountant/public/js/ai_accountant.js` | The chat window |
| `ai_accountant/ai_accountant/doctype/ai_accountant_settings` | Settings page (API key, model, effort, extra instructions) |
| `docker/` | Image + compose override to run ERPNext with this app |

## Run it (Mac or Windows, with Docker Desktop)

```bash
# 1. The official ERPNext Docker setup (once)
git clone --depth 1 https://github.com/frappe/frappe_docker.git erpnext-docker

# 2. This app
git clone https://github.com/aliiherzi/ErpNext-For-chat-BOT.git
cd ErpNext-For-chat-BOT

# 3. Build the images (ERPNext + HRMS base, then this app on top) and start everything
docker build -f docker/hrms/Containerfile -t erpnext-hrms:v16.60.0 docker/hrms
docker build --build-arg ERPNEXT_IMAGE=erpnext-hrms:v16.60.0 -f docker/Dockerfile -t erpnext-ai:latest .
docker compose -p erpnext -f ../erpnext-docker/pwd.yml -f docker/compose.ai.yml -f docker/compose.second-site.yml up -d

# 4. First time only: install the app on the site
docker exec erpnext-backend-1 bench --site frontend install-app ai_accountant
```

Open http://localhost:8080 (first login: `Administrator` / `admin`), then go to
**AI Accountant Settings** (http://localhost:8080/app/ai-accountant-settings), paste your
Anthropic API key from https://console.anthropic.com, and save.

### Second site on http://localhost:8081
`docker/compose.second-site.yml` adds a second entrance for a site restored from a backup
(`FRAPPE_SITE_NAME_HEADER` = that site's name). Create and restore it with
`bench new-site <name> ... --install-app erpnext --install-app hrms`, then
`bench --site <name> restore <database.sql.gz> --with-public-files <files.tar> --with-private-files <private-files.tar>`,
copy the backup's `encryption_key` with `bench --site <name> set-config encryption_key ...`, and run `bench --site <name> migrate`.

### After changing the code

```bash
docker build --build-arg ERPNEXT_IMAGE=erpnext-hrms:v16.60.0 -f docker/Dockerfile -t erpnext-ai:latest .
docker compose -p erpnext -f ../erpnext-docker/pwd.yml -f docker/compose.ai.yml -f docker/compose.second-site.yml up -d
docker exec erpnext-backend-1 bench --site frontend migrate   # only if you changed a DocType
```

Then hard-refresh the browser (Cmd/Ctrl+Shift+R).

## Customizing the accountant

- **Change how it behaves:** edit `SYSTEM_PROMPT` in `ai_accountant/agent.py`, or, without
  rebuilding, write rules in *Extra Instructions* on the settings page.
- **Add a skill:** add an entry to `TOOLS` and a function to `_HANDLERS` in `ai_accountant/tools.py`.
- **Allow drafting more document types:** add them to `DRAFTABLE_DOCTYPES`.
