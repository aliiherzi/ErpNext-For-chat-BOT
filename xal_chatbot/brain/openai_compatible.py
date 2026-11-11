"""Brain for any service that speaks the OpenAI chat-completions format:
OpenRouter (for example the free Gemma models), Ollama, or a model server of your own."""

import json

import requests

from xal_chatbot.brain import BrainError, api_key

TIMEOUT = 120


def reply(settings, system, history, tools, run_tool):
	url = settings.base_url.rstrip("/") + "/chat/completions"
	headers = {"Content-Type": "application/json"}
	key = api_key(settings)
	if key:
		headers["Authorization"] = f"Bearer {key}"
	messages = [{"role": "system", "content": system}, *history]
	functions = [{"type": "function", "function": t} for t in tools]

	for _step in range(settings.max_steps or 8):
		message = _ask(url, headers, {"model": settings.model, "messages": messages, "tools": functions})
		calls = message.get("tool_calls") or []
		if not calls:
			return (message.get("content") or "").strip()
		messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": calls})
		for call in calls:
			fn = call.get("function") or {}
			try:
				args = json.loads(fn.get("arguments") or "{}")
				if not isinstance(args, dict):
					raise ValueError("arguments are not an object")
				result = run_tool(fn.get("name"), args)
			except ValueError as e:
				result = json.dumps({"error": f"The arguments were not valid JSON ({e}). Call the tool again."})
			messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": result})
	raise BrainError("The AI took too many steps without answering. Please ask again in a simpler way.")


def _ask(url, headers, body):
	try:
		r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
	except requests.Timeout:
		raise BrainError("The AI service did not answer in time. Please try again.")
	except requests.RequestException as e:
		raise BrainError(f"The AI service cannot be reached ({type(e).__name__}). Check the Base URL in Chatbot Settings.")
	try:
		data = r.json()
	except ValueError:
		data = {}
	error = data.get("error") if isinstance(data, dict) else None
	if r.status_code in (401, 403):
		raise BrainError("The AI service refused the API key. Check it in Chatbot Settings.")
	if r.status_code == 429:
		raise BrainError("The AI service limit is reached for now (too many requests). Try again later.")
	if r.status_code >= 400 or error:
		detail = (error.get("message") if isinstance(error, dict) else error) or r.text[:200]
		raise BrainError(f"The AI service returned an error ({r.status_code}): {detail}")
	try:
		return data["choices"][0]["message"]
	except (KeyError, IndexError, TypeError):
		raise BrainError("The AI service sent an answer the bot could not read.")
