"""Read-only host probe. No privilege, no shell pipelines."""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path
from typing import Mapping, Protocol

from enigmars_util.profile import Gpu, HostProfile

FAMILY_BY_ID: dict[str, str] = {
    "enigmarsos": "arch",
    "arch": "arch",
    "archlinux": "arch",
    "manjaro": "arch",
    "endeavouros": "arch",
    "cachyos": "arch",
    "garuda": "arch",
    "artix": "arch",
    "archcraft": "arch",
    "ubuntu": "debian",
    "debian": "debian",
    "linuxmint": "debian",
    "pop": "debian",
    "elementary": "debian",
    "zorin": "debian",
    "kali": "debian",
    "raspbian": "debian",
    "devuan": "debian",
    "fedora": "fedora",
    "rhel": "fedora",
    "centos": "fedora",
    "rocky": "fedora",
    "almalinux": "fedora",
    "nobara": "fedora",
    "ol": "fedora",
    "opensuse-tumbleweed": "suse",
    "opensuse-leap": "suse",
    "opensuse": "suse",
    "sle": "suse",
    "void": "void",
    "alpine": "alpine",
    "nixos": "nix",
    "gentoo": "gentoo",
}

PM_BY_FAMILY: dict[str, str] = {
    "arch": "pacman",
    "debian": "apt",
    "fedora": "dnf",
    "suse": "zypper",
    "void": "xbps",
    "alpine": "apk",
    "nix": "nix",
    "gentoo": "portage",
}

PM_EVIDENCE: dict[str, tuple[str, str]] = {
    # binary name, database/dir that must exist
    "pacman": ("pacman", "/var/lib/pacman"),
    "apt": ("apt-get", "/var/lib/dpkg"),
    "dnf": ("dnf", "/var/lib/rpm"),
    "zypper": ("zypper", "/var/lib/rpm"),
    "xbps": ("xbps-install", "/var/db/xbps"),
    "apk": ("apk", "/lib/apk"),
}

DESKTOP_TOKENS: dict[str, str] = {
    "kde": "plasma",
    "plasma": "plasma",
    "gnome": "gnome",
    "ubuntu": "gnome",
    "x-cinnamon": "cinnamon",
    "cinnamon": "cinnamon",
    "xfce": "xfce",
    "mate": "mate",
    "budgie": "budgie",
    "hyprland": "hyprland",
    "sway": "sway",
    "cosmic": "cosmic",
    "lxqt": "lxqt",
    "lxde": "lxde",
    "i3": "i3",
    "niri": "niri",
    "wayfire": "wayfire",
}


class FS(Protocol):
    def read(self, path: str) -> str | None: ...
    def exists(self, path: str) -> bool: ...
    def which(self, name: str) -> str | None: ...


class RealFS:
    def read(self, path: str) -> str | None:
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def which(self, name: str) -> str | None:
        return shutil.which(name)


def parse_os_release(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key] = val
    return out


def family_of(distro_id: str, like: tuple[str, ...]) -> str:
    ident = distro_id.lower().strip()
    if ident in FAMILY_BY_ID:
        return FAMILY_BY_ID[ident]
    for item in like:
        token = item.lower().strip()
        if token in FAMILY_BY_ID:
            return FAMILY_BY_ID[token]
    return "unknown"


def parse_like(raw: str) -> tuple[str, ...]:
    if not raw.strip():
        return ()
    return tuple(p for p in raw.replace(",", " ").split() if p)


def desktop_of(environ: Mapping[str, str]) -> str:
    for key in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION"):
        raw = environ.get(key, "") or ""
        for token in raw.replace(";", ":").split(":"):
            t = token.strip().lower()
            if not t:
                continue
            if t in DESKTOP_TOKENS:
                return DESKTOP_TOKENS[t]
            # "plasma:wayland" already split; "kde-plasma" fallback
            for name, mapped in DESKTOP_TOKENS.items():
                if name in t:
                    return mapped
    return "unknown"


def session_of(environ: Mapping[str, str]) -> str:
    raw = (environ.get("XDG_SESSION_TYPE") or "").strip().lower()
    if raw in {"wayland", "x11", "tty", "mir"}:
        return raw
    return "unknown"


def confirm_pm(family: str, fs: FS) -> str:
    wanted = PM_BY_FAMILY.get(family)
    if wanted and wanted in PM_EVIDENCE:
        binary, db = PM_EVIDENCE[wanted]
        if fs.which(binary) and fs.exists(db):
            return wanted
        if wanted == "dnf" and fs.which("dnf5") and fs.exists(db):
            return "dnf"
    # immutable / special
    if family == "nix":
        return "nix"
    if family == "gentoo":
        return "portage" if fs.which("emerge") else "none"
    return "none"


def is_immutable(fs: FS, distro_id: str, family: str) -> bool:
    if family == "nix" or distro_id == "nixos":
        return True
    if fs.exists("/run/ostree-booted"):
        return True
    if fs.which("rpm-ostree") and fs.exists("/usr/bin/rpm-ostree"):
        # present on Silverblue/Kinoite; treat as immutable if ostree booted OR ostree dir
        if fs.exists("/ostree/repo"):
            return True
    return False


def detect_bootloader(fs: FS, distro_id: str) -> str:
    limine_paths = (
        "/boot/efi/limine.conf",
        "/boot/efi/EFI/EnigmarsOS/limine.conf",
        "/boot/efi/EFI/BOOT/limine.conf",
        "/boot/limine.conf",
        "/boot/limine/limine.conf",
        "/efi/limine.conf",
    )
    if any(fs.exists(p) for p in limine_paths) or distro_id == "enigmarsos":
        if any(fs.exists(p) for p in limine_paths) or fs.which("limine"):
            return "limine"
    if fs.exists("/boot/loader/loader.conf") or fs.which("bootctl"):
        if fs.exists("/boot/loader/loader.conf"):
            return "systemd-boot"
    if fs.exists("/boot/grub/grub.cfg") or fs.exists("/boot/grub2/grub.cfg"):
        return "grub"
    if fs.which("grub-mkconfig") or fs.which("grub2-mkconfig"):
        return "grub"
    if fs.which("limine"):
        return "limine"
    return "unknown"


def _gpu_vendor(line: str) -> str:
    low = line.lower()
    if "nvidia" in low:
        return "nvidia"
    if "amd" in low or "advanced micro devices" in low or "radeon" in low:
        return "amd"
    if "intel" in low:
        return "intel"
    return "unknown"


def parse_lspci(text: str) -> tuple[Gpu, ...]:
    gpus: list[Gpu] = []
    for line in text.splitlines():
        if not any(tag in line for tag in ("VGA", "3D", "Display")):
            continue
        gpus.append(Gpu(pci=line.strip(), vendor=_gpu_vendor(line)))
    return tuple(gpus)


def firewall_state(fs: FS) -> str:
    ufw = fs.which("ufw")
    if not ufw:
        return "unknown"
    # /etc/ufw/ufw.conf ENABLED=yes is cheaper and avoids subprocess
    conf = fs.read("/etc/ufw/ufw.conf") or ""
    for line in conf.splitlines():
        if line.strip().startswith("ENABLED="):
            val = line.split("=", 1)[1].strip().lower()
            if val == "yes":
                return "active"
            if val == "no":
                return "inactive"
    return "unknown"


def probe_host(
    *,
    fs: FS | None = None,
    environ: Mapping[str, str] | None = None,
    os_release_text: str | None = None,
    kernel_release: str | None = None,
    lspci_text: str | None = None,
) -> HostProfile:
    fs = fs or RealFS()
    environ = environ if environ is not None else os.environ

    text = os_release_text
    if text is None:
        text = fs.read("/etc/os-release") or fs.read("/usr/lib/os-release") or ""
    fields = parse_os_release(text)
    distro_id = (fields.get("ID") or "unknown").strip().lower()
    like = parse_like(fields.get("ID_LIKE") or "")
    pretty = fields.get("PRETTY_NAME") or fields.get("NAME") or distro_id
    version_id = fields.get("VERSION_ID") or ""
    family = family_of(distro_id, like)
    native_pm = confirm_pm(family, fs)
    immutable = is_immutable(fs, distro_id, family)
    can_mutate = (not immutable) and native_pm in {"pacman", "apt", "dnf", "zypper", "xbps", "apk"}

    gpus: tuple[Gpu, ...] = ()
    if lspci_text is not None:
        gpus = parse_lspci(lspci_text)
    elif fs.which("lspci"):
        # Best-effort; ignore failures
        try:
            import subprocess

            out = subprocess.run(
                ["lspci", "-nn"],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
            if out.returncode == 0:
                gpus = parse_lspci(out.stdout)
        except (OSError, subprocess.TimeoutExpired):
            gpus = ()

    return HostProfile(
        distro_id=distro_id,
        distro_like=like,
        pretty_name=pretty,
        version_id=version_id,
        family=family,
        desktop=desktop_of(environ),
        session=session_of(environ),
        native_pm=native_pm,
        flatpak=bool(fs.which("flatpak")),
        snap=bool(fs.which("snap")),
        immutable=immutable,
        can_mutate_native=can_mutate,
        bootloader=detect_bootloader(fs, distro_id),
        kernel_release=kernel_release or platform.release(),
        gpus=gpus,
        nvidia_loaded=fs.exists("/proc/driver/nvidia/version"),
        vulkan_tools=bool(fs.which("vulkaninfo")),
        firewall=firewall_state(fs),
        enigmarsos=distro_id == "enigmarsos" or "enigmarsos" in like,
    )
