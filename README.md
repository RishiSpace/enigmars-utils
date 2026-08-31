# Enigmars Util

Qt landing hub for Linux. Detects the distro, desktop, and package manager, then
offers Windows-convert tweaks, package actions, and kernel management.

Version **1.0.0**. EnigmarsOS is first-class (Plasma 6, pacman, Limine, ESP
kernel staging). The same binary works on other families by probing the host.

The GUI never runs as root. Package, kernel, and firewall changes go through
`pkexec /usr/libexec/enigmars-util-helper`.

## Run from a checkout (UI only)

```bash
make run
make test
```

Privileged buttons need the helper installed.

## Packages (.deb and Arch/AUR)

```bash
make deb        # dist/enigmars-utils_*.deb
make rpm        # dist/enigmars-utils-*.noarch.rpm
make pkg-arch   # packaging/arch/enigmars-utils-*.pkg.tar.zst
```

Pushes to `main` also build `.deb` + `.rpm` on GitHub Actions and attach them to
the **Latest** release. See [docs/PACKAGING.md](docs/PACKAGING.md).

## Install (Arch / EnigmarsOS)

From this repo:

```bash
sudo ./scripts/install.sh
# or
cd packaging/arch && makepkg -si -p PKGBUILD.local
```

Then launch **Enigmars Util** from the app menu, or `enigmars-util`.

Enable “Show on login” on the Home page if you want it as a welcome screen.
This package does not force autostart.

On EnigmarsOS, point `enigmarsos-welcome` at `enigmars-util` (wrapper or
`Depends: enigmars-util`).

## Security

- No `shell=True`
- Package names validated before they reach the helper
- Catalogs cannot run shell
- Helper refuses non-root, unknown verbs, and extra arguments
- EnigmarsOS kernel install/remove restages the ESP via `sync-esp-boot.sh`
