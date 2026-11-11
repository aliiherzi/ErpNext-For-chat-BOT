// XAL Accountant Bot: a chat button at the bottom right of the ERPNext desk.
// It only appears for users the server allows (xal_chatbot.api.get_boot).
(function () {
	const API = "xal_chatbot.api.";
	let panel, list, input, sendBtn, busy = false, started = false;

	function start() {
		// Several desk events can fire this; ask the server only once.
		if (started || !window.frappe || !frappe.session || !frappe.session.user || frappe.session.user === "Guest") return;
		started = true;
		frappe.call({ method: API + "get_boot" }).then((r) => {
			const boot = r.message || {};
			if (!boot.show) return;
			build();
			(boot.history || []).forEach((m) => {
				if (m.content && m.content[0] !== "[") bubble(m.role === "user" ? "me" : "bot", m.content);
			});
			if (boot.action) card(boot.action);
			if (!list.children.length) bubble("bot", __("Hello. Tell me what happened, for example: I sold 2 books to Ahmed for 5 dollars each.") + "\n" + __("Somali waan fahmaa: Waxaan Axmed ka iibiyay 2 buug."));
		});
	}

	function el(tag, cls, text) {
		const e = document.createElement(tag);
		if (cls) e.className = cls;
		if (text != null) e.textContent = text;
		return e;
	}

	function build() {
		const button = el("button", "xal-bot-button", "💬");
		button.id = "xal-bot-button";
		button.title = __("Accountant");
		button.setAttribute("aria-label", __("Open the accountant chat"));
		button.onclick = () => {
			panel.classList.toggle("open");
			if (panel.classList.contains("open")) { input.focus(); scroll(); }
		};

		panel = el("div", "xal-bot-panel");
		panel.id = "xal-bot-panel";
		const head = el("div", "xal-bot-head");
		head.append(el("span", "xal-bot-title", __("Accountant")));
		const fresh = el("button", "xal-bot-link", __("New chat"));
		fresh.onclick = () => frappe.call({ method: API + "reset", type: "POST" }).then(() => { list.innerHTML = ""; });
		const close = el("button", "xal-bot-link", "✕");
		close.setAttribute("aria-label", __("Close"));
		close.onclick = () => panel.classList.remove("open");
		head.append(fresh, close);

		list = el("div", "xal-bot-list");
		const form = el("form", "xal-bot-form");
		input = el("textarea", "xal-bot-input");
		input.rows = 1;
		input.placeholder = __("Write here...");
		input.addEventListener("keydown", (e) => {
			if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
		});
		sendBtn = el("button", "btn btn-primary btn-sm", __("Send"));
		sendBtn.type = "submit";
		form.append(input, sendBtn);
		form.onsubmit = (e) => { e.preventDefault(); submit(); };

		panel.append(head, list, form);
		document.body.append(button, panel);
	}

	function scroll() { list.scrollTop = list.scrollHeight; }

	function bubble(who, text) {
		const b = el("div", "xal-bot-msg xal-bot-" + who, text);
		list.append(b);
		scroll();
		return b;
	}

	function links(items) {
		if (!items || !items.length) return;
		const row = el("div", "xal-bot-links");
		items.forEach((l) => {
			const open = el("a", "btn btn-default btn-xs", __("Open") + " " + l.name);
			open.href = frappe.utils.get_form_link(l.doctype, l.name);
			row.append(open);
			if (l.pdf) {
				const pdf = el("a", "btn btn-default btn-xs", "PDF " + l.name);
				pdf.href = "/api/method/frappe.utils.print_format.download_pdf?doctype=" +
					encodeURIComponent(l.doctype) + "&name=" + encodeURIComponent(l.name);
				pdf.target = "_blank";
				row.append(pdf);
			}
		});
		list.append(row);
		scroll();
	}

	// The summary the server will save, with the only two buttons that can save or drop it.
	function card(action) {
		const c = el("div", "xal-bot-card");
		c.append(el("pre", "xal-bot-summary", action.summary));
		const row = el("div", "xal-bot-links");
		const yes = el("button", "btn btn-primary btn-sm", __("Confirm") + " / Haa");
		const no = el("button", "btn btn-default btn-sm", __("Cancel") + " / Maya");
		const done = (method) => {
			yes.disabled = no.disabled = true;
			call(method, { action: action.name });
		};
		yes.onclick = () => done("confirm");
		no.onclick = () => done("cancel");
		row.append(yes, no);
		c.append(row);
		list.append(c);
		scroll();
	}

	function call(method, args) {
		busy = true;
		sendBtn.disabled = true;
		const wait = bubble("bot", "…");
		// frappe.call gives a jQuery promise; wrap it to get catch / finally.
		return Promise.resolve(frappe.call({ method: API + method, args: args, type: "POST" })).then((r) => {
			const m = r.message || {};
			wait.remove();
			list.querySelectorAll(".xal-bot-card button").forEach((b) => (b.disabled = true));
			if (m.reply) bubble(m.error ? "bot xal-bot-error" : "bot", m.reply);
			if (m.action) card(m.action);
			links(m.links);
		}).catch(() => {
			wait.remove();
			bubble("bot xal-bot-error", __("Something went wrong. Please try again."));
		}).finally(() => { busy = false; sendBtn.disabled = false; input.focus(); });
	}

	function submit() {
		const text = input.value.trim();
		if (!text || busy) return;
		input.value = "";
		bubble("me", text);
		call("send", { message: text });
	}

	$(document).on("app_ready startup", start);
	$(start);
})();
