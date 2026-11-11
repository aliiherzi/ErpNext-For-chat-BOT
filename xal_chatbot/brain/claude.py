"""Brain that uses Claude through Anthropic's API (set Model to, for example, claude-haiku-5-5)."""

from xal_chatbot.brain import BrainError, api_key

MAX_TOKENS = 16000


def reply(settings, system, history, tools, run_tool):
	import anthropic

	key = api_key(settings)
	if not key:
		raise BrainError("No API key is set. Add the Claude API key in Chatbot Settings.")
	client = anthropic.Anthropic(api_key=key)
	claude_tools = [
		{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools
	]
	messages = [{"role": m["role"], "content": m["content"]} for m in history]

	for _step in range(settings.max_steps or 8):
		try:
			response = client.messages.create(
				model=settings.model,
				max_tokens=MAX_TOKENS,
				system=system,
				tools=claude_tools,
				messages=messages,
			)
		except anthropic.AuthenticationError:
			raise BrainError("Claude refused the API key. Check it in Chatbot Settings.")
		except anthropic.NotFoundError:
			raise BrainError(f"Claude does not know the model '{settings.model}'. Check it in Chatbot Settings.")
		except anthropic.RateLimitError:
			raise BrainError("The Claude limit is reached for now (too many requests). Try again in a minute.")
		except anthropic.APIStatusError as e:
			raise BrainError(f"Claude returned an error ({e.status_code}): {e.message}")
		except anthropic.APIConnectionError:
			raise BrainError("Claude cannot be reached. Check the server's internet connection.")

		if response.stop_reason == "refusal":
			raise BrainError("The AI declined to answer this message.")
		if response.stop_reason == "max_tokens":
			raise BrainError("The answer was too long and was cut off. Please ask for less at once.")

		calls = [b for b in response.content if b.type == "tool_use"]
		if response.stop_reason != "tool_use" or not calls:
			return "".join(b.text for b in response.content if b.type == "text").strip()

		# Keep the assistant turn exactly as it came back, then answer every tool call in one user turn.
		messages.append({"role": "assistant", "content": response.content})
		messages.append(
			{
				"role": "user",
				"content": [
					{"type": "tool_result", "tool_use_id": c.id, "content": run_tool(c.name, c.input)} for c in calls
				],
			}
		)
	raise BrainError("The AI took too many steps without answering. Please ask again in a simpler way.")
