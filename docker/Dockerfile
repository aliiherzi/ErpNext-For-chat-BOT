# ERPNext v16 + the AI Accountant app.
# Build from the repo root:  docker build -f docker/Dockerfile -t erpnext-ai:latest .
ARG ERPNEXT_IMAGE=frappe/erpnext:v16.60.0
FROM ${ERPNEXT_IMAGE}

USER frappe
WORKDIR /home/frappe/frappe-bench

COPY --chown=frappe:0 . apps/ai_accountant

RUN rm -rf apps/ai_accountant/docker apps/ai_accountant/.git \
 && env/bin/pip install --no-cache-dir -e apps/ai_accountant \
 && ln -sfn /home/frappe/frappe-bench/apps/ai_accountant/ai_accountant/public assets/ai_accountant \
 && env/bin/python -c "import ai_accountant.agent, anthropic; print('anthropic', anthropic.__version__)"
