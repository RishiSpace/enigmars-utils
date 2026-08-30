from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Gpu:
    pci: str
    vendor: str  # nvidia | amd | intel | unknown


@dataclass(frozen=True)
class HostProfile:
    distro_id: str
    distro_like: tuple[str, ...]
    pretty_name: str
    version_id: str
    family: str
    desktop: str
    session: str
    native_pm: str
    flatpak: bool
    snap: bool
    immutable: bool
    can_mutate_native: bool
    bootloader: str
    kernel_release: str
    gpus: tuple[Gpu, ...] = field(default_factory=tuple)
    nvidia_loaded: bool = False
    vulkan_tools: bool = False
    firewall: str = "unknown"  # active | inactive | unknown
    enigmarsos: bool = False

    @property
    def native_pm_label(self) -> str:
        labels = {
            "pacman": "pacman",
            "apt": "APT",
            "dnf": "DNF",
            "zypper": "Zypper",
            "xbps": "xbps",
            "apk": "apk",
            "nix": "Nix",
            "portage": "Portage",
            "none": "none",
        }
        return labels.get(self.native_pm, self.native_pm)
