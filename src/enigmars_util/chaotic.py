"""Detect and describe the Chaotic-AUR pacman repo.

Chaotic-AUR is a third-party binary cache of AUR packages. Enabling it means:
  1. importing + locally signing the primary key,
  2. installing chaotic-keyring + chaotic-mirrorlist from the CDN,
  3. appending ``[chaotic-aur]`` to pacman.conf,
  4. refreshing the sync databases.

Mutations run through the privileged helper (``chaotic-repo-setup`` verb).
This module only reads state and edits pacman.conf *text* (pure functions)
so the UI can preview and the helper can apply atomically.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

CHAOTIC_REPO = "chaotic-aur"
CHAOTIC_MIRRORLIST = Path("/etc/pacman.d/chaotic-mirrorlist")
CHAOTIC_INCLUDE = "Include = /etc/pacman.d/chaotic-mirrorlist"
CHAOTIC_SNIPPET = "[chaotic-aur]\nInclude = /etc/pacman.d/chaotic-mirrorlist\n"

CHAOTIC_KEYID = "3056513887B78AEB"
CHAOTIC_KEYSERVER = "keyserver.ubuntu.com"
CHAOTIC_KEYRING_URL = "https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-keyring.pkg.tar.zst"
CHAOTIC_MIRRORLIST_URL = "https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-mirrorlist.pkg.tar.zst"

PACMAN_CONF = Path("/etc/pacman.conf")
_TIMEOUT = 20


@dataclass(frozen=True)
class ChaoticStatus:
    configured: bool
    mirrorlist_present: bool
    detail: str


class ChaoticError(Exception):
    pass


def chaotic_include_present(text: str) -> bool:
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == CHAOTIC_INCLUDE:
            return True
    return False


def chaotic_repo_present(text: str) -> bool:
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]") and len(line) > 2:
            if line[1:-1].strip() == CHAOTIC_REPO:
                return True
    return False


def with_chaotic_include(text: str) -> str:
    """Return pacman.conf text with [chaotic-aur] appended, without duplicating."""
    if chaotic_repo_present(text) or chaotic_include_present(text):
        return text
    body = text
    if body and not body.endswith("\n"):
        body += "\n"
    return body + "\n# chaotic-aur (enigmars-util)\n" + CHAOTIC_SNIPPET


def probe_chaotic(
    repos: list[str] | None = None,
    *,
    mirrorlist: Path = CHAOTIC_MIRRORLIST,
) -> ChaoticStatus:
    """Best-effort status of the chaotic-aur repo (never raises for missing tools)."""
    if not shutil.which("pacman"):
        return ChaoticStatus(False, False, "Chaotic-AUR needs pacman (EnigmarsOS / Arch).")
    if repos is None:
        try:
            from enigmars_util.extras import configured_repos
        except Exception:  # noqa: BLE001
            configured = False
        else:
            try:
                configured = CHAOTIC_REPO in configured_repos()
            except Exception:  # noqa: BLE001
                configured = False
    else:
        configured = CHAOTIC_REPO in repos
    try:
        has_mirrorlist = mirrorlist.is_file()
    except OSError:
        has_mirrorlist = False
    if configured and has_mirrorlist:
        count = _repo_package_count()
        if count is None:
            detail = "chaotic-aur is enabled and the mirrorlist is installed."
        elif count == 0:
            detail = "chaotic-aur is enabled but the sync db is empty. Run a system update."
        else:
            detail = f"chaotic-aur is enabled ({count} packages in sync db)."
        return ChaoticStatus(True, True, detail)
    if configured:
        return ChaoticStatus(
            True,
            False,
            "chaotic-aur is in pacman.conf but /etc/pacman.d/chaotic-mirrorlist is missing. "
            "Re-run enable to reinstall the mirrorlist.",
        )
    if has_mirrorlist:
        return ChaoticStatus(
            False,
            True,
            "chaotic-mirrorlist is installed but [chaotic-aur] is not in pacman.conf.",
        )
    return ChaoticStatus(False, False, "chaotic-aur is not configured.")


def _repo_package_count() -> int | None:
    pacman = shutil.which("pacman")
    if not pacman:
        return None
    try:
        proc = subprocess.run(
            [pacman, "-Sl", CHAOTIC_REPO],
            check=False,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    count = 0
    for line in (proc.stdout or "").splitlines():
        if line.strip().startswith(CHAOTIC_REPO + " "):
            count += 1
    return count
