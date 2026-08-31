# Decisions

| Decision | Rationale |
|---|---|
| PySide6 Widgets | Existing EnigmarsOS welcome stack; table UI; shortest production path |
| Family-first probe | Avoid picking a random PM binary |
| TOML catalogs + stdlib `tomllib` | No PyYAML; humans can add tweaks |
| pkexec helper, not D-Bus daemon | Smaller attack surface |
| ESP sync via existing script | Avoids EnigmarsOS emergency-mode bug |
| No general AUR / no custom kernels in v1 | Supply-chain and bricking |
| Allowlisted yay/paru bootstrap from GitHub | Official repos omit them; no PKGBUILD execution |
| Windows pack = composed key tweaks | No Plasma panel rewrite until reversible |
| AMOLED QSS always | Card/hero objectNames are unreadable on stock Fusion |
| No `/etc/xdg/autostart` in this package | User opt-in on Home; distro wrapper can still autostart |
