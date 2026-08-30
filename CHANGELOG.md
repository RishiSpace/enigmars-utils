# Changelog

## 1.0.0

First production release of Enigmars Util.

- Host probe: distro, desktop, family-first package manager, bootloader, GPU, firewall
- Tweaks with preview/confirm/undo, including a Windows-convert pack
- Package catalog, search, install/remove, system update via pkexec helper
- Kernel inventory (installed + repo-available), install/remove with safety checks
- EnigmarsOS kernel transactions restage the ESP on install **and** remove
- Drivers page with NVIDIA install when an NVIDIA GPU is present
- GUI never runs as root
