import frappe

from ai_accountant import agent

ALLOWED_ROLES = {"System Manager", "Accounts Manager", "Accounts User"}


def _check_access():
	if frappe.session.user == "Guest" or not ALLOWED_ROLES.intersection(frappe.get_roles()):
		frappe.throw("Only accounts users can use the AI Accountant.", frappe.PermissionError)
	if not frappe.db.get_single_value("AI Accountant Settings", "enabled"):
		frappe.throw("The AI Accountant is turned off in AI Accountant Settings.")


@frappe.whitelist()
def can_use():
	return bool(ALLOWED_ROLES.intersection(frappe.get_roles())) and bool(
		frappe.db.get_single_value("AI Accountant Settings", "enabled")
	)


@frappe.whitelist(methods=["POST"])
def send_message(message: str, session_id: str | None = None):
	_check_access()
	message = (message or "").strip()
	if not message:
		frappe.throw("Message is empty.")
	if len(message) > 8000:
		frappe.throw("Message is too long.")
	session_id = session_id or frappe.generate_hash(length=12)
	reply_key = f"{frappe.session.user}:{frappe.generate_hash(length=16)}"
	agent.set_reply(reply_key, "pending", "Thinking…")
	frappe.enqueue(
		"ai_accountant.agent.run_turn",
		queue="long",
		timeout=900,
		session_id=session_id,
		message=message,
		reply_key=reply_key,
	)
	return {"session_id": session_id, "reply_key": reply_key}


@frappe.whitelist()
def get_reply(reply_key: str):
	if not reply_key.startswith(frappe.session.user + ":"):
		frappe.throw("Not your conversation.", frappe.PermissionError)
	return agent.get_reply(reply_key) or {"status": "error", "text": "This reply expired."}


@frappe.whitelist(methods=["POST"])
def reset(session_id: str):
	from ai_accountant import agent_openrouter

	agent.clear_history(frappe.session.user, session_id)
	agent_openrouter.clear_history(frappe.session.user, session_id)
	return True
