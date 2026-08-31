#!/bin/sh
# Build a noarch .rpm from this checkout.
# Output: dist/enigmars-utils-<version>-1.*.noarch.rpm
set -eu

ROOT="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
VERSION="$(python3 -c "import tomllib; print(tomllib.load(open('${ROOT}/pyproject.toml','rb'))['project']['version'])")"
TOP="${TMPDIR:-/tmp}/enigmars-utils-rpm-$$"
OUT="${ROOT}/dist"

if ! command -v rpmbuild >/dev/null 2>&1; then
  echo "build-rpm.sh: rpmbuild not found (install rpm-build / rpm)." >&2
  exit 1
fi

cleanup() { rm -rf "$TOP"; }
trap cleanup EXIT

umask 022
mkdir -p "$OUT" "$TOP/SPECS" "$TOP/BUILD" "$TOP/RPMS" "$TOP/SOURCES" "$TOP/SRPMS"

sed "s/@@VERSION@@/${VERSION}/" "$ROOT/packaging/rpm/enigmars-utils.spec" \
  > "$TOP/SPECS/enigmars-utils.spec"

rpmbuild -bb \
  --define "_topdir ${TOP}" \
  --define "srcroot ${ROOT}" \
  --define "dist %{nil}" \
  "$TOP/SPECS/enigmars-utils.spec"

find "$TOP/RPMS" -name '*.rpm' -exec cp -a {} "$OUT/" \;
echo "Built RPM(s):"
ls -lh "$OUT"/enigmars-utils-*.rpm
