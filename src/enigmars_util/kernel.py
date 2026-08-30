from __future__ import annotations

import platform
from dataclasses import dataclass

from enigmars_util.catalog import KernelFlavor, load_kernels
from enigmars_util.packages import PackageBackend
from enigmars_util.profile import HostProfile


class KernelSafetyError(Exception):
    pass


@dataclass(frozen=True)
class KernelRow:
    flavor: KernelFlavor
    installed: bool
    running: bool
    version: str


def running_matches(package: str, release: str) -> bool:
    rel = release.lower()
    pkg = package.lower()
    if pkg == "linux-enigmarsos":
        return "enigmarsos" in rel
    if pkg.startswith("linux-"):
        token = pkg.split("linux-", 1)[1]
        return bool(token) and token in rel
    if pkg == "linux":
        flavors = ("zen", "lts", "hardened", "enigmarsos", "cachyos")
        return not any(f in rel for f in flavors)
    return pkg in rel


def inventory(profile: HostProfile, backend: PackageBackend) -> list[KernelRow]:
    flavors = load_kernels(profile.family)
    release = profile.kernel_release or platform.release()
    installed = backend.installed_versions()
    names = [f.package for f in flavors]
    available = backend.available_set(names) | set(installed)
    rows: list[KernelRow] = []
    for flavor in flavors:
        inst = flavor.package in installed
        if not inst and flavor.package not in available:
            continue
        rows.append(
            KernelRow(
                flavor,
                inst,
                running_matches(flavor.package, release),
                installed.get(flavor.package, ""),
            )
        )
    if not rows:
        rows.append(
            KernelRow(
                KernelFlavor(package="(running)", label=f"Running {release}", recommended=True, headers=None),
                True,
                True,
                release,
            )
        )
    return rows


def packages_to_install(row: KernelRow) -> list[str]:
    names = [row.flavor.package]
    if row.flavor.headers:
        names.append(row.flavor.headers)
    return names


def packages_to_remove(row: KernelRow, installed_versions: dict[str, str]) -> list[str]:
    names = [row.flavor.package]
    if row.flavor.headers and row.flavor.headers in installed_versions:
        names.append(row.flavor.headers)
    return names


def assert_can_remove(rows: list[KernelRow], target: KernelRow) -> None:
    if not target.installed:
        raise KernelSafetyError(f"{target.flavor.package} is not installed")
    installed = [r for r in rows if r.installed and r.flavor.package != "(running)"]
    if len(installed) <= 1:
        raise KernelSafetyError("refusing to remove the last installed kernel")
    if target.running and len(installed) <= 1:
        raise KernelSafetyError("refusing to remove the running kernel")
    others = [r for r in installed if r.flavor.package != target.flavor.package]
    if target.running and not others:
        raise KernelSafetyError("refusing to remove the running kernel with no fallback")
