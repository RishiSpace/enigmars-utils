"""Apply/undo desktop tweaks. User-level only; no shell from catalogs."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from enigmars_util.catalog import Tweak, tweaks_for
from enigmars_util.paths import state_dir
from enigmars_util.profile import HostProfile


class TweakError(Exception):
    pass


def _snapshot_path() -> Path:
    return state_dir() / "tweaks.json"


def _load_store() -> dict[str, Any]:
    path = _snapshot_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_store(store: dict[str, Any]) -> None:
    path = _snapshot_path()
    path.write_text(json.dumps(store, indent=2, sort_keys=True), encoding="utf-8")


def _run(cmd: list[str], timeout: int = 8) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _plasma_read(file: str, group: str, key: str) -> str:
    exe = shutil.which("kreadconfig6") or shutil.which("kreadconfig5")
    if not exe:
        raise TweakError("kreadconfig6 is not installed")
    proc = _run([exe, "--file", file, "--group", group, "--key", key])
    return (proc.stdout or "").strip()


def _plasma_write(file: str, group: str, key: str, value: str, type_: str) -> None:
    exe = shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")
    if not exe:
        raise TweakError("kwriteconfig6 is not installed")
    cmd = [exe, "--file", file, "--group", group, "--key", key]
    if type_:
        cmd.extend(["--type", type_])
    cmd.append(value)
    proc = _run(cmd)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "kwriteconfig failed").strip()
        raise TweakError(err)


def _gsettings_read(schema: str, key: str) -> str:
    exe = shutil.which("gsettings")
    if not exe:
        raise TweakError("gsettings is not installed")
    proc = _run([exe, "get", schema, key])
    if proc.returncode != 0:
        raise TweakError((proc.stderr or "gsettings get failed").strip())
    return (proc.stdout or "").strip()


def _gsettings_write(schema: str, key: str, value: str) -> None:
    exe = shutil.which("gsettings")
    if not exe:
        raise TweakError("gsettings is not installed")
    proc = _run([exe, "set", schema, key, value])
    if proc.returncode != 0:
        raise TweakError((proc.stderr or "gsettings set failed").strip())


def current_value(step: dict[str, Any]) -> str:
    backend = step.get("backend")
    if backend == "plasma":
        return _plasma_read(str(step["file"]), str(step["group"]), str(step["key"]))
    if backend == "gsettings":
        return _gsettings_read(str(step["schema"]), str(step["key"]))
    raise TweakError(f"unknown tweak backend: {backend!r}")


def _apply_step(step: dict[str, Any]) -> None:
    backend = step.get("backend")
    if backend == "plasma":
        _plasma_write(
            str(step["file"]),
            str(step["group"]),
            str(step["key"]),
            str(step["value"]),
            str(step.get("type") or ""),
        )
        return
    if backend == "gsettings":
        _gsettings_write(str(step["schema"]), str(step["key"]), str(step["value"]))
        return
    raise TweakError(f"unknown tweak backend: {backend!r}")


def preview(tweak: Tweak) -> list[tuple[str, str, str]]:
    """Return (label, current, target) rows."""
    rows: list[tuple[str, str, str]] = []
    for step in tweak.apply:
        label = str(step.get("key") or step.get("backend") or "setting")
        try:
            cur = current_value(step)
        except TweakError:
            cur = "(unread)"
        rows.append((label, cur, str(step.get("value") or "")))
    return rows


def _kwin_reconfigure() -> None:
    for exe in ("qdbus6", "qdbus"):
        path = shutil.which(exe)
        if path:
            _run([path, "org.kde.KWin", "/KWin", "reconfigure"])
            return
    if shutil.which("dbus-send"):
        _run(
            [
                "dbus-send",
                "--session",
                "--type=method_call",
                "--dest=org.kde.KWin",
                "/KWin",
                "org.kde.KWin.reconfigure",
            ]
        )


def _reload_if_plasma(tweaks: list[Tweak]) -> None:
    if any(any(step.get("backend") == "plasma" for step in t.apply) for t in tweaks):
        _kwin_reconfigure()


def apply_tweak(tweak: Tweak, *, reload_desktop: bool = True) -> None:
    store = _load_store()
    snapshots: list[dict[str, Any]] = []
    for step in tweak.apply:
        before = ""
        try:
            before = current_value(step)
        except TweakError:
            before = ""
        snapshots.append({"step": step, "before": before})
        _apply_step(step)
    store[tweak.id] = {"snapshots": snapshots}
    _save_store(store)
    if reload_desktop:
        _reload_if_plasma([tweak])


def windows_pack(profile: HostProfile, tweaks: list[Tweak] | None = None) -> list[Tweak]:
    return [t for t in tweaks_for(profile, tweaks) if "windows-convert" in t.audience]


def apply_pack(tweaks: list[Tweak]) -> list[str]:
    applied: list[str] = []
    for tweak in tweaks:
        if is_applied(tweak.id):
            continue
        apply_tweak(tweak, reload_desktop=False)
        applied.append(tweak.id)
    _reload_if_plasma(tweaks)
    return applied


def undo_tweak(tweak: Tweak) -> None:
    store = _load_store()
    entry = store.get(tweak.id) or {}
    snaps = entry.get("snapshots") or []
    if not snaps:
        raise TweakError("nothing to undo")
    for item in reversed(snaps):
        step = dict(item.get("step") or {})
        before = item.get("before")
        if before is None:
            continue
        step = {**step, "value": before}
        _apply_step(step)
    store.pop(tweak.id, None)
    _save_store(store)
    _reload_if_plasma([tweak])


def is_applied(tweak_id: str) -> bool:
    return tweak_id in _load_store()
