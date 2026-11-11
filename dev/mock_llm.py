"""A scripted stand-in for an AI service (OpenAI chat-completions format), for testing only.
It follows fixed rules so the whole path chat box -> brain -> tools -> ERPNext can be tested
without an API key. It is NOT part of the app."""
import json, re, itertools
from http.server import BaseHTTPRequestHandler, HTTPServer

ids = itertools.count(1)
def call(name, **args):
    return {"id": f"call_{next(ids)}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}

def decide(messages):
    last_user = max(i for i, m in enumerate(messages) if m["role"] == "user")
    text = messages[last_user]["content"].lower()
    results = [json.loads(m["content"]) for m in messages[last_user + 1:] if m["role"] == "tool"]
    n = len(results)
    who = "Ahmed" if "ahmed" in text or "axmed" in text else ("Nobody" if "nobody" in text else "")
    if "sold" in text or "iibiyay" in text:
        if n == 0:
            return [call("find_customer", query=who), call("find_item", query="book")]
        if n == 2:
            if not results[0]["customers"]:
                return "I cannot find that customer. Which customer is it?"
            cust = results[0]["customers"][0]["id"] if who else results[0]["customer_to_use_when_none_is_named"]
            qty = float((re.search(r"(\d+) (book|buug)", text) or [0, 1])[1])
            rate = float((re.search(r"(\d+(\.\d+)?) ?(dollar|\$|doolar)", text) or [0, results[1]["items"][0]["selling_price"]])[1])
            args = dict(customer=cust, items=[{"item_code": results[1]["items"][0]["item_code"], "qty": qty, "rate": rate}])
            if "cash" in text: args["paid_with"] = "Cash"
            return [call("prepare_sales_invoice", **args)]
        if "error" in results[-1]: return "Problem: " + results[-1]["error"]
        return "Fadlan hubi oo xaqiiji." if "iibiyay" in text else "Please check it and confirm."
    if "balance" in text or "owe" in text:
        if "everyone" in text or "all" in text:
            return [call("receivables")] if n == 0 else "Total owed to us: " + results[0].get("total_owed_to_us", results[0].get("error", "?"))
        if n == 0: return [call("find_customer", query=who)]
        if n == 1: return [call("customer_balance", customer=results[0]["customers"][0]["id"])]
        return "Balance: " + results[1].get("owes", results[1].get("error", "?"))
    if "profit" in text:
        if n == 0: return [call("profit_and_loss", from_date="2026-01-01", to_date="2026-12-31")]
        r = results[0]
        return r["error"] if "error" in r else f"Income {r['income']}, expenses {r['expenses']}, net profit {r['net_profit']}."
    if "paid me" in text or "payment" in text:
        if n == 0: return [call("find_customer", query=who)]
        if n == 1:
            amt = float(re.search(r"(\d+(\.\d+)?)", text)[1])
            return [call("prepare_payment", customer=results[0]["customers"][0]["id"], amount=amt, paid_with="Cash")]
        return ("Problem: " + results[-1]["error"]) if "error" in results[-1] else "Please check it and confirm."
    if "pdf" in text:
        inv = re.search(r"(acc-sinv-[\d-]+)", text)
        if n == 0: return [call("invoice_pdf", invoice=inv[1].upper() if inv else "NOPE")]
        return results[0].get("error") or "Here is the PDF."
    return "Hello, I am the accountant."

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert body["tools"] and body["messages"][0]["role"] == "system"
        out = decide(body["messages"])
        msg = {"role": "assistant", "content": out} if isinstance(out, str) else {"role": "assistant", "content": None, "tool_calls": out}
        data = json.dumps({"choices": [{"message": msg}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def log_message(self, *a): pass

HTTPServer(("127.0.0.1", 9000), H).serve_forever()
