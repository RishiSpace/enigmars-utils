# Changelog

## Unreleased

- Secure Boot page: sbctl install/enrollment/enabled/Setup Mode status, firmware reboot with instructions, resume into the Secure Boot tab after login, enroll keys including Microsoft (`sbctl enroll-keys -m`)
- Packages page: Set up yay / Set up paru (pacman if present, otherwise clone+compile upstream GitHub)

## 1.0.0

First production release of Enigmars Util.

- Host probe: distro, desktop, family-first package manager, bootloader, GPU, firewall
- Tweaks with preview/confirm/undo, including a Windows-convert pack
- Package catalog, search, install/remove, system update via pkexec helper
- Kernel inventory (installed + repo-available), install/remove with safety checks
- EnigmarsOS kernel transactions restage the ESP on install **and** remove
- Drivers page with NVIDIA install when an NVIDIA GPU is present
- GUI never runs as root
