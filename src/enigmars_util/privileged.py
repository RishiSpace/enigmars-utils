"""Unprivileged client for the pkexec helper. Streams output via QProcess or subprocess."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from enigmars_util.names import validate_package_list, validate_service, validate_verb
from enigmars_util.paths import HELPER_PATH


def helper_executable() -> Path | None:
    env = os.environ.get("ENIGMARS_UTIL_HELPER")
    if env:
        path = Path(env)
        return path if path.is_file() else None
    if HELPER_PATH.is_file() and os.access(HELPER_PATH, os.X_OK):
        return HELPER_PATH
    found = shutil.which("enigmars-util-helper")
    if found:
        return Path(found)
    return None


def pkexec_cmd(verb: str, args: list[str] | None = None) -> list[str]:
    verb = validate_verb(verb)
    args = list(args or [])
    helper = helper_executable()
    if helper is None:
        raise FileNotFoundError(
            "enigmars-util-helper is not installed (expected /usr/libexec/enigmars-util-helper)"
        )
    pkexec = shutil.which("pkexec")
    if not pkexec:
        raise FileNotFoundError("pkexec is not installed")
    return [pkexec, str(helper), verb, *args]


def pkg_install_cmd(names: list[str]) -> list[str]:
    names = validate_package_list(names)
    return pkexec_cmd("pkg-install", names)


def pkg_remove_cmd(names: list[str]) -> list[str]:
    names = validate_package_list(names)
    return pkexec_cmd("pkg-remove", names)


def pkg_update_cmd() -> list[str]:
    return pkexec_cmd("pkg-update")


def pkg_refresh_cmd() -> list[str]:
    return pkexec_cmd("pkg-refresh")


def kernel_sync_esp_cmd() -> list[str]:
    return pkexec_cmd("kernel-sync-esp")


def ufw_cmd(enable: bool) -> list[str]:
    return pkexec_cmd("ufw-enable" if enable else "ufw-disable")


def service_cmd(enable: bool, name: str) -> list[str]:
    name = validate_service(name)
    return pkexec_cmd("service-enable" if enable else "service-disable", [name])
