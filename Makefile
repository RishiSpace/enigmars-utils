PYTHON ?= python3
export PYTHONPATH := src

.PHONY: test run helper-check install deb rpm pkg-arch

test:
	$(PYTHON) -m unittest discover -s tests -v

run:
	$(PYTHON) -m enigmars_util

helper-check:
	$(PYTHON) -m enigmars_util_helper pkg-update; test $$? -eq 2 || true

install:
	./scripts/install.sh

deb:
	./packaging/debian/build-deb.sh

rpm:
	./packaging/rpm/build-rpm.sh

pkg-arch:
	cd packaging/arch && makepkg -f -p PKGBUILD.local
