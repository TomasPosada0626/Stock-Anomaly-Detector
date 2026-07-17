PYTHON ?= .venv/Scripts/python

.PHONY: dev test lint format coverage e2e security scheduler

dev:
	$(PYTHON) -m streamlit run src/app.py

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests

format:
	$(PYTHON) -m black src tests

coverage:
	$(PYTHON) -m pytest --cov=src --cov-report=term-missing

e2e:
	$(PYTHON) -m pytest tests/e2e -q

security:
	$(PYTHON) -m bandit -r src -ll
	$(PYTHON) -m pip_audit -r requirements/app.txt

scheduler:
	$(PYTHON) scripts/run_scheduler.py
