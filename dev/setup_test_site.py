"""Test-site setup: company, a customer, an item, payment method account, a bot user.
Run by dev/start-demo.sh. Never run it on a site with real books."""

import frappe


def run():
	frappe.set_user("Administrator")
	if not frappe.db.exists("Company", "Test Books"):
		from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

		setup_complete(
			{
				"language": "English",
				"country": "Somalia",
				"timezone": "Africa/Mogadishu",
				"currency": "USD",
				"full_name": "Admin",
				"email": "admin@example.com",
				"password": "admin",
				"company_name": "Test Books",
				"company_abbr": "TB",
				"chart_of_accounts": "Standard",
				"fy_start_date": "2026-01-01",
				"fy_end_date": "2026-12-31",
				"setup_demo": 0,
			}
		)
		frappe.db.commit()
	print("companies", frappe.get_all("Company", pluck="name"))
	for name in ("Ahmed Ali", "Walk-in Customer", "Amina Hassan"):
		if not frappe.db.exists("Customer", name):
			frappe.get_doc({"doctype": "Customer", "customer_name": name, "customer_type": "Individual"}).insert()
	for code, price in (("Book", 5), ("Pen", 1)):
		if not frappe.db.exists("Item", code):
			frappe.get_doc(
				{"doctype": "Item", "item_code": code, "item_name": code, "item_group": "All Item Groups", "stock_uom": "Nos", "is_stock_item": 0}
			).insert()
			frappe.get_doc({"doctype": "Item Price", "item_code": code, "price_list": "Standard Selling", "price_list_rate": price}).insert()
	cash = frappe.db.get_value("Account", {"account_type": "Cash", "is_group": 0, "company": "Test Books"}, "name")
	mop = frappe.get_doc("Mode of Payment", "Cash")
	if not any(a.company == "Test Books" for a in mop.accounts):
		mop.append("accounts", {"company": "Test Books", "default_account": cash})
		mop.save()
	for email, roles in (
		("manager@example.com", ["Accounts User", "Accounts Manager", "Sales User", "Accountant Bot User"]),
		("viewer@example.com", ["Accountant Bot User"]),
		("nobot@example.com", ["Accounts User"]),
	):
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0, "new_password": "Bot-test-12345"})
			u.insert()
			u.add_roles(*roles)
	s = frappe.get_doc("Chatbot Settings")
	s.enabled = 1
	if not s.get_password("api_key", raise_exception=False):  # keep a real brain if the tester set one
		s.provider = "OpenAI-compatible"
		s.base_url = "http://127.0.0.1:9000/v1"
		s.model = "mock"
	s.default_company = "Test Books"
	s.default_customer = "Walk-in Customer"
	s.save()
	frappe.db.commit()
	print("ready", cash)
