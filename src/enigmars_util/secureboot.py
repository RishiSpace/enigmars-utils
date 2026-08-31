"""Secure Boot status via sbctl and EFI variables. No privilege required to probe."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from enigmars_util import autostart
from enigmars_util.paths import state_dir, xdg_config_home

EFI_DIR = Path("/sys/firmware/efi")
EFIVARS = EFI_DIR / "efivars"
RESUME_NAME = "secureboot-resume.json"
ONESHOT_NAME = "org.enigmars.Util-secureboot.desktop"
PHASES = frozenset({"enroll", "enable-sb"})


@dataclass(frozen=True)
class SecureBootStatus:
    uefi: bool
    sbctl_present: bool
    sbctl_installed: bool
    secure_boot: bool | None
    setup_mode: bool | None
    enrolled: bool
    microsoft_keys: bool
    guid: str
    vendors: tuple[str, ...]


def _efi_flag(prefix: str) -> bool | None:
    if not EFIVARS.is_dir():
        return None
    matches = sorted(EFIVARS.glob(f"{prefix}-*"))
    if not matches:
        return None
    try:
        data = matches[0].read_bytes()
    except OSError:
        return None
    if len(data) < 5:
        return None
    return data[4] == 1


def parse_sbctl_status(doc: dict[str, Any]) -> SecureBootStatus:
    vendors = tuple(str(v) for v in (doc.get("vendors") or []) if v)
    guid = str(doc.get("guid") or "")
    microsoft = any("microsoft" in v.lower() for v in vendors)
    installed = bool(doc.get("installed"))
    return SecureBootStatus(
        uefi=True,
        sbctl_present=True,
        sbctl_installed=installed,
        secure_boot=bool(doc.get("secure_boot")) if "secure_boot" in doc else None,
        setup_mode=bool(doc.get("setup_mode")) if "setup_mode" in doc else None,
        enrolled=installed and bool(guid),
        microsoft_keys=microsoft,
        guid=guid,
        vendors=vendors,
    )


def probe_secure_boot() -> SecureBootStatus:
    uefi = EFI_DIR.is_dir()
    present = bool(shutil.which("sbctl"))
    if present:
        try:
            proc = subprocess.run(
                ["sbctl", "status", "--json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=8,
            )
            if proc.returncode == 0 and (proc.stdout or "").strip():
                doc = json.loads(proc.stdout)
                if isinstance(doc, dict):
                    status = parse_sbctl_status(doc)
                    if not uefi:
                        status = SecureBootStatus(
                            uefi=False,
                            sbctl_present=True,
                            sbctl_installed=status.sbctl_installed,
                            secure_boot=None,
                            setup_mode=None,
                            enrolled=status.enrolled,
                            microsoft_keys=status.microsoft_keys,
                            guid=status.guid,
                            vendors=status.vendors,
                        )
                    return status
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
    if not uefi:
        return SecureBootStatus(
            uefi=False,
            sbctl_present=present,
            sbctl_installed=False,
            secure_boot=None,
            setup_mode=None,
            enrolled=False,
            microsoft_keys=False,
            guid="",
            vendors=(),
        )
    sb = _efi_flag("SecureBoot")
    setup = _efi_flag("SetupMode")
    return SecureBootStatus(
        uefi=True,
        sbctl_present=present,
        sbctl_installed=False,
        secure_boot=sb,
        setup_mode=setup,
        enrolled=False,
        microsoft_keys=False,
        guid="",
        vendors=(),
    )


def resume_path() -> Path:
    return state_dir() / RESUME_NAME


def oneshot_path() -> Path:
    return xdg_config_home() / "autostart" / ONESHOT_NAME


def load_resume_phase() -> str | None:
    path = resume_path()
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict):
        return None
    phase = str(doc.get("phase") or "")
    if phase not in PHASES:
        return None
    return phase


def save_resume_phase(phase: str) -> None:
    if phase not in PHASES:
        raise ValueError(f"invalid phase: {phase}")
    path = resume_path()
    path.write_text(json.dumps({"page": "secure-boot", "phase": phase}, indent=2), encoding="utf-8")


def clear_resume() -> None:
    path = resume_path()
    if path.exists():
        path.unlink()
    oneshot = oneshot_path()
    if oneshot.exists():
        oneshot.unlink()


def _launch_exec() -> str:
    exe = shutil.which("enigmars-util")
    if exe:
        return f"{exe} --page secure-boot"
    return "enigmars-util --page secure-boot"


def arm_resume(phase: str) -> None:
    """Remember the wizard step and auto-open this tab after the next login if needed."""
    save_resume_phase(phase)
    if autostart.enabled():
        return
    path = oneshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Enigmars Utils (Secure Boot setup)\n"
        f"Exec={_launch_exec()}\n"
        "Icon=enigmarsos\n"
        "X-KDE-autostart-phase=1\n"
        "X-GNOME-Autostart-enabled=true\n",
        encoding="utf-8",
    )


def consume_oneshot() -> None:
    path = oneshot_path()
    if path.exists():
        path.unlink()


SETUP_MODE_INSTRUCTIONS = (
    "The firmware must be in Setup Mode so new keys can be enrolled.\n\n"
    "After the machine restarts into firmware setup:\n"
    "1. Open the Secure Boot / Key Management menu "
    "(often under Security or Boot).\n"
    "2. Enter Setup Mode. Names vary: “Clear Secure Boot keys”, "
    "“Reset to Setup Mode”, or “Delete all Secure Boot variables”.\n"
    "3. Save and exit so the OS boots again.\n\n"
    "Enigmars Utils will open on this page after login."
)

ENABLE_SB_INSTRUCTIONS = (
    "Keys are enrolled (including Microsoft keys for GPU firmware and dual-boot).\n\n"
    "After the machine restarts into firmware setup:\n"
    "1. Enable Secure Boot.\n"
    "2. Leave Setup Mode if it is still listed as on "
    "(enrolling the Platform Key usually turns it off).\n"
    "3. Save and exit.\n\n"
    "Enigmars Utils will open on this page after login so you can confirm the result."
)
