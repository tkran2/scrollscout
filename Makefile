# Common tasks. `make check` before a pull request; the others rebuild the published results.
PYTHON ?= python

.PHONY: install check test lint docs figures report

install:
	$(PYTHON) -m pip install -e ".[figures,test]"

check: lint test

test:
	$(PYTHON) -m pytest -q tests

lint:
	$(PYTHON) -m pyflakes scrollscout scripts tests

docs:
	$(PYTHON) -I scripts/summarize_atlas.py atlas
	$(PYTHON) -I scripts/update_docs.py

figures:
	$(PYTHON) -I scripts/make_figures.py

report: figures
	$(PYTHON) -I scripts/make_report.py
