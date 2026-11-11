"""What the brain is allowed to do.

Two kinds of tools:
- look-ups (customers, items, balances, reports): they run at once, as the logged-in user,
  so ERPNext's own permissions decide what that user can see;
- "prepare_*" tools: they never save anything. They check the details and store a
  Chatbot Action with status Pending. Only the user's own Confirm (see api.confirm)
  turns it into a real document.
"""

import json

import frappe
from frappe.utils import flt, fmt_money, getdate, nowdate

SPECS = [
	{
		"name": "find_customer",
		"description": "Search customers by name. Use it before any invoice, payment or balance to get the exact customer id.",
		"parameters": {
			"type": "object",
			"properties": {"query": {"type": "string", "description": "Part of the customer name. Empty lists the first customers."}},
			"required": ["query"],
		},
	},
	{
		"name": "find_item",
		"description": "Search items (products or services) by name or code. Returns the exact item code and its selling price if one is set.",
		"parameters": {
			"type": "object",
			"properties": {"query": {"type": "string", "description": "Part of the item name or code."}},
			"required": ["query"],
		},
	},
	{
		"name": "list_payment_methods",
		"description": "List the ways of paying set up in this company (cash, bank, mobile money...).",
		"parameters": {"type": "object", "properties": {}},
	},
	{
		"name": "customer_balance",
		"description": "How much one customer owes now, with their unpaid invoices.",
		"parameters": {
			"type": "object",
			"properties": {"customer": {"type": "string", "description": "Exact customer id from find_customer."}},
			"required": ["customer"],
		},
	},
	{
		"name": "receivables",
		"description": "Accounts receivable: every customer who owes the company money and how much, largest first.",
		"parameters": {"type": "object", "properties": {}},
	},
	{
		"name": "profit_and_loss",
		"description": "Profit and Loss for a period: income, expenses and net profit, by account.",
		"parameters": {
			"type": "object",
			"properties": {
				"from_date": {"type": "string", "description": "First day, YYYY-MM-DD."},
				"to_date": {"type": "string", "description": "Last day, YYYY-MM-DD."},
			},
			"required": ["from_date", "to_date"],
		},
	},
	{
		"name": "invoice_pdf",
		"description": "Give the user the PDF of an existing sales invoice.",
		"parameters": {
			"type": "object",
			"properties": {"invoice": {"type": "string", "description": "Sales invoice number, for example ACC-SINV-2026-00012."}},
			"required": ["invoice"],
		},
	},
	{
		"name": "prepare_sales_invoice",
		"description": (
			"Prepare a sales invoice and show it to the user for confirmation. Nothing is saved until the user "
			"confirms. Use exact ids from find_customer and find_item."
		),
		"parameters": {
			"type": "object",
			"properties": {
				"customer": {"type": "string", "description": "Exact customer id."},
				"items": {
					"type": "array",
					"description": "The lines of the invoice.",
					"items": {
						"type": "object",
						"properties": {
							"item_code": {"type": "string", "description": "Exact item code."},
							"qty": {"type": "number", "description": "Quantity sold."},
							"rate": {"type": "number", "description": "Price for one unit."},
						},
						"required": ["item_code", "qty", "rate"],
					},
				},
				"posting_date": {"type": "string", "description": "Invoice date YYYY-MM-DD. Leave out for today."},
				"paid_with": {
					"type": "string",
					"description": "Payment method from list_payment_methods if the customer already paid in full. Leave out for a credit sale.",
				},
			},
			"required": ["customer", "items"],
		},
	},
	{
		"name": "prepare_payment",
		"description": (
			"Prepare a payment received from a customer and show it to the user for confirmation. Nothing is "
			"saved until the user confirms."
		),
		"parameters": {
			"type": "object",
			"properties": {
				"customer": {"type": "string", "description": "Exact customer id."},
				"amount": {"type": "number", "description": "Amount received."},
				"paid_with": {"type": "string", "description": "Payment method from list_payment_methods."},
				"invoice": {"type": "string", "description": "Sales invoice this pays, if the user named one. Leave out and it settles the customer's oldest unpaid invoices first."},
				"posting_date": {"type": "string", "description": "Date YYYY-MM-DD. Leave out for today."},
			},
			"required": ["customer", "amount", "paid_with"],
		},
	},
]


class Turn:
	"""What one user message produced besides the reply text."""

	def __init__(self):
		self.action = None  # the Chatbot Action waiting for Confirm, if any
		self.links = []  # documents / PDFs to show as buttons
		self.calls = []  # for the log


class ToolError(Exception):
	"""A problem the brain can explain to the user (not found, not allowed, wrong value)."""


def run(turn, name, args):
	"""Run one tool for the brain and return the text it reads back."""
	fn = HANDLERS.get(name)
	entry = {"tool": name, "args": args}
	turn.calls.append(entry)
	if not fn:
		entry["error"] = "unknown tool"
		return json.dumps({"error": f"There is no tool called {name}."})
	try:
		result = fn(turn, **(args or {}))
	except ToolError as e:
		entry["error"] = str(e)
		return json.dumps({"error": str(e)})
	except frappe.PermissionError:
		frappe.clear_last_message()
		entry["error"] = "not permitted"
		return json.dumps({"error": "This user is not allowed to see or do that in ERPNext. Tell them so; do not try another way."})
	except TypeError as e:
		entry["error"] = str(e)
		return json.dumps({"error": f"Wrong arguments for {name}: {e}"})
	return json.dumps(result, default=str)


# ---------------------------------------------------------------- helpers


def company():
	name = (
		frappe.db.get_single_value("Chatbot Settings", "default_company")
		or frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
	)
	if not name:
		raise ToolError("No company is set. Ask the administrator to choose one in Chatbot Settings.")
	return name


def currency():
	return frappe.get_cached_value("Company", company(), "default_currency")


def money(amount):
	return fmt_money(flt(amount), currency=currency())


def _customer(name):
	if not name or not frappe.db.exists("Customer", name):
		raise ToolError(f"There is no customer with the id '{name}'. Use find_customer to get the exact id.")
	frappe.has_permission("Customer", "read", doc=name, throw=True)
	return name


def _date(value):
	if not value:
		return nowdate()
	try:
		return str(getdate(value))
	except Exception:
		raise ToolError(f"'{value}' is not a date. Use YYYY-MM-DD.")


def _payment_method(name):
	if not frappe.db.exists("Mode of Payment", {"name": name, "enabled": 1}):
		raise ToolError(f"There is no payment method '{name}'. Use list_payment_methods.")
	account = frappe.db.get_value("Mode of Payment Account", {"parent": name, "company": company()}, "default_account")
	if not account:
		raise ToolError(
			f"The payment method '{name}' has no account for {company()}. "
			"The administrator must set it in Mode of Payment before the bot can use it."
		)
	return account


# ---------------------------------------------------------------- look-ups


def find_customer(turn, query=""):
	like = f"%{(query or '').strip()}%"
	rows = frappe.get_list(
		"Customer",
		filters={"disabled": 0},
		or_filters={"customer_name": ["like", like], "name": ["like", like]},
		fields=["name", "customer_name"],
		limit_page_length=10,
		order_by="customer_name asc",
	)
	out = {"customers": [{"id": r.name, "name": r.customer_name} for r in rows]}
	default = frappe.db.get_single_value("Chatbot Settings", "default_customer")
	if default:
		out["customer_to_use_when_none_is_named"] = default
	if not rows:
		out["note"] = "No customer matches. Ask the user for the right name; do not invent one."
	return out


def find_item(turn, query=""):
	like = f"%{(query or '').strip()}%"
	rows = frappe.get_list(
		"Item",
		filters={"disabled": 0, "is_sales_item": 1, "has_variants": 0},
		or_filters={"item_name": ["like", like], "name": ["like", like]},
		fields=["name", "item_name", "stock_uom"],
		limit_page_length=10,
		order_by="item_name asc",
	)
	items = []
	for r in rows:
		price = frappe.db.get_value("Item Price", {"item_code": r.name, "selling": 1}, "price_list_rate")
		items.append({"item_code": r.name, "name": r.item_name, "unit": r.stock_uom, "selling_price": flt(price) if price else None})
	out = {"items": items}
	if not rows:
		out["note"] = "No item matches. Ask the user which item they mean; do not invent one."
	return out


def list_payment_methods(turn):
	names = frappe.get_all("Mode of Payment", filters={"enabled": 1}, pluck="name")
	ready = frappe.get_all(
		"Mode of Payment Account", filters={"company": company(), "parent": ["in", names]}, pluck="parent"
	)
	return {"payment_methods": sorted(set(ready))}


def _unpaid(customer=None):
	filters = {"docstatus": 1, "outstanding_amount": [">", 0], "company": company()}
	if customer:
		filters["customer"] = customer
	return frappe.get_list(
		"Sales Invoice",
		filters=filters,
		fields=["name", "customer", "customer_name", "posting_date", "due_date", "grand_total", "outstanding_amount"],
		order_by="posting_date asc",
		limit_page_length=500,
	)


def customer_balance(turn, customer):
	from erpnext.accounts.utils import get_balance_on

	customer = _customer(customer)
	balance = flt(get_balance_on(party_type="Customer", party=customer, company=company()))
	invoices = _unpaid(customer)
	return {
		"customer": customer,
		"owes": money(balance),
		"owes_number": balance,
		"unpaid_invoices": [
			{"invoice": i.name, "date": i.posting_date, "due": i.due_date, "total": money(i.grand_total), "unpaid": money(i.outstanding_amount)}
			for i in invoices[:20]
		],
	}


def receivables(turn):
	"""Who owes the company, from the ledger (so payments on account are counted too)."""
	from frappe.query_builder.functions import Sum

	frappe.has_permission("GL Entry", "read", throw=True)
	gle = frappe.qb.DocType("GL Entry")
	rows = (
		frappe.qb.from_(gle)
		.select(gle.party, (Sum(gle.debit) - Sum(gle.credit)).as_("owes"))
		.where(gle.company == company())
		.where(gle.is_cancelled == 0)
		.where(gle.party_type == "Customer")
		.groupby(gle.party)
	).run(as_dict=True)
	rows = sorted((r for r in rows if abs(flt(r.owes)) >= 0.005), key=lambda r: -flt(r.owes))
	names = dict(frappe.get_all("Customer", filters={"name": ["in", [r.party for r in rows]]}, fields=["name", "customer_name"], as_list=True))
	return {
		"total_owed_to_us": money(sum(flt(r.owes) for r in rows)),
		"customers": [{"customer": names.get(r.party, r.party), "owes": money(r.owes)} for r in rows[:30]],
		"note": "A negative amount means the customer paid in advance.",
	}


def profit_and_loss(turn, from_date, to_date):
	from frappe.query_builder.functions import Sum

	frappe.has_permission("GL Entry", "read", throw=True)
	start, end = _date(from_date), _date(to_date)
	if start > end:
		raise ToolError("from_date is after to_date.")
	gle = frappe.qb.DocType("GL Entry")
	acc = frappe.qb.DocType("Account")
	rows = (
		frappe.qb.from_(gle)
		.join(acc)
		.on(gle.account == acc.name)
		.select(acc.root_type, gle.account, Sum(gle.credit).as_("credit"), Sum(gle.debit).as_("debit"))
		.where(gle.company == company())
		.where(gle.is_cancelled == 0)
		.where(gle.voucher_type != "Period Closing Voucher")
		.where(gle.posting_date[start:end])
		.where(acc.root_type.isin(["Income", "Expense"]))
		.groupby(acc.root_type, gle.account)
	).run(as_dict=True)
	income, expense = [], []
	for r in rows:
		if r.root_type == "Income":
			income.append((r.account, flt(r.credit) - flt(r.debit)))
		else:
			expense.append((r.account, flt(r.debit) - flt(r.credit)))
	total_income = sum(a for _, a in income)
	total_expense = sum(a for _, a in expense)
	return {
		"company": company(),
		"from": start,
		"to": end,
		"income": money(total_income),
		"expenses": money(total_expense),
		"net_profit": money(total_income - total_expense),
		"income_accounts": [{"account": n, "amount": money(a)} for n, a in sorted(income, key=lambda x: -x[1]) if a],
		"expense_accounts": [{"account": n, "amount": money(a)} for n, a in sorted(expense, key=lambda x: -x[1]) if a],
	}


def invoice_pdf(turn, invoice):
	if not frappe.db.exists("Sales Invoice", invoice):
		raise ToolError(f"There is no sales invoice '{invoice}'.")
	frappe.has_permission("Sales Invoice", "print", doc=invoice, throw=True)
	turn.links.append({"doctype": "Sales Invoice", "name": invoice, "pdf": 1})
	return {"ok": True, "note": "A PDF button for this invoice is now shown to the user under your reply."}


# ---------------------------------------------------------------- prepare (nothing is saved)


def _store(turn, action_type, payload, summary):
	"""Keep the checked details until the user confirms. One pending action per user."""
	for old in frappe.get_all("Chatbot Action", filters={"user": frappe.session.user, "status": "Pending"}, pluck="name"):
		frappe.db.set_value("Chatbot Action", old, "status", "Cancelled")
	doc = frappe.get_doc(
		{
			"doctype": "Chatbot Action",
			"user": frappe.session.user,
			"action_type": action_type,
			"status": "Pending",
			"summary": summary,
			"payload": json.dumps(payload, indent=1),
		}
	).insert(ignore_permissions=True)
	turn.action = {"name": doc.name, "summary": summary}
	return {
		"status": "waiting_for_user_confirmation",
		"shown_to_user": summary,
		"note": "NOT saved yet. The user now sees this summary with Confirm and Cancel buttons. Ask them to confirm; do not say it is done.",
	}


def prepare_sales_invoice(turn, customer, items, posting_date=None, paid_with=None):
	frappe.has_permission("Sales Invoice", "create", throw=True)
	customer = _customer(customer)
	date = _date(posting_date)
	if not items:
		raise ToolError("The invoice has no items.")
	lines, total, text = [], 0, []
	for row in items:
		code = (row or {}).get("item_code")
		if not code or not frappe.db.exists("Item", {"name": code, "disabled": 0}):
			raise ToolError(f"There is no item with the code '{code}'. Use find_item to get the exact code.")
		qty, rate = flt(row.get("qty")), flt(row.get("rate"))
		if qty <= 0:
			raise ToolError(f"The quantity of {code} must be more than 0.")
		if rate < 0:
			raise ToolError(f"The price of {code} cannot be negative.")
		lines.append({"item_code": code, "qty": qty, "rate": rate})
		total += qty * rate
		name = frappe.db.get_value("Item", code, "item_name") or code
		text.append(f"  {qty:g} x {name} @ {money(rate)} = {money(qty * rate)}")
	payload = {"company": company(), "customer": customer, "posting_date": date, "items": lines}
	if paid_with:
		payload["paid_to"] = _payment_method(paid_with)
		payload["paid_with"] = paid_with
		frappe.has_permission("Payment Entry", "create", throw=True)
	customer_name = frappe.db.get_value("Customer", customer, "customer_name") or customer
	summary = "\n".join(
		[
			"SALES INVOICE",
			f"Customer: {customer_name}",
			f"Date: {date}",
			*text,
			f"Total before tax: {money(total)}",
			f"Payment: {'paid now by ' + paid_with if paid_with else 'not paid yet (credit)'}",
		]
	)
	return _store(turn, "Sales Invoice", payload, summary)


def prepare_payment(turn, customer, amount, paid_with, invoice=None, posting_date=None):
	frappe.has_permission("Payment Entry", "create", throw=True)
	customer = _customer(customer)
	date = _date(posting_date)
	amount = flt(amount)
	if amount <= 0:
		raise ToolError("The amount must be more than 0.")
	payload = {
		"company": company(),
		"customer": customer,
		"posting_date": date,
		"amount": amount,
		"paid_with": paid_with,
		"paid_to": _payment_method(paid_with),
	}
	if invoice:
		inv = frappe.db.get_value("Sales Invoice", invoice, ["customer", "docstatus", "outstanding_amount"], as_dict=True)
		if not inv or inv.docstatus != 1:
			raise ToolError(f"There is no submitted sales invoice '{invoice}'.")
		if inv.customer != customer:
			raise ToolError(f"Invoice {invoice} belongs to another customer ({inv.customer}).")
		if amount > flt(inv.outstanding_amount) + 0.005:
			raise ToolError(
				f"Invoice {invoice} has only {money(inv.outstanding_amount)} unpaid, less than {money(amount)}. "
				"Ask the user whether to pay that amount, or leave the invoice out so the rest goes to their other invoices."
			)
		unpaid = [frappe._dict(name=invoice, outstanding_amount=inv.outstanding_amount)]
	else:
		unpaid = _unpaid(customer)  # oldest first, as an accountant would settle them
	left, allocations, against = amount, [], []
	for i in unpaid:
		if left < 0.005:
			break
		part = min(left, flt(i.outstanding_amount))
		allocations.append({"invoice": i.name, "amount": part})
		against.append(f"  {i.name}: {money(part)} of {money(i.outstanding_amount)} unpaid")
		left -= part
	if left >= 0.005:
		against.append(f"  On account (no unpaid invoice left): {money(left)}")
	payload["allocations"] = allocations
	customer_name = frappe.db.get_value("Customer", customer, "customer_name") or customer
	summary = "\n".join(
		[
			"PAYMENT RECEIVED",
			f"Customer: {customer_name}",
			f"Date: {date}",
			f"Amount: {money(amount)}",
			f"Paid with: {paid_with}",
			"Goes to:",
			*against,
		]
	)
	return _store(turn, "Payment Entry", payload, summary)


HANDLERS = {
	"find_customer": find_customer,
	"find_item": find_item,
	"list_payment_methods": list_payment_methods,
	"customer_balance": customer_balance,
	"receivables": receivables,
	"profit_and_loss": profit_and_loss,
	"invoice_pdf": invoice_pdf,
	"prepare_sales_invoice": prepare_sales_invoice,
	"prepare_payment": prepare_payment,
}
