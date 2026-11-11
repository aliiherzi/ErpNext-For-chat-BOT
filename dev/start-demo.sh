#!/usr/bin/env bash
# Start a throw-away ERPNext with the Accountant Bot and test data, on port 8080.
# Used by GitHub Codespaces (.devcontainer) and works on any computer with Docker:
#   bash dev/start-demo.sh
# Safe to run again: it only starts what is not running. NOT for real books.
set -euo pipefail
cd "$(dirname "$0")/.."
P=botdemo
B=$P-backend-1
bench() { docker exec "$B" bench --site frontend "$@"; }

if [ "${SKIP_BUILD:-0}" != 1 ]; then
	echo "==> Building the ERPNext + bot image (first time: about 5 GB to download)"
	docker build -f docker/chatbot.Containerfile -t erpnext-chatbot:dev .
fi

echo "==> Starting ERPNext"
docker compose -p $P -f dev/compose.yml up -d

echo "==> Waiting for the site (first time: 5 to 10 minutes)"
docker wait $P-create-site-1 >/dev/null
for _ in $(seq 60); do
	docker exec "$B" bench --site frontend list-apps >/dev/null 2>&1 && break
	sleep 5
done

if ! bench list-apps | grep -q xal_chatbot; then
	echo "==> Installing the bot on the site"
	bench install-app xal_chatbot
fi
bench set-config http_port 8080 --parse >/dev/null

echo "==> Test company, customers, items and users"
docker cp dev/setup_test_site.py "$B":/home/frappe/frappe-bench/apps/frappe/frappe/xal_devsetup.py
bench execute frappe.xal_devsetup.run

# The scripted stand-in AI, so the chat answers before any API key is set.
docker cp dev/mock_llm.py "$B":/tmp/mock_llm.py
docker exec -d "$B" /home/frappe/frappe-bench/env/bin/python /tmp/mock_llm.py
docker restart $P-pdf-helper-1 >/dev/null

cat <<'MSG'

==> Ready: open port 8080 (in Codespaces: the PORTS tab, then the globe icon).

    Bot user        manager@example.com   password  Bot-test-12345
    Administrator   Administrator         password  admin

    The chat button is at the bottom right for the bot user.
    See docs/DEMO.md for sentences to try and how to connect a real AI.
MSG
