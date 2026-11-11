# ERPNext for Chat BOT

The business ERP for **Chat BOT**, built on the shared ERPNext system in
[`aliiherzi/erpnext-system`](https://github.com/aliiherzi/erpnext-system), with the XAL Desk look.
It follows the steps in `prompts/new-erp-like-rays.md` from that repo.

This repo holds **only what is special to this business**. The Docker stack, images and prompts
stay in `erpnext-system`.

## Where it goes on your PC

```
C:\Users\hp\.claude\ErpNext System\        <- erpnext-system
  frappe_docker\                           <- Docker stack (pwd.yml)
  xal_desk\                                <- Xalfinance/xal-desk
  RAYS CLEANING\                           <- the finished example
  CHAT BOT\                                <- THIS repo
```

```powershell
cd "C:\Users\hp\.claude\ErpNext System"
git clone https://github.com/aliiherzi/ErpNext-For-chat-BOT.git "CHAT BOT"
```

Then add `/CHAT BOT/` to the `.gitignore` of `erpnext-system`, the same way `/RAYS CLEANING/` is listed.

## Folders

| Path | What goes there |
|---|---|
| `HANDOFF.md` | The answers to the business questions, then what was built, users, roles, open questions |
| `users/` | One Python script per user: roles, menu (`kit.menu`), home page (`kit.home`) |
| `scripts/` | Business-wide scripts: brand (`kit.brand`), roles, Overview pages (`kit.overview`) |
| `branding/` | Logo (square PNG) and other images |
| `LOCAL-PASSWORDS.txt` | Users' passwords. **On your PC only**, never committed |

Each script starts with a comment saying what was asked and the date, and can be run again
(it updates, it never makes duplicates). Run them inside the backend container:

```powershell
docker compose -p erpnext -f frappe_docker/pwd.yml exec backend bench --site <site> execute ...
```

## Rules
- Never change what Administrator sees.
- Never delete anything: hide or pause instead.
- No test records on the business site: use the demo site.
- Create users one by one and check each one.
