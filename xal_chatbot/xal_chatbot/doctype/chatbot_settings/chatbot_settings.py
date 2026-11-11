import frappe
from frappe.model.document import Document


class ChatbotSettings(Document):
	def validate(self):
		if self.provider == "OpenAI-compatible" and not (self.base_url or "").strip():
			frappe.throw("Base URL is needed for an OpenAI-compatible provider.")
		if not self.max_steps or self.max_steps < 2:
			self.max_steps = 8
