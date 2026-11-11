import json
from xal_chatbot import tools, actions
import frappe
from xal_chatbot import api

def say(text):
	r = api.send(text)
	print(f"   > {text}\n   < {r.get('reply')!r} action={bool(r.get('action'))} links={r.get('links')}")
	return r

def check(label, ok):
	print(("PASS " if ok else "FAIL ") + label)
	assert ok, label

def bal(c="Ahmed Ali"):
	from erpnext.accounts.utils import get_balance_on
	return get_balance_on(party_type="Customer", party=c, company="Test Books")

def total_recv():
	return frappe.db.sql("select ifnull(sum(debit-credit),0) from `tabGL Entry` where party_type='Customer' and is_cancelled=0")[0][0]

def run():
	try:
		_run()
	except Exception:
		import traceback; traceback.print_exc()
		print("TESTS FAILED")

def _run():
	frappe.set_user("manager@example.com"); api.reset()
	b0, t0 = bal(), total_recv()
	n_si = frappe.db.count("Sales Invoice")
	r = say("I sold 2 book to Ahmed for 5 dollars each")
	check("invoice is only prepared, nothing saved", r["action"] and frappe.db.count("Sales Invoice") == n_si)
	print(r["action"]["summary"])
	act = r["action"]["name"]
	r = api.confirm(act); print("   <", r)
	si = frappe.get_doc("Sales Invoice", r["links"][0]["name"])
	check("confirm creates a submitted invoice of 10", si.docstatus == 1 and si.grand_total == 10 and si.customer == "Ahmed Ali" and si.outstanding_amount == 10)
	check("second confirm does nothing", "already" in api.confirm(act)["reply"] and frappe.db.count("Sales Invoice") == n_si + 1)
	check("balance went up by 10", bal() == b0 + 10 and frappe.format_value(b0 + 10, {"fieldtype": "Currency", "options": "USD"}) in say("what is the balance of Ahmed")["reply"])
	r = say("Ahmed paid me 4 payment")
	check("payment prepared", bool(r["action"])); print(r["action"]["summary"])
	r = say("haa"); 
	check("typing haa confirms the payment", r["links"] and r["links"][0]["doctype"] == "Payment Entry" and frappe.db.get_value("Payment Entry", r["links"][0]["name"], "docstatus") == 1)
	check("balance went down by 4", bal() == b0 + 6)
	check("the payment settled unpaid invoices", sum(frappe.get_all("Payment Entry Reference", {"parent": r["links"][0]["name"]}, pluck="allocated_amount")) == 4)
	r = say("I sold 1 book for 3 dollars cash")
	print(r["action"]["summary"])
	r = say("yes")
	si2 = frappe.get_doc("Sales Invoice", r["links"][0]["name"])
	check("cash sale to walk-in is fully paid", si2.customer == "Walk-in Customer" and si2.outstanding_amount == 0 and len(r["links"]) == 2)
	rep = say("who owes me, everyone balance")["reply"]
	check("receivables total matches the ledger", abs(total_recv() - (t0 + 6)) < 0.01 and frappe.format_value(t0 + 6, {"fieldtype": "Currency", "options": "USD"}) in rep)
	inc = frappe.db.sql("select sum(credit-debit) from `tabGL Entry` g join tabAccount a on a.name=g.account where a.root_type='Income' and g.is_cancelled=0")[0][0]
	check("profit and loss income matches the ledger", frappe.format_value(inc, {"fieldtype": "Currency", "options": "USD"}) in say("show me profit")["reply"])
	r = say("I sold 5 book to Ahmed for 2 dollars each"); a = r["action"]["name"]
	r = say("maya")
	check("maya cancels, nothing saved", frappe.db.get_value("Chatbot Action", a, "status") == "Cancelled" and frappe.db.count("Sales Invoice") == n_si + 2)
	r = say("Ahmed paid me 9999 payment"); print(r["action"]["summary"]); say("no")
	check("unknown customer is asked about", not say("I sold 1 book to Nobody for 5 dollars")["action"])
	check("pdf link", say(f"send me the pdf of {si.name.lower()}")["links"] == [{"doctype": "Sales Invoice", "name": si.name, "pdf": 1}])
	r = say("I sold 1 book to Ahmed for 9 dollars"); mine = r["action"]["name"]

	frappe.set_user("viewer@example.com"); api.reset()
	try:
		api.confirm(mine); check("another user cannot confirm my action", False)
	except frappe.PermissionError:
		check("another user cannot confirm my action", True)
	r = say("I sold 2 book to Ahmed for 5 dollars each")
	check("user without accounting roles cannot prepare an invoice", not r["action"])
	say("balance of Ahmed"); say("show me profit")
	check("still only 2 invoices", frappe.db.count("Sales Invoice") == n_si + 2)

	for user in ("nobot@example.com", "Administrator"):
		frappe.set_user(user)
		try:
			api.send("hello"); check(f"{user} is refused", False)
		except frappe.PermissionError:
			check(f"{user} is refused", True)
		check(f"{user} sees no chat button", api.get_boot() == {"show": False})
	frappe.set_user("manager@example.com")
	frappe.db.set_value("Chatbot Action", mine, "status", "Cancelled")
	frappe.db.commit()
	print("ALL TESTS PASSED"); print("logs", frappe.db.count("Chatbot Log"), "actions", frappe.db.get_all("Chatbot Action", fields=["name","status","result_name"], as_list=1))
def run_limits():
	frappe.set_user("viewer@example.com")
	for name, args in [
		("find_customer", {"query": "Ahmed"}),
		("customer_balance", {"customer": "Ahmed Ali"}),
		("receivables", {}),
		("profit_and_loss", {"from_date": "2026-01-01", "to_date": "2026-12-31"}),
		("prepare_sales_invoice", {"customer": "Ahmed Ali", "items": [{"item_code": "Book", "qty": 1, "rate": 5}]}),
		("prepare_payment", {"customer": "Ahmed Ali", "amount": 1, "paid_with": "Cash"}),
		("invoice_pdf", {"invoice": "ACC-SINV-2026-00001"}),
	]:
		t = tools.Turn(); out = json.loads(tools.run(t, name, args))
		print("viewer", name, "->", "REFUSED" if "error" in out and not t.action and not t.links else f"!!! ALLOWED {out}")
	frappe.set_user("manager@example.com")
	for name, args in [
		("prepare_sales_invoice", {"customer": "Ahmed Ali", "items": [{"item_code": "Nope", "qty": 1, "rate": 5}]}),
		("prepare_sales_invoice", {"customer": "Ahmed Ali", "items": [{"item_code": "Book", "qty": -1, "rate": 5}]}),
		("prepare_sales_invoice", {"customer": "Ahmed", "items": [{"item_code": "Book", "qty": 1, "rate": 5}]}),
		("prepare_payment", {"customer": "Ahmed Ali", "amount": 50, "paid_with": "Cash", "invoice": "ACC-SINV-2026-00001"}),
		("prepare_payment", {"customer": "Ahmed Ali", "amount": 5, "paid_with": "Bitcoin"}),
		("prepare_sales_invoice", {"customer": "Ahmed Ali", "items": [{"item_code": "Book", "qty": 1, "rate": 5}], "posting_date": "tomorrow-ish"}),
		("drop_database", {}),
	]:
		t = tools.Turn(); out = json.loads(tools.run(t, name, args)); print("bad input", name, "->", out.get("error", f"!!! {out}")[:90])
	# all or nothing: the payment fails after the invoice was made
	n = frappe.db.count("Sales Invoice"); g = frappe.db.count("GL Entry")
	t = tools.Turn(); tools.run(t, "prepare_sales_invoice", {"customer": "Ahmed Ali", "items": [{"item_code": "Book", "qty": 1, "rate": 5}], "paid_with": "Cash"})
	real = actions._payment_entry
	actions._payment_entry = lambda **k: frappe.throw("simulated failure")
	r = api.confirm(t.action["name"]); actions._payment_entry = real
	print("atomic:", r["reply"], "| invoices unchanged:", frappe.db.count("Sales Invoice") == n, "| ledger unchanged:", frappe.db.count("GL Entry") == g, "| status:", frappe.db.get_value("Chatbot Action", t.action["name"], "status"))
