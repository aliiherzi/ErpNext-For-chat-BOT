# XAL Accountant Bot: handoff

Everything decided and built so far, so the work can continue from any computer.
Last updated: 2026-11-11.

## 1. The idea

A chatbot inside ERPNext that works like an accountant. The owner or manager of a company may
not know how ERPNext works; they write what happened in plain words ("I sold a book for $1")
and the bot does the bookkeeping and answers questions about the accounts.

## 2. Decisions

| Topic | Decision |
|---|---|
| Where the chat is | A chat box inside ERPNext first. WhatsApp later, when confirmed (the existing `Xalfinance/erp-whatsapp` system can be the base). |
| Who it is for | XAL Finance first, then client companies. |
| Where ERPNext runs | Local PC (`localhost:8080`) and online on a Hostinger VPS (believed to be KVM 2 - check in the Hostinger panel). |
| Languages | English and Somali, text only. Voice was dropped for now. |
| Safety | The bot always shows a summary and waits for Confirm before saving anything. |
| Permissions | Every user keeps their own ERPNext permissions; the bot cannot do more than the user can. |
| The AI ("brain") | Replaceable in one settings page. Test with the free Gemma 4 on OpenRouter; for real books use Claude Haiku 5.5 (estimated ~$3/month for 50 invoices a day). |
| Own AI on own server | Not now: the VPS has no graphics card, so a self-hosted model would be slow and weak in Somali. The brain stays replaceable so this can change later. |
| First version | Sales invoice with PDF, payment received, customer balance, receivables, Profit and Loss. |

## 3. What is built (version 0.1)

The Frappe app `xal_chatbot` in this repository.

| Part | File | What it does |
|---|---|---|
| Chat box | `xal_chatbot/public/js/accountant_bot.js`, `css/accountant_bot.css` | Button at the bottom right of the desk, messages, Confirm / Cancel card, Open and PDF buttons. |
| Server methods | `xal_chatbot/api.py` | `get_boot`, `send`, `confirm`, `cancel`, `reset`. "yes / haa / no / maya" are handled by fixed rules, not by the AI. |
| Tools | `xal_chatbot/tools.py` | What the AI may do: find customer / item, payment methods, customer balance, receivables, Profit and Loss, invoice PDF, prepare sales invoice, prepare payment. |
| Saving | `xal_chatbot/actions.py` | Creates and submits the Sales Invoice / Payment Entry after Confirm, as the user, all or nothing. |
| Brains | `xal_chatbot/brain/` | `openai_compatible.py` (OpenRouter, Ollama, own server) and `claude.py` (Anthropic API). The accountant's instructions are in `brain/__init__.py`. |
| Settings | DocType **Chatbot Settings** | Enabled, provider, base URL, model, API key (encrypted), company, walk-in customer. |
| Audit | DocTypes **Chatbot Action**, **Chatbot Log** | Every summary shown for confirmation and what became of it; every message, reply and look-up. |
| Role | **Accountant Bot User** | Lets a user open the chat. Gives no accounting rights by itself. |
| Image | `docker/chatbot.Containerfile` | ERPNext image with the app inside. |
| Demo | `dev/start-demo.sh`, `.devcontainer/` | A throw-away ERPNext with the bot and test data, for GitHub Codespaces or a PC with Docker (`docs/DEMO.md`). |

### How the safety works

1. The AI can only call the tools in `tools.py`. Look-ups run as the logged-in user.
2. `prepare_sales_invoice` / `prepare_payment` save nothing. They check the details and store a
   **Chatbot Action** with status Pending; the summary the user sees is written by the server,
   not by the AI.
3. Only the Confirm button (or the user typing yes / haa) calls `api.confirm`, which saves
   exactly what was shown. If ERPNext changes a price or refuses, nothing is saved.
4. The bot is hidden from Administrator unless "Also show the chat to Administrator" is ticked,
   so the Administrator screen stays unchanged.

## 4. Not built yet

- Purchase invoices, supplier payments, payables.
- Journal entries, Balance Sheet, other statements.
- Cancelling a document from the chat (do it in ERPNext for now).
- Excel export (PDF only for now).
- Reading a photo of a supplier bill; daily summary; WhatsApp; voice.
- Creating a new customer or item from the chat (the bot asks; create it in ERPNext).

## 5. Open questions

- Confirm the Hostinger plan (RAM, CPU) and how ERPNext is installed there (Docker or bench).
- Which customer is the walk-in / cash customer at XAL Finance?
- Which payment methods (cash, EVC Plus, Zaad, eDahab, banks) and their accounts.
- OpenRouter account and key for testing; Anthropic key for real use (typed into Chatbot Settings by the owner, never sent in a chat).

See `README.md` for installing and `docs/TESTING.md` for what was tested and how.
