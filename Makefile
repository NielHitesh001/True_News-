PY := .venv/bin/python

test:
	PYTHONPATH=src:. $(PY) -m pytest tests/ -v

run:
	@if [ -z "$(EVENT)" ]; then \
		echo "Usage: make run EVENT=<event_id> (e.g. make run EVENT=event-key-bridge-01 or EVENT=all)"; \
		exit 1; \
	fi
	PYTHONPATH=src:. $(PY) -m newsx.cli run --event $(EVENT)

transparency:
	PYTHONPATH=src:. $(PY) -m newsx.cli transparency

brief:
	@if [ -z "$(EVENT)" ]; then \
		echo "Usage: make brief EVENT=<event_id> (e.g. make brief EVENT=event-key-bridge-01 or EVENT=all)"; \
		exit 1; \
	fi
	PYTHONPATH=src:. $(PY) -m newsx.cli brief --event $(EVENT)

benchmark:
	PYTHONPATH=src:scripts:. $(PY) scripts/evaluate_all.py

web:
	PYTHONPATH=src:. $(PY) -m newsx.web

.PHONY: test run transparency brief benchmark web
