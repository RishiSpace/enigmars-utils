#!/bin/sh
# Build a .deb from this checkout (no dh_make required).
# Output: dist/enigmars-utils_<version>_all.deb
set -eu

ROOT="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
VERSION="$(python3 -c "import tomllib; print(tomllib.load(open('${ROOT}/pyproject.toml','rb'))['project']['version'])")"
PKG=enigmars-utils
DEB_NAME="${PKG}_${VERSION}_all.deb"
STAGE="${TMPDIR:-/tmp}/enigmars-utils-deb-$$"
OUT="${ROOT}/dist"

cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

umask 022
mkdir -p "$STAGE" "$OUT"
DESTDIR="$STAGE" PREFIX=/usr "$ROOT/scripts/install.sh"

# Python bytecode is not needed in the package
find "$STAGE" -type d -name '__pycache__' -prune -exec rm -rf {} +

install -d "$STAGE/DEBIAN"
sed "s/^Version:.*/Version: ${VERSION}/" "$ROOT/packaging/debian/control" > "$STAGE/DEBIAN/control"
cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi
exit 0
EOF
chmod 755 "$STAGE/DEBIAN/postinst"

# Installed-Size in KiB
size="$(du -sk "$STAGE" | awk '{print $1}')"
printf '\nInstalled-Size: %s\n' "$size" >> "$STAGE/DEBIAN/control"

if command -v dpkg-deb >/dev/null 2>&1; then
  dpkg-deb --root-owner-group --build "$STAGE" "$OUT/$DEB_NAME"
else
  # Portable fallback: a .deb is an ar archive of debian-binary + control + data.
  work="$STAGE/.deb-pack"
  mkdir -p "$work"
  (
    cd "$STAGE"
    tar --owner=root --group=root --mtime='UTC 1970-01-01' -czf "$work/data.tar.gz" usr
    tar --owner=root --group=root --mtime='UTC 1970-01-01' -czf "$work/control.tar.gz" -C DEBIAN .
  )
  printf '2.0\n' > "$work/debian-binary"
  (
    cd "$work"
    ar r "$OUT/$DEB_NAME" debian-binary control.tar.gz data.tar.gz
  )
fi

echo "Built $OUT/$DEB_NAME"
ls -lh "$OUT/$DEB_NAME"
