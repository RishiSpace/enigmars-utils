#!/usr/bin/env python3
"""Root helper. Allowlisted verbs, argv only, never shell=True."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import syslog

from enigmars_util.names import validate_package_list, validate_service, validate_verb
from enigmars_util.paths import ESP_SYNC
from enigmars_util.probe import probe_host
from enigmars_util.protocol import RESULT_PREFIX

SAFE_PATH = "/usr/bin:/usr/sbin:/bin:/sbin"


def _die(msg: str, code: int = 1) -> int:
    print(msg, file=sys.stderr)
    _result(False, msg)
    return code


def _result(ok: bool, detail: str) -> None:
    print(RESULT_PREFIX + json.dumps({"ok": ok, "detail": detail}, separators=(",", ":")))


def _syslog(verb: str, detail: str, ok: bool) -> None:
    try:
        syslog.openlog("enigmars-util-helper", syslog.LOG_PID, syslog.LOG_AUTH)
        syslog.syslog(
            syslog.LOG_NOTICE if ok else syslog.LOG_WARNING,
            f"verb={verb} ok={int(ok)} {detail}",
        )
    except OSError:
        pass


def _harden() -> None:
    os.environ["PATH"] = SAFE_PATH
    os.environ.pop("LD_PRELOAD", None)
    os.environ.pop("LD_LIBRARY_PATH", None)
    os.environ.pop("PYTHONPATH", None)
    try:
        os.umask(0o022)
    except OSError:
        pass


def _stream(cmd: list[str]) -> int:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "PATH": SAFE_PATH, "DEBIAN_FRONTEND": "noninteractive"},
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
    return proc.wait()


_PROFILE = None


def _profile():
    global _PROFILE
    if _PROFILE is None:
        _PROFILE = probe_host()
    return _PROFILE


def _pm() -> str:
    return _profile().native_pm


def _is_enigmars() -> bool:
    return _profile().enigmarsos


def _maybe_sync_esp(names: list[str]) -> int:
    if not _is_enigmars():
        return 0
    if not any(n.startswith("linux") for n in names):
        return 0
    return _sync_esp()


def _sync_esp() -> int:
    if not ESP_SYNC.is_file():
        print(f"ESP sync script missing: {ESP_SYNC}", file=sys.stderr)
        return 1
    return _stream(["/bin/bash", str(ESP_SYNC)])


def _pkg_cmd(verb: str, names: list[str]) -> list[str]:
    pm = _pm()
    if pm == "pacman":
        pacman = shutil.which("pacman") or "/usr/bin/pacman"
        if verb == "install":
            return [pacman, "-S", "--needed", "--noconfirm", "--", *names]
        if verb == "remove":
            return [pacman, "-R", "--noconfirm", "--", *names]
        if verb == "update":
            return [pacman, "-Syu", "--noconfirm"]
        if verb == "refresh":
            return [pacman, "-Sy", "--noconfirm"]
    if pm == "apt":
        apt = shutil.which("apt-get") or "/usr/bin/apt-get"
        if verb == "install":
            return [apt, "install", "-y", "--", *names]
        if verb == "remove":
            return [apt, "remove", "-y", "--", *names]
        if verb == "update":
            return [apt, "dist-upgrade", "-y"]
        if verb == "refresh":
            return [apt, "update", "-y"]
    if pm == "dnf":
        dnf = shutil.which("dnf5") or shutil.which("dnf") or "/usr/bin/dnf"
        if verb == "install":
            return [dnf, "install", "-y", "--", *names]
        if verb == "remove":
            return [dnf, "remove", "-y", "--", *names]
        if verb == "update":
            return [dnf, "upgrade", "-y"]
        if verb == "refresh":
            return [dnf, "makecache"]
    if pm == "zypper":
        zypper = shutil.which("zypper") or "/usr/bin/zypper"
        if verb == "install":
            return [zypper, "--non-interactive", "install", "--", *names]
        if verb == "remove":
            return [zypper, "--non-interactive", "remove", "--", *names]
        if verb == "update":
            return [zypper, "--non-interactive", "update"]
        if verb == "refresh":
            return [zypper, "--non-interactive", "refresh"]
    raise ValueError(f"unsupported package manager: {pm}")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    _harden()
    if not argv:
        return _die("usage: enigmars-util-helper <verb> [args]", 2)
    try:
        verb = validate_verb(argv[0])
        extra = argv[1:]
        if verb in {"pkg-install", "pkg-remove"}:
            extra = validate_package_list(extra)
        elif verb in {"service-enable", "service-disable"}:
            if len(extra) != 1:
                raise ValueError("service name required")
            extra = [validate_service(extra[0])]
        elif extra:
            raise ValueError("unexpected arguments")
    except ValueError as exc:
        return _die(str(exc), 2)
    if os.geteuid() != 0:
        return _die("helper must run as root via pkexec", 2)
    rc = 0
    detail = verb
    try:
        if verb in {"pkg-install", "pkg-remove"}:
            names = validate_package_list(extra)
            detail = f"{verb} {' '.join(names)}"
            action = "install" if verb == "pkg-install" else "remove"
            rc = _stream(_pkg_cmd(action, names))
            if rc == 0:
                rc = _maybe_sync_esp(names)
        elif verb in {"pkg-update", "pkg-refresh"}:
            action = "update" if verb == "pkg-update" else "refresh"
            rc = _stream(_pkg_cmd(action, []))
            if rc == 0 and verb == "pkg-update" and _is_enigmars():
                rc = _sync_esp()
        elif verb == "kernel-sync-esp":
            rc = _sync_esp()
        elif verb == "ufw-enable":
            ufw = shutil.which("ufw") or "/usr/sbin/ufw"
            rc = _stream([ufw, "--force", "enable"])
        elif verb == "ufw-disable":
            ufw = shutil.which("ufw") or "/usr/sbin/ufw"
            rc = _stream([ufw, "disable"])
        elif verb in {"service-enable", "service-disable"}:
            if len(extra) != 1:
                raise ValueError("service name required")
            name = validate_service(extra[0])
            detail = f"{verb} {name}"
            systemctl = shutil.which("systemctl") or "/usr/bin/systemctl"
            action = "enable" if verb == "service-enable" else "disable"
            rc = _stream([systemctl, action, "--now", "--", name])
        else:
            raise ValueError(f"unhandled verb {verb}")
    except ValueError as exc:
        _syslog(verb, str(exc), False)
        return _die(str(exc), 2)
    except OSError as exc:
        _syslog(verb, str(exc), False)
        return _die(str(exc), 1)

    ok = rc == 0
    _syslog(verb, detail, ok)
    _result(ok, detail if ok else f"{detail} rc={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
