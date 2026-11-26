FROM erpnext-ai:latest
USER frappe
WORKDIR /home/frappe/frappe-bench
COPY --chown=frappe:0 travel_agency apps/travel_agency
RUN echo /home/frappe/frappe-bench/apps/travel_agency > "$(env/bin/python -c 'import site; print(site.getsitepackages()[0])')/travel_agency.pth" \
 && ln -sfn /home/frappe/frappe-bench/apps/travel_agency/travel_agency/public assets/travel_agency \
 && env/bin/python -c "import travel_agency.hooks"
