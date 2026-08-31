"""Allowlisted AUR helper bootstrap (yay, paru).

Official pacman repos do not ship these. The privileged helper may install
them from the distro sync db when present, otherwise clone the upstream
GitHub tree and compile. No general AUR, no PKGBUILD execution.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from enigmars_util.names import ALLOWED_AUR_HELPERS, validate_aur_helper

__all__ = [
    "ALLOWED_AUR_HELPERS",
    "AurHelperSpec",
    "SPECS",
    "installed_path",
    "spec_for",
]


@dataclass(frozen=True)
class AurHelperSpec:
    name: str
    git_url: str
    pacman_deps: tuple[str, ...]
    kind: str  # make | cargo
    binary: str
    marker: str


SPECS: dict[str, AurHelperSpec] = {
    "yay": AurHelperSpec(
        name="yay",
        git_url="https://github.com/Jguer/yay.git",
        pacman_deps=("git", "base-devel", "go"),
        kind="make",
        binary="yay",
        marker="Makefile",
    ),
    "paru": AurHelperSpec(
        name="paru",
        git_url="https://github.com/Morganamilo/paru.git",
        pacman_deps=("git", "base-devel", "cargo", "clang"),
        kind="cargo",
        binary="paru",
        marker="Cargo.toml",
    ),
}


def spec_for(name: str) -> AurHelperSpec:
    key = validate_aur_helper(name)
    return SPECS[key]


def installed_path(name: str) -> str | None:
    validate_aur_helper(name)
    path = shutil.which(name)
    return path or None
