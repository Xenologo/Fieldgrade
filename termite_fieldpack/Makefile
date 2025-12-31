.PHONY: venv test lint

venv:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

test:
	python -m unittest -q

