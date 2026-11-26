"""Tools the AI accountant can call.

Every tool runs as the logged-in user, through ERPNext's normal permission
checks, so the assistant can only see or create what that user could in the UI.
Nothing here submits, cancels, or deletes a document: writes are drafts only.
"""

import json

import frappe
from frappe.utils import get_url_to_form, nowdate

MAX_RESULT_CHARS = 60_000
MAX_LIST_ROWS = 200
MAX_REPORT_ROWS = 300

# Document types the assistant may create (always as drafts).
DRAFTABLE_DOCTYPES = [
	"Sales Invoice",
	"Purchase Invoice",
	"Journal Entry",
	"Payment Entry",
	"Quotation",
	"Sales Order",
	"Purchase Order",
	"Customer",
	"Supplier",
	"Item",
]

TOOLS = [
	{
		"name": "get_context",
		"description": (
			"Get today's date, the user's default company and currency, the current fiscal year, "
			"and the list of companies. Call this first when dates, company, or currency matter."
		),
		"input_schema": {"type": "object", "properties": {}},
	},
	{
		"name": "search_records",
		"description": (
			"List ERPNext records of one DocType (e.g. 'Sales Invoice', 'Customer', 'GL Entry', "
			"'Payment Entry', 'Account'). Filters use Frappe syntax: a list of "
			"[field, operator, value] triples, e.g. [[\"docstatus\",\"=\",1],"
			"[\"posting_date\",\">=\",\"2026-10-01\"]]. docstatus: 0=draft, 1=submitted, 2=cancelled. "
			"Fields are column names, or aggregates written as objects, e.g. "
			"{\"SUM\": \"grand_total\", \"as\": \"total\"} or {\"COUNT\": \"*\", \"as\": \"n\"} "
			"(also AVG, MIN, MAX), optionally with group_by (e.g. 'customer'). "
			f"Returns at most {MAX_LIST_ROWS} rows."
		),
		"input_schema": {
			"type": "object",
			"properties": {
				"doctype": {"type": "string"},
				"filters": {"type": "array", "items": {"type": "array"}},
				"fields": {
					"type": "array",
					"items": {"anyOf": [{"type": "string"}, {"type": "object"}]},
				},
				"order_by": {"type": "string", "description": "e.g. 'posting_date desc'"},
				"group_by": {"type": "string"},
				"limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIST_ROWS},
			},
			"required": ["doctype"],
		},
	},
	{
		"name": "get_record",
		"description": "Read one full ERPNext document, including its child tables (e.g. invoice items).",
		"input_schema": {
			"type": "object",
			"properties": {"doctype": {"type": "string"}, "name": {"type": "string"}},
			"required": ["doctype", "name"],
		},
	},
	{
		"name": "run_report",
		"description": (
			"Run a standard ERPNext report and get its rows. Useful reports: 'General Ledger', "
			"'Trial Balance', 'Profit and Loss Statement', 'Balance Sheet', 'Cash Flow', "
			"'Accounts Receivable', 'Accounts Payable', 'Accounts Receivable Summary', "
			"'Accounts Payable Summary', 'Sales Register', 'Purchase Register', 'Gross Profit'. "
			"Most need filters such as company, from_date/to_date or period_start_date/period_end_date, "
			"report_date, and for financial statements: filter_based_on ('Date Range' or 'Fiscal Year'), "
			"periodicity ('Monthly','Quarterly','Half-Yearly','Yearly'). If a filter is missing, "
			"the error says which one."
		),
		"input_schema": {
			"type": "object",
			"properties": {
				"report_name": {"type": "string"},
				"filters": {"type": "object"},
			},
			"required": ["report_name", "filters"],
		},
	},
	{
		"name": "create_draft",
		"description": (
			"Create a DRAFT document for a human to review and submit. Never submits. "
			f"Allowed doctypes: {', '.join(DRAFTABLE_DOCTYPES)}. 'data' holds the document's fields "
			"and child tables, e.g. for a Sales Invoice: {\"customer\": \"Ali\", \"company\": \"...\", "
			"\"items\": [{\"item_code\": \"CHAIR\", \"qty\": 3, \"rate\": 50}]}. Look up the exact "
			"customer/item/account names with search_records first. Returns the draft's name and link."
		),
		"input_schema": {
			"type": "object",
			"properties": {
				"doctype": {"type": "string", "enum": DRAFTABLE_DOCTYPES},
				"data": {"type": "object"},
			},
			"required": ["doctype", "data"],
		},
	},
]


def _dumps(value) -> str:
	text = json.dumps(value, default=str, ensure_ascii=False)
	if len(text) > MAX_RESULT_CHARS:
		text = text[:MAX_RESULT_CHARS] + " ...[truncated: narrow the filters or ask for fewer fields]"
	return text


def _require_doctype(doctype: str):
	if not doctype or not frappe.db.exists("DocType", doctype):
		raise frappe.ValidationError(f"Unknown DocType: {doctype!r}")


def get_context() -> dict:
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	currency = frappe.get_cached_value("Company", company, "default_currency") if company else None
	fiscal_year = None
	try:
		from erpnext.accounts.utils import get_fiscal_year

		fy = get_fiscal_year(nowdate(), company=company, as_dict=True)
		fiscal_year = {"name": fy.name, "start": fy.year_start_date, "end": fy.year_end_date}
	except Exception:
		pass
	return {
		"today": nowdate(),
		"user": frappe.session.user,
		"default_company": company,
		"currency": currency,
		"fiscal_year": fiscal_year,
		"companies": frappe.get_list("Company", pluck="name"),
	}


def search_records(doctype, filters=None, fields=None, order_by=None, group_by=None, limit=50):
	_require_doctype(doctype)
	limit = max(1, min(int(limit or 50), MAX_LIST_ROWS))
	return frappe.get_list(
		doctype,
		filters=filters or [],
		fields=fields or ["name"],
		order_by=order_by or None,
		group_by=group_by or None,
		limit_page_length=limit,
	)


def get_record(doctype, name):
	_require_doctype(doctype)
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	return doc.as_dict(no_default_fields=False)


def run_report(report_name, filters):
	from frappe.desk.query_report import run

	result = run(report_name, filters=filters, ignore_prepared_report=True, are_default_filters=False)
	columns = []
	for col in result.get("columns") or []:
		if isinstance(col, dict):
			columns.append({"fieldname": col.get("fieldname"), "label": col.get("label")})
		else:
			columns.append({"label": str(col)})
	rows = result.get("result") or []
	return {
		"columns": columns,
		"rows": rows[:MAX_REPORT_ROWS],
		"total_rows": len(rows),
		"truncated": len(rows) > MAX_REPORT_ROWS,
	}


def create_draft(doctype, data):
	if doctype not in DRAFTABLE_DOCTYPES:
		raise frappe.PermissionError(f"The assistant may not create {doctype}.")
	data = dict(data or {})
	for key in ("name", "docstatus", "doctype", "owner", "creation", "modified", "amended_from"):
		data.pop(key, None)
	doc = frappe.get_doc({"doctype": doctype, **data})
	doc.docstatus = 0
	doc.insert()  # checks the user's create permission and runs ERPNext validation
	frappe.db.commit()
	return {
		"doctype": doctype,
		"name": doc.name,
		"status": "Draft - needs human review and submit",
		"url": get_url_to_form(doctype, doc.name),
		"grand_total": doc.get("grand_total"),
	}


_HANDLERS = {
	"get_context": get_context,
	"search_records": search_records,
	"get_record": get_record,
	"run_report": run_report,
	"create_draft": create_draft,
}


def execute(name: str, tool_input: dict) -> tuple[str, bool]:
	"""Run one tool. Returns (result_text, is_error)."""
	handler = _HANDLERS.get(name)
	if not handler:
		return f"Unknown tool: {name}", True
	if not isinstance(tool_input, dict):
		return "Tool input must be a JSON object.", True
	try:
		return _dumps(handler(**tool_input)), False
	except frappe.PermissionError as e:
		frappe.db.rollback()
		return f"Permission denied: {e}. The current user is not allowed to do this.", True
	except TypeError as e:
		return f"Bad arguments for {name}: {e}", True
	except Exception as e:
		frappe.db.rollback()
		frappe.clear_messages()
		return f"Error: {type(e).__name__}: {e}", True
