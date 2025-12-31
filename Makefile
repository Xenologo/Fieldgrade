.PHONY: venv install test fmt

VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(PY) -m pip

venv:
	python -m venv $(VENV)
	$(PIP) install -U pip

install: venv
	$(PIP) install -r requirements.txt
	$(PIP) install -e termite_fieldpack
	$(PIP) install -e mite_ecology
	$(PIP) install -e fieldgrade_ui

test: install
	$(PIP) install -r requirements-dev.txt
	$(PY) -m pytest -q

