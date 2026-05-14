.PHONY: venv install test fmt

VENV ?= .venv
PY := $(VENV)/bin/python

venv:
	python -m pip install -U pip uv
	UV_PROJECT_ENVIRONMENT=$(PWD)/$(VENV) uv sync --frozen

install: venv

test: install
	python -m pip install -U uv
	UV_PROJECT_ENVIRONMENT=$(PWD)/$(VENV) uv sync --frozen --group dev
	$(PY) -m pytest -q
