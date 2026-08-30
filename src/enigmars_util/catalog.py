from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from enigmars_util.paths import data_root
from enigmars_util.profile import HostProfile


def _load_tomls(directory: Path) -> list[dict[str, Any]]:
    if not directory.is_dir():
        return []
    docs: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.toml")):
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        if not isinstance(data, dict):
            continue
        data["_source"] = str(path)
        docs.append(data)
    return docs


@dataclass(frozen=True)
class Tweak:
    id: str
    title: str
    summary: str
    group: str
    audience: tuple[str, ...]
    risk: str
    desktops: tuple[str, ...]
    families: tuple[str, ...]
    apply: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class CatalogApp:
    id: str
    title: str
    summary: str
    group: str
    packages: dict[str, str]
    flatpak: str | None


@dataclass(frozen=True)
class KernelFlavor:
    package: str
    label: str
    recommended: bool
    headers: str | None


def load_tweaks() -> list[Tweak]:
    out: list[Tweak] = []
    for doc in _load_tomls(data_root() / "tweaks"):
        tid = str(doc.get("id") or "")
        if not tid:
            continue
        apply = doc.get("apply") or []
        if not isinstance(apply, list):
            continue
        out.append(
            Tweak(
                id=tid,
                title=str(doc.get("title") or tid),
                summary=str(doc.get("summary") or ""),
                group=str(doc.get("group") or "General"),
                audience=tuple(doc.get("audience") or ("general",)),
                risk=str(doc.get("risk") or "low"),
                desktops=tuple(d.lower() for d in (doc.get("desktop") or ())),
                families=tuple(doc.get("family") or ()),
                apply=tuple(a for a in apply if isinstance(a, dict)),
            )
        )
    return out


def tweaks_for(profile: HostProfile, tweaks: Iterable[Tweak] | None = None) -> list[Tweak]:
    items = list(tweaks) if tweaks is not None else load_tweaks()
    matched: list[Tweak] = []
    for t in items:
        if t.desktops and profile.desktop not in t.desktops and "any" not in t.desktops:
            continue
        if t.families and profile.family not in t.families and profile.distro_id not in t.families:
            continue
        matched.append(t)
    return matched


def load_apps() -> list[CatalogApp]:
    out: list[CatalogApp] = []
    for doc in _load_tomls(data_root() / "catalog"):
        cid = str(doc.get("id") or "")
        if not cid:
            continue
        pkgs = doc.get("packages") or {}
        if not isinstance(pkgs, dict):
            pkgs = {}
        flatpak = doc.get("flatpak")
        out.append(
            CatalogApp(
                id=cid,
                title=str(doc.get("title") or cid),
                summary=str(doc.get("summary") or ""),
                group=str(doc.get("group") or "Apps"),
                packages={str(k): str(v) for k, v in pkgs.items() if v},
                flatpak=str(flatpak) if flatpak else None,
            )
        )
    return out


def app_package_for(app: CatalogApp, profile: HostProfile) -> str | None:
    pkgs = app.packages
    return pkgs.get(profile.family) or pkgs.get(profile.distro_id) or pkgs.get(profile.native_pm)


def load_kernels(family: str) -> list[KernelFlavor]:
    path = data_root() / "kernels" / f"{family}.toml"
    if not path.is_file():
        return []
    with path.open("rb") as fh:
        doc = tomllib.load(fh)
    flavors = doc.get("kernel") or []
    out: list[KernelFlavor] = []
    if not isinstance(flavors, list):
        return out
    for item in flavors:
        if not isinstance(item, dict):
            continue
        pkg = str(item.get("package") or "")
        if not pkg:
            continue
        headers = item.get("headers")
        out.append(
            KernelFlavor(
                package=pkg,
                label=str(item.get("label") or pkg),
                recommended=bool(item.get("recommended")),
                headers=str(headers) if headers else None,
            )
        )
    return out
