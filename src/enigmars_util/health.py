"""PC Health rows for the Home dashboard. Pure assessment, no Qt."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from enigmars_util.profile import HostProfile
from enigmars_util.secureboot import SecureBootStatus

LEVELS = ("ok", "warn", "bad", "unknown")


@dataclass(frozen=True)
class HealthItem:
    id: str
    label: str
    detail: str
    level: str  # ok | warn | bad | unknown
    page: str


def _modules_present(release: str) -> bool:
    return Path(f"/usr/lib/modules/{release}").is_dir() or Path(f"/lib/modules/{release}").is_dir()


def _apparmor_on() -> bool:
    lsm = Path("/sys/kernel/security/lsm")
    try:
        if lsm.is_file() and "apparmor" in lsm.read_text(encoding="utf-8", errors="replace"):
            return True
    except OSError:
        pass
    return Path("/sys/module/apparmor").is_dir()


def gpu_item(profile: HostProfile) -> HealthItem:
    if not profile.gpus:
        return HealthItem("gpu", "GPU drivers", "No GPU reported", "warn", "drivers")
    nvidia = any(g.vendor == "nvidia" for g in profile.gpus)
    vendors = sorted({g.vendor for g in profile.gpus if g.vendor != "unknown"} or {"unknown"})
    names = ", ".join(vendors)
    if nvidia and not profile.nvidia_loaded:
        return HealthItem(
            "gpu",
            "GPU drivers",
            f"{names}: NVIDIA module not loaded",
            "warn",
            "drivers",
        )
    if nvidia:
        return HealthItem("gpu", "GPU drivers", f"{names}: proprietary loaded", "ok", "drivers")
    return HealthItem("gpu", "GPU drivers", f"{names} (Mesa)", "ok", "drivers")


def kernel_item(profile: HostProfile, *, modules_present: bool | None = None) -> HealthItem:
    release = profile.kernel_release or "unknown"
    present = _modules_present(release) if modules_present is None else modules_present
    if not present:
        return HealthItem("kernel", "Kernel", f"{release} (modules missing)", "bad", "kernel")
    return HealthItem("kernel", "Kernel", release, "ok", "kernel")


def secure_boot_item(sb: SecureBootStatus) -> HealthItem:
    if not sb.uefi:
        return HealthItem("secure-boot", "Secure Boot", "Not UEFI", "unknown", "secure-boot")
    if sb.secure_boot and sb.setup_mode:
        return HealthItem("secure-boot", "Secure Boot", "On, but Setup Mode still active", "warn", "secure-boot")
    if sb.secure_boot and sb.enrolled:
        ms = " · Microsoft keys" if sb.microsoft_keys else ""
        return HealthItem("secure-boot", "Secure Boot", f"Enabled{ms}", "ok", "secure-boot")
    if sb.secure_boot:
        return HealthItem("secure-boot", "Secure Boot", "Enabled (sbctl not enrolled)", "warn", "secure-boot")
    if sb.setup_mode:
        return HealthItem("secure-boot", "Secure Boot", "Setup Mode (keys not protecting boot)", "warn", "secure-boot")
    if sb.secure_boot is False:
        return HealthItem("secure-boot", "Secure Boot", "Disabled", "warn", "secure-boot")
    return HealthItem("secure-boot", "Secure Boot", "Unknown", "unknown", "secure-boot")


def security_item(profile: HostProfile, *, apparmor: bool | None = None) -> HealthItem:
    aa = _apparmor_on() if apparmor is None else apparmor
    fw = profile.firewall
    parts: list[str] = []
    level = "ok"
    if fw == "active":
        parts.append("UFW on")
    elif fw == "inactive":
        parts.append("UFW off")
        level = "warn"
    else:
        parts.append("firewall unknown")
        if level == "ok":
            level = "unknown"
    if aa:
        parts.append("AppArmor on")
    else:
        parts.append("AppArmor off")
        if level == "ok":
            level = "warn"
    return HealthItem("security", "Security", " · ".join(parts), level, "home")


def overall_level(items: list[HealthItem]) -> str:
    order = {"ok": 0, "unknown": 1, "warn": 2, "bad": 3}
    worst = 0
    label = "ok"
    for item in items:
        rank = order.get(item.level, 1)
        if rank > worst:
            worst = rank
            label = item.level
    return label


def assess(
    profile: HostProfile,
    sb: SecureBootStatus,
    *,
    modules_present: bool | None = None,
    apparmor: bool | None = None,
) -> list[HealthItem]:
    return [
        gpu_item(profile),
        kernel_item(profile, modules_present=modules_present),
        secure_boot_item(sb),
        security_item(profile, apparmor=apparmor),
    ]
