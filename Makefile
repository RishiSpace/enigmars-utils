PYTHON ?= python3
export PYTHONPATH := src

.PHONY: test run helper-check install

test:
	$(PYTHON) -m unittest discover -s tests -v

run:
	$(PYTHON) -m enigmars_util

helper-check:
	$(PYTHON) -m enigmars_util_helper pkg-update; test $$? -eq 2 || true

install:
	./scripts/install.sh
