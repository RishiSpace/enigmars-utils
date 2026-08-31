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
make pkg-arch   # packaging/arch/enigmars-utils-1.0.0-1-any.pkg.tar.zst
```

GitHub Actions (`.github/workflows/packages.yml`) builds the `.deb` and `.rpm` on
every push to `main` and publishes them on the **Latest** GitHub Release. Version
tags (`v1.0.0`, …) get a matching named release.

## Debian / Ubuntu (`.deb`)

```bash
./packaging/debian/build-deb.sh
sudo dpkg -i dist/enigmars-utils_1.0.0_all.deb
sudo apt-get install -f   # if python3-pyside6 is missing
```

Depends on `python3-pyside6` (Ubuntu 24.04+) and `policykit-1` or `polkitd`.

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
