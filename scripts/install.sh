#!/bin/sh
# Install Enigmars Util (GUI + pkexec helper + catalogs + polkit policy).
# Usage:
#   sudo ./scripts/install.sh
#   DESTDIR=/tmp/pkg PREFIX=/usr ./scripts/install.sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
PREFIX="${PREFIX:-/usr}"
DESTDIR="${DESTDIR:-}"

if [ "$(id -u)" -ne 0 ] && [ -z "$DESTDIR" ]; then
  echo "install.sh: run as root, or set DESTDIR for packaging." >&2
  exit 1
fi

python3 -m pip install \
  --disable-pip-version-check \
  --no-build-isolation \
  --no-deps \
  --ignore-installed \
  --prefix="$PREFIX" \
  --root="${DESTDIR:-/}" \
  "$ROOT"

share="${DESTDIR}${PREFIX}/share/enigmars-util"
install -d "$share"
cp -a "$ROOT/data/tweaks" "$ROOT/data/catalog" "$ROOT/data/kernels" "$ROOT/data/branding" "$ROOT/data/icons" "$share/"

install -Dm644 "$ROOT/data/desktop/org.enigmars.Util.desktop" \
  "${DESTDIR}${PREFIX}/share/applications/org.enigmars.Util.desktop"
# Same mark as EnigmarsOS, under both the OS icon name and this app's id.
install -Dm644 "$ROOT/data/icons/EnigmarsOS.svg" \
  "${DESTDIR}${PREFIX}/share/icons/hicolor/scalable/apps/enigmarsos.svg"
install -Dm644 "$ROOT/data/icons/EnigmarsOS.svg" \
  "${DESTDIR}${PREFIX}/share/icons/hicolor/scalable/apps/org.enigmars.Util.svg"
install -Dm644 "$ROOT/data/icons/EnigmarsOS.png" \
  "${DESTDIR}${PREFIX}/share/icons/hicolor/256x256/apps/enigmarsos.png"
install -Dm644 "$ROOT/data/icons/EnigmarsOS.png" \
  "${DESTDIR}${PREFIX}/share/pixmaps/enigmarsos.png"
install -Dm644 "$ROOT/data/polkit/org.enigmars.util.policy" \
  "${DESTDIR}${PREFIX}/share/polkit-1/actions/org.enigmars.util.policy"

install -d "${DESTDIR}${PREFIX}/libexec"
helper_src="${DESTDIR}${PREFIX}/bin/enigmars-util-helper"
if [ -e "$helper_src" ] || [ -L "$helper_src" ]; then
  ln -sfn "${PREFIX}/bin/enigmars-util-helper" \
    "${DESTDIR}${PREFIX}/libexec/enigmars-util-helper"
else
  install -Dm755 "$ROOT/packaging/libexec/enigmars-util-helper" \
    "${DESTDIR}${PREFIX}/libexec/enigmars-util-helper"
fi

echo "Installed to ${DESTDIR}${PREFIX}"
