# Testing

## What was tested (2026-11-11)

On a fresh ERPNext v16.52.0 test site in Docker (company "Test Books", USD), with the app
installed from this repository.

**The AI was replaced by a scripted stand-in** (`dev/mock_llm.py`), because no API key was
available. So these tests prove everything around the AI; they do not prove how well a real
model understands English or Somali.

| Check | Result |
|---|---|
| "I sold 2 book to Ahmed for 5 dollars each" only prepares; nothing saved before Confirm | pass |
| Confirm creates a submitted Sales Invoice of $10 for the right customer | pass |
| Pressing Confirm twice does not create a second invoice | pass |
| Customer balance goes up by 10 and the bot reports it | pass |
| "Ahmed paid me 4" + typing "haa" saves a Payment Entry that settles his unpaid invoices, oldest first | pass |
| Cash sale with no customer named goes to the walk-in customer and is fully paid | pass |
| Receivables total and Profit and Loss income match the ledger | pass |
| "maya" cancels and nothing is saved | pass |
| Paying more than is owed shows the rest as "on account" in the summary | pass |
| Unknown customer: the bot asks, nothing is prepared | pass |
| A user with only the bot role is refused by every tool (7 of 7) | pass |
| A user cannot confirm another user's action | pass |
| A user without the bot role, and Administrator, are refused and see no chat button | pass |
| Wrong item, negative quantity, wrong date, unknown payment method, unknown tool | all refused with a clear message |
| If the payment fails after the invoice was made, the invoice is rolled back too | pass |
| Chat box in a real browser (desktop and phone width): send, Confirm, Open and PDF buttons | pass |
| PDF download returns a PDF | pass (needs the `pdf-helper` service and `http_port` that `erpnext-system` already has) |

Two bugs were found and fixed during these tests: the chat button was added three times, and
a payment with no invoice named did not settle the customer's invoices.

## Not tested

- The demo inside GitHub Codespaces itself. `dev/start-demo.sh` was run from scratch on another Linux machine with Docker, but not in a Codespace.
- A real AI model: neither Gemma on OpenRouter nor Claude was called. The Claude brain was only
  run as far as the network call.
- Somali and English understanding, and how often a real model picks the wrong customer or amount.
- Taxes, discounts, pricing rules, stock items, other currencies than the company's.
- The Hostinger server and the `erpnext-rays` image (the test used plain `frappe/erpnext`).

First thing to do with a real key: run the sentences in `dev/test_flows.py` by hand in the chat
on a demo site, in both languages, and read the summaries before confirming.

## Repeat the tests

With a test stack running the image built from `docker/chatbot.Containerfile` and the app
installed (never on a site with real books: these create invoices and payments):

```bash
docker cp dev/setup_test_site.py <backend>:/home/frappe/frappe-bench/apps/frappe/frappe/xal_devsetup.py
docker cp dev/test_flows.py <backend>:/home/frappe/frappe-bench/apps/frappe/frappe/xal_devtest.py
docker cp dev/mock_llm.py <backend>:/tmp/mock_llm.py
docker exec -d <backend> /home/frappe/frappe-bench/env/bin/python /tmp/mock_llm.py
docker exec <backend> bench --site frontend execute frappe.xal_devsetup.run
docker exec <backend> bench --site frontend execute frappe.xal_devtest.run
docker exec <backend> bench --site frontend execute frappe.xal_devtest.run_limits
```

`dev/ui_check.js` drives the chat box in a browser with Playwright (`node dev/ui_check.js <folder for screenshots>`).
