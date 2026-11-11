# ERPNext image + the XAL Accountant Bot app.
# Build from the root of this repository:
#   docker build -f docker/chatbot.Containerfile -t erpnext-chatbot:v16.52.0 .
# To add the bot on top of another image (for example the Rays one):
#   docker build -f docker/chatbot.Containerfile --build-arg BASE=erpnext-rays:v16.52.0 -t erpnext-rays-chatbot:v16.52.0 .
# Then, once per site:  bench --site <site> install-app xal_chatbot
ARG BASE=frappe/erpnext:v16.52.0
FROM ${BASE}
USER frappe
WORKDIR /home/frappe/frappe-bench
COPY --chown=frappe:frappe . apps/xal_chatbot
# Install the app (and the Claude SDK it can use), serve its public folder as /assets/xal_chatbot,
# and list it in apps.txt so bench knows it.
RUN env/bin/pip install --no-cache-dir -e apps/xal_chatbot \
 && ln -s /home/frappe/frappe-bench/apps/xal_chatbot/xal_chatbot/public assets/xal_chatbot \
 && ls -1 apps > sites/apps.txt \
 && env/bin/python -c "import xal_chatbot.hooks, anthropic"
