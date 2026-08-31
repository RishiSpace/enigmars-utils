# Packaging Enigmars Utils

The install layout (no pip):

| Path | What |
|------|------|
| `/usr/bin/enigmars-util` | GUI wrapper |
| `/usr/libexec/enigmars-util-helper` | pkexec helper (this path is in the polkit policy) |
| `/usr/lib/enigmars-utils/` | Python packages |
| `/usr/share/enigmars-util/` | tweak/app/kernel catalogs |
| `/usr/share/polkit-1/actions/org.enigmars.util.policy` | polkit |

Build artifacts from a checkout:

```bash
make deb        # dist/enigmars-utils_1.0.0_all.deb
make rpm        # dist/enigmars-utils-1.0.0-1.noarch.rpm  (needs rpmbuild)
make appimage   # dist/Enigmars_Utils-1.0.0-x86_64.AppImage
make pkg-arch   # packaging/arch/enigmars-utils-1.0.0-1-any.pkg.tar.zst
```

GitHub Actions (`.github/workflows/packages.yml`) builds `.deb`, `.rpm`, and
`.AppImage` on every push to `main` and publishes them on the **Latest** GitHub
Release. Version tags (`v1.0.0`, …) get a matching named release.

The AppImage bundles Python, PySide6, the privileged helper, and the polkit
policy. The first kernel/package/sbctl action runs the helper via `pkexec`; as
root it copies the helper and policy into `/usr/libexec` and
`/usr/share/polkit-1` so later actions use the host package manager (`pacman`,
`apt`, `dnf`, …) and `sbctl`.

## Debian / Ubuntu (`.deb`)

```bash
./packaging/debian/build-deb.sh
sudo dpkg -i dist/enigmars-utils_1.0.0_all.deb
sudo apt-get install -f   # if python3-pyside6 is missing
```

Depends on PySide6 (`python3-pyside6` on Ubuntu 25.10+, or `pip install PySide6`
on 24.04) and `policykit-1` or `polkitd`. GitHub Actions installs PySide6 from
PyPI because Ubuntu 24.04 does not ship `python3-pyside6`.

This is a local binary package, not an upload to Debian/Ubuntu archives.

## Arch / EnigmarsOS / AUR

**Install this tree now** (no GitHub tag needed):

```bash
cd packaging/arch
makepkg -f -si -p PKGBUILD.local
```

**AUR (after the GitHub repo is public):**

1. Tag a release matching `pkgver`:

   ```bash
   git tag -s v1.0.0 -m "Enigmars Utils 1.0.0"
   git push origin v1.0.0
   ```

2. Put `packaging/arch/PKGBUILD` in an AUR clone and fill `sha256sums`:

   ```bash
   cd packaging/arch
   makepkg -g          # prints sha256sums=('...')
   makepkg --printsrcinfo > .SRCINFO
   ```

3. Publish:

   ```bash
   git clone ssh://aur@aur.archlinux.org/enigmars-utils.git
   # copy PKGBUILD and .SRCINFO, commit, git push
   ```

Use `PKGBUILD-git` for `enigmars-utils-git` (builds `main`). AUR sources must be **public**; a private GitHub repo will fail for everyone else.

## Version

Single source: `pyproject.toml` → `project.version`. Keep PKGBUILD `pkgver` and `packaging/debian/control` Version in sync when you release.
