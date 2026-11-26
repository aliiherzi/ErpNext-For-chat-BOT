"""OpenRouter version of the AI accountant loop (for free/test models such as Gemma).

OpenRouter uses the OpenAI-style chat-completions format, so this is a separate
loop from agent.py. Same tools, same prompt, same reply/caching helpers.
"""

import json

import frappe
import requests

from ai_accountant import tools
from ai_accountant.agent import (
	MAX_STEPS,
	HISTORY_TTL,
	_system_prompt,
	set_reply,
)

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemma-4-31b-it:free"

OPENAI_TOOLS = [
	{
		"type": "function",
		"function": {
			"name": t["name"],
			"description": t["description"],
			"parameters": t["input_schema"],
		},
	}
	for t in tools.TOOLS
]


def _key(user, session_id):
	return f"ai_accountant:or_history:{user}:{session_id}"


def load_history(user, session_id):
	raw = frappe.cache.get_value(_key(user, session_id))
	return json.loads(raw) if raw else []


def save_history(user, session_id, messages):
	frappe.cache.set_value(_key(user, session_id), json.dumps(messages), expires_in_sec=HISTORY_TTL)


def clear_history(user, session_id):
	frappe.cache.delete_value(_key(user, session_id))


class OpenRouterError(Exception):
	pass


def _call(api_key, model, messages):
	resp = requests.post(
		API_URL,
		headers={
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
			"X-Title": "ERPNext AI Accountant",
		},
		json={"model": model, "messages": messages, "tools": OPENAI_TOOLS, "max_tokens": 8000},
		timeout=180,
	)
	try:
		data = resp.json()
	except ValueError:
		raise OpenRouterError(f"OpenRouter returned HTTP {resp.status_code}.")
	if resp.status_code == 401:
		raise OpenRouterError("The OpenRouter API key is invalid. Check **AI Accountant Settings**.")
	if resp.status_code == 429:
		raise OpenRouterError(
			"The free model's limit was reached (free models allow only a few requests per minute "
			"and per day). Wait a bit and try again."
		)
	if resp.status_code >= 400 or "error" in data:
		msg = (data.get("error") or {}).get("message") if isinstance(data, dict) else None
		raise OpenRouterError(f"OpenRouter error ({resp.status_code}): {msg or 'unknown error'}")
	if not data.get("choices"):
		raise OpenRouterError("OpenRouter returned no answer. Try again.")
	return data["choices"][0]


def run_turn(settings, session_id, message, reply_key):
	user = frappe.session.user
	api_key = settings.get_password("openrouter_api_key", raise_exception=False)
	if not api_key:
		set_reply(reply_key, "error", "No OpenRouter API key yet. Add it in **AI Accountant Settings**.")
		return
	model = (settings.openrouter_model or DEFAULT_MODEL).strip()

	history = load_history(user, session_id)
	messages = [{"role": "system", "content": _system_prompt(settings)}] + history
	messages.append({"role": "user", "content": message})
	drafts = []

	try:
		for _ in range(MAX_STEPS):
			choice = _call(api_key, model, messages)
			msg = choice.get("message") or {}
			tool_calls = msg.get("tool_calls") or []
			assistant = {"role": "assistant", "content": msg.get("content") or ""}
			if tool_calls:
				assistant["tool_calls"] = tool_calls
			messages.append(assistant)

			if not tool_calls:
				text = (msg.get("content") or "").strip()
				if choice.get("finish_reason") == "length":
					text += "\n\n_(Answer was cut off — ask me to continue.)_"
				save_history(user, session_id, messages[1:])
				set_reply(reply_key, "done", text or "(no answer)", drafts)
				return

			for call in tool_calls:
				fn = call.get("function") or {}
				name = fn.get("name", "")
				try:
					args = json.loads(fn.get("arguments") or "{}")
					output, is_error = tools.execute(name, args)
				except json.JSONDecodeError:
					output, is_error = "Arguments were not valid JSON. Try again.", True
				if name == "create_draft" and not is_error:
					drafts.append(json.loads(output))
				messages.append(
					{
						"role": "tool",
						"tool_call_id": call.get("id"),
						"content": ("ERROR: " if is_error else "") + output,
					}
				)
			set_reply(reply_key, "pending", "Looking at your books…", drafts)

		set_reply(reply_key, "done", "This took too many steps. Try a more specific question.", drafts)

	except OpenRouterError as e:
		set_reply(reply_key, "error", str(e))
	except requests.RequestException:
		set_reply(reply_key, "error", "Can't reach OpenRouter. Check this server's internet connection.")
	except Exception:
		frappe.log_error("AI Accountant (OpenRouter): unexpected error")
		set_reply(reply_key, "error", "Something went wrong. An administrator can see details in the Error Log.")
