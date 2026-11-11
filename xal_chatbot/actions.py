"""Turn a confirmed Chatbot Action into real ERPNext documents.

Runs as the user who confirmed, with normal permission checks: a user who may not
create or submit a Sales Invoice in ERPNext cannot do it through the bot either.
Everything for one action is saved together or not at all.
"""

import json

import frappe
from frappe.utils import flt, nowdate


def execute(action):
	"""Save the documents for a pending action. Returns the links to show the user."""
	payload = json.loads(action.payload)
	if action.action_type == "Sales Invoice":
		return _sales_invoice(payload)
	if action.action_type == "Payment Entry":
		return _payment(payload)
	frappe.throw(f"Unknown action type {action.action_type}")


def _sales_invoice(p):
	si = frappe.new_doc("Sales Invoice")
	si.company = p["company"]
	si.customer = p["customer"]
	si.posting_date = p["posting_date"]
	si.set_posting_time = 1
	si.due_date = p["posting_date"] if p.get("paid_to") else None
	for row in p["items"]:
		si.append("items", {"item_code": row["item_code"], "qty": row["qty"], "rate": row["rate"]})
	si.insert()
	# The user confirmed these exact prices: refuse to post if ERPNext changed one (pricing rule, price list).
	for row, line in zip(p["items"], si.items):
		if abs(flt(line.rate) - flt(row["rate"])) > 0.005 or abs(flt(line.qty) - flt(row["qty"])) > 0.0005:
			frappe.throw(
				f"ERPNext changed the price or quantity of {row['item_code']} "
				f"(asked {row['qty']} x {row['rate']}, got {line.qty} x {line.rate}). Nothing was saved."
			)
	si.submit()
	links = [{"doctype": "Sales Invoice", "name": si.name, "pdf": 1}]
	if p.get("paid_to"):
		pe = _payment_entry(
			company=p["company"],
			customer=p["customer"],
			date=p["posting_date"],
			amount=flt(si.outstanding_amount),
			paid_to=p["paid_to"],
			paid_with=p["paid_with"],
			allocations=[{"invoice": si.name, "amount": flt(si.outstanding_amount)}],
		)
		links.append({"doctype": "Payment Entry", "name": pe.name})
	return {"doctype": "Sales Invoice", "name": si.name, "links": links, "total": si.grand_total, "currency": si.currency}


def _payment(p):
	pe = _payment_entry(
		company=p["company"],
		customer=p["customer"],
		date=p["posting_date"],
		amount=flt(p["amount"]),
		paid_to=p["paid_to"],
		paid_with=p["paid_with"],
		allocations=p.get("allocations") or [],
	)
	return {
		"doctype": "Payment Entry",
		"name": pe.name,
		"links": [{"doctype": "Payment Entry", "name": pe.name}],
		"total": pe.paid_amount,
		"currency": pe.paid_from_account_currency,
	}


def _payment_entry(company, customer, date, amount, paid_to, paid_with, allocations):
	"""A payment received from a customer, settling the given invoices (any rest stays on account)."""
	from erpnext.accounts.party import get_party_account

	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.company = company
	pe.posting_date = date or nowdate()
	pe.mode_of_payment = paid_with
	pe.party_type = "Customer"
	pe.party = customer
	pe.paid_from = get_party_account("Customer", customer, company)
	pe.paid_to = paid_to
	pe.paid_amount = amount
	pe.received_amount = amount
	pe.source_exchange_rate = 1
	pe.target_exchange_rate = 1
	pe.reference_no = "Accountant Bot"
	pe.reference_date = pe.posting_date
	for a in allocations:
		pe.append(
			"references",
			{"reference_doctype": "Sales Invoice", "reference_name": a["invoice"], "allocated_amount": a["amount"]},
		)
	pe.insert()
	allocated = sum(flt(r.allocated_amount) for r in pe.references)
	if abs(flt(pe.paid_amount) - amount) > 0.005 or abs(allocated - sum(flt(a["amount"]) for a in allocations)) > 0.005:
		frappe.throw(f"ERPNext changed the payment amounts (asked {amount}, got {pe.paid_amount}). Nothing was saved.")
	pe.submit()
	return pe
