import frappe

BOT_ROLE = "Accountant Bot User"


def after_install():
	"""Create the role that lets a user open the chat. It gives no accounting rights by itself:
	what the bot can do for a user is decided by that user's normal ERPNext roles."""
	if not frappe.db.exists("Role", BOT_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": BOT_ROLE, "desk_access": 1}).insert(ignore_permissions=True)
