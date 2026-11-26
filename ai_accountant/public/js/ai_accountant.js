// AI Accountant chat window for the ERPNext desk.
(function () {
	const STORE_KEY = () => `ai_accountant:${frappe.session.user}`;
	const POLL_MS = 1500;
	const MAX_WAIT_MS = 15 * 60 * 1000;

	const state = { session_id: null, transcript: [], busy: false };

	function load() {
		try {
			Object.assign(state, JSON.parse(localStorage.getItem(STORE_KEY())) || {});
		} catch (e) {
			/* ignore */
		}
		state.busy = false;
	}
	function save() {
		localStorage.setItem(
			STORE_KEY(),
			JSON.stringify({ session_id: state.session_id, transcript: state.transcript.slice(-60) })
		);
	}

	function build() {
		const $launcher = $(`
			<button class="ai-acc-launcher" title="${__("AI Accountant")}">
				<span>💬</span><span class="ai-acc-launcher-label">${__("AI Accountant")}</span>
			</button>`).appendTo(document.body);

		const $panel = $(`
			<div class="ai-acc-panel" style="display:none" role="dialog" aria-label="${__("AI Accountant")}">
				<div class="ai-acc-header">
					<div>
						<div class="ai-acc-title">${__("AI Accountant")}</div>
						<div class="ai-acc-sub">${__("Answers from your ERPNext books · creates drafts only")}</div>
					</div>
					<div class="ai-acc-actions">
						<button class="btn btn-xs btn-default ai-acc-new">${__("New chat")}</button>
						<button class="btn btn-xs btn-default ai-acc-close" aria-label="${__("Close")}">✕</button>
					</div>
				</div>
				<div class="ai-acc-body"></div>
				<div class="ai-acc-suggest"></div>
				<form class="ai-acc-input">
					<textarea rows="2" placeholder="${__("Ask about sales, receivables, profit, or ask me to draft an invoice…")}"></textarea>
					<button type="submit" class="btn btn-primary btn-sm">${__("Send")}</button>
				</form>
			</div>`).appendTo(document.body);

		const $body = $panel.find(".ai-acc-body");
		const $text = $panel.find("textarea");
		const $send = $panel.find("button[type=submit]");
		const $suggest = $panel.find(".ai-acc-suggest");

		const suggestions = [
			__("How much did we sell this month?"),
			__("Who owes us money, and how overdue?"),
			__("Show the profit and loss for this fiscal year"),
			__("What bills do we need to pay this week?"),
		];

		function bubble(role, html) {
			const $b = $(`<div class="ai-acc-msg ai-acc-${role}"></div>`).html(html);
			$body.append($b);
			$body.scrollTop($body[0].scrollHeight);
			return $b;
		}
		function renderBot(text, drafts) {
			let html = frappe.markdown(text || "");
			(drafts || []).forEach((d) => {
				if (d && d.url) {
					html += `<a class="ai-acc-draft" href="${encodeURI(d.url)}">📝 ${frappe.utils.escape_html(
						d.doctype + " " + d.name
					)} — ${__("open draft to review & submit")}</a>`;
				}
			});
			return html;
		}
		function renderAll() {
			$body.empty();
			if (!state.transcript.length) {
				bubble(
					"bot",
					frappe.markdown(
						__(
							"Hi! I'm your AI accountant. I read your ERPNext books (with your permissions) and can prepare draft invoices and entries for you to review."
						)
					)
				);
				$suggest.empty().show();
				suggestions.forEach((s) =>
					$(`<button class="btn btn-xs btn-default"></button>`)
						.text(s)
						.on("click", () => send(s))
						.appendTo($suggest)
				);
			} else {
				$suggest.hide();
			}
			state.transcript.forEach((m) =>
				bubble(m.role, m.role === "user" ? frappe.utils.escape_html(m.text) : renderBot(m.text, m.drafts))
			);
		}
		function setBusy(b) {
			state.busy = b;
			$send.prop("disabled", b);
			$text.prop("disabled", b);
		}

		async function send(message) {
			message = (message || "").trim();
			if (!message || state.busy) return;
			$suggest.hide();
			state.transcript.push({ role: "user", text: message });
			save();
			bubble("user", frappe.utils.escape_html(message));
			$text.val("");
			setBusy(true);
			const $wait = bubble("bot ai-acc-wait", `<span class="ai-acc-dots">${__("Thinking…")}</span>`);
			try {
				const r = await frappe.call({
					method: "ai_accountant.api.send_message",
					args: { message, session_id: state.session_id },
				});
				state.session_id = r.message.session_id;
				const reply = await poll(r.message.reply_key, $wait);
				$wait.remove();
				state.transcript.push({ role: "bot", text: reply.text, drafts: reply.drafts });
				save();
				bubble(reply.status === "error" ? "bot ai-acc-error" : "bot", renderBot(reply.text, reply.drafts));
			} catch (e) {
				$wait.remove();
				bubble("bot ai-acc-error", __("Couldn't reach the AI Accountant. Please try again."));
			} finally {
				setBusy(false);
				$text.trigger("focus");
			}
		}

		function poll(reply_key, $wait) {
			const started = Date.now();
			return new Promise((resolve, reject) => {
				const tick = () => {
					frappe
						.call({ method: "ai_accountant.api.get_reply", args: { reply_key }, freeze: false })
						.then((r) => {
							const reply = r.message || {};
							if (reply.status === "pending") {
								if (reply.text) $wait.find(".ai-acc-dots").text(reply.text);
								if (Date.now() - started > MAX_WAIT_MS)
									return resolve({ status: "error", text: __("Timed out waiting for an answer.") });
								setTimeout(tick, POLL_MS);
							} else {
								resolve(reply);
							}
						})
						.catch(reject);
				};
				setTimeout(tick, POLL_MS);
			});
		}

		$launcher.on("click", () => {
			$panel.toggle();
			if ($panel.is(":visible")) $text.trigger("focus");
		});
		$panel.find(".ai-acc-close").on("click", () => $panel.hide());
		$panel.find(".ai-acc-new").on("click", () => {
			if (state.busy) return;
			if (state.session_id)
				frappe.call({ method: "ai_accountant.api.reset", args: { session_id: state.session_id } });
			state.session_id = null;
			state.transcript = [];
			save();
			renderAll();
		});
		$panel.find("form").on("submit", (e) => {
			e.preventDefault();
			send($text.val());
		});
		$text.on("keydown", (e) => {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				send($text.val());
			}
		});

		renderAll();
	}

	$(document).ready(() => {
		if (!window.frappe || !frappe.session || frappe.session.user === "Guest") return;
		frappe
			.call({ method: "ai_accountant.api.can_use", freeze: false })
			.then((r) => {
				if (r.message) {
					load();
					build();
				}
			});
	});
})();
