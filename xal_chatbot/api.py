"""The chat box talks to these methods. Each one runs as the logged-in user."""

import time

import frappe
from frappe.utils import fmt_money

from xal_chatbot import actions, brain, tools
from xal_chatbot.install import BOT_ROLE

HISTORY_TURNS = 12  # messages kept as context (user + bot)
HISTORY_SECONDS = 6 * 60 * 60
YES = {"yes", "y", "ok", "okay", "confirm", "confirmed", "haa", "haye", "sax", "ogolaaday", "xaqiiji"}
NO = {"no", "n", "cancel", "stop", "maya", "jooji", "ka noqo"}


def _allowed(settings=None):
	settings = settings or frappe.get_cached_doc("Chatbot Settings")
	if not settings.enabled or frappe.session.user == "Guest":
		return False
	if frappe.session.user == "Administrator":
		return bool(settings.show_to_administrator)
	return BOT_ROLE in frappe.get_roles()


def _check():
	settings = frappe.get_cached_doc("Chatbot Settings")
	if not _allowed(settings):
		frappe.throw("The accountant bot is not available for this user.", frappe.PermissionError)
	return settings


def _history_key():
	return f"xal_chatbot:history:{frappe.session.user}"


def _pending():
	name = frappe.db.get_value(
		"Chatbot Action", {"user": frappe.session.user, "status": "Pending"}, "name", order_by="creation desc"
	)
	return frappe.get_doc("Chatbot Action", name) if name else None


@frappe.whitelist()
def get_boot():
	"""Should the chat button be shown to this user, and is something waiting for their Confirm?"""
	if not _allowed():
		return {"show": False}
	pending = _pending()
	return {
		"show": True,
		"history": frappe.cache.get_value(_history_key()) or [],
		"action": {"name": pending.name, "summary": pending.summary} if pending else None,
	}


@frappe.whitelist(methods=["POST"])
def send(message):
	"""One message from the user. Returns the reply, and the action waiting for Confirm if there is one."""
	settings = _check()
	message = (message or "").strip()
	if not message:
		return {"reply": ""}
	if len(message) > 4000:
		frappe.throw("That message is too long for the bot.")

	# "yes" / "haa" while something waits for confirmation is handled here, by fixed rules, never by the AI.
	pending = _pending()
	word = message.lower().strip(" .!")
	if pending and word in YES:
		return confirm(pending.name)
	if pending and word in NO:
		return cancel(pending.name)

	turn = tools.Turn()
	history = frappe.cache.get_value(_history_key()) or []
	history.append({"role": "user", "content": message})
	started, error = time.time(), None
	try:
		company = tools.company()
		system = brain.system_prompt(company, tools.currency(), settings.default_customer)
		reply = brain.get(settings)(settings, system, history, tools.SPECS, lambda name, args: tools.run(turn, name, args))
		reply = reply or "..."
	except (brain.BrainError, tools.ToolError) as e:
		reply, error = str(e), str(e)
	history.append({"role": "assistant", "content": reply})
	_save_history(history)
	_log(message, reply, turn.calls, settings, time.time() - started, error)
	return {"reply": reply, "action": turn.action, "links": turn.links, "error": bool(error)}


@frappe.whitelist(methods=["POST"])
def confirm(action):
	"""The user pressed Confirm: save the documents exactly as they were shown."""
	_check()
	doc = frappe.get_doc("Chatbot Action", action)
	if doc.user != frappe.session.user:
		frappe.throw("This is not your action.", frappe.PermissionError)
	if doc.status != "Pending":
		return {"reply": f"This was already {doc.status.lower()}.", "links": []}
	frappe.db.savepoint("xal_chatbot_action")
	try:
		result = actions.execute(doc)
	except Exception as e:
		frappe.db.rollback(save_point="xal_chatbot_action")
		reason = _clean(e)
		frappe.clear_messages()
		frappe.db.set_value("Chatbot Action", doc.name, {"status": "Failed", "error": reason[:1000]})
		reply = f"Not saved. ERPNext refused it: {reason}"
		_remember(f"[The user confirmed, but it was NOT saved. ERPNext said: {reason}]", reply)
		return {"reply": reply, "links": [], "error": True}
	frappe.db.set_value(
		"Chatbot Action",
		doc.name,
		{"status": "Done", "result_doctype": result["doctype"], "result_name": result["name"]},
	)
	total = fmt_money(result["total"], currency=result["currency"])
	reply = f"Done. {result['doctype']} {result['name']} is saved ({total})."
	_remember("[The user pressed Confirm.]", reply)
	return {"reply": reply, "links": result["links"]}


@frappe.whitelist(methods=["POST"])
def cancel(action):
	_check()
	doc = frappe.get_doc("Chatbot Action", action)
	if doc.user != frappe.session.user:
		frappe.throw("This is not your action.", frappe.PermissionError)
	if doc.status == "Pending":
		frappe.db.set_value("Chatbot Action", doc.name, "status", "Cancelled")
	reply = "Cancelled. Nothing was saved."
	_remember("[The user pressed Cancel.]", reply)
	return {"reply": reply, "links": []}


@frappe.whitelist(methods=["POST"])
def reset():
	"""Start a new conversation (documents already saved are not touched)."""
	_check()
	frappe.cache.delete_value(_history_key())
	pending = _pending()
	if pending:
		frappe.db.set_value("Chatbot Action", pending.name, "status", "Cancelled")
	return {"ok": True}


def _remember(user_text, reply):
	history = frappe.cache.get_value(_history_key()) or []
	history += [{"role": "user", "content": user_text}, {"role": "assistant", "content": reply}]
	_save_history(history)


def _save_history(history):
	history = history[-HISTORY_TURNS:]
	while history and history[0]["role"] != "user":  # a conversation must start with the user
		history.pop(0)
	frappe.cache.set_value(_history_key(), history, expires_in_sec=HISTORY_SECONDS)


def _clean(e):
	text = frappe.utils.strip_html(str(e) or type(e).__name__).strip()
	return text or type(e).__name__


def _log(message, reply, calls, settings, seconds, error):
	frappe.get_doc(
		{
			"doctype": "Chatbot Log",
			"user": frappe.session.user,
			"message": message,
			"reply": reply,
			"tools": frappe.as_json(calls),
			"model": f"{settings.provider}: {settings.model}",
			"seconds": round(seconds, 2),
			"error": error,
		}
	).insert(ignore_permissions=True)
