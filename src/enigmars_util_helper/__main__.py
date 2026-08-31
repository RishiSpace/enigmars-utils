#!/usr/bin/env python3
"""Root helper. Allowlisted verbs, argv only, never shell=True."""

from __future__ import annotations

import glob
import json
import os
import pwd
import shutil
import subprocess
import sys
import syslog
from pathlib import Path

from enigmars_util.aur_helpers import spec_for
from enigmars_util.names import (
    validate_aur_helper,
    validate_package_list,
    validate_service,
    validate_verb,
)
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


def _stream(
    cmd: list[str],
    *,
    user: int | None = None,
    group: int | None = None,
    cwd: str | Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> int:
    if user is None:
        env = {**os.environ, "PATH": SAFE_PATH, "DEBIAN_FRONTEND": "noninteractive"}
        if extra_env:
            env.update(extra_env)
    else:
        env = {"PATH": SAFE_PATH, **(extra_env or {})}
    kwargs: dict[str, object] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "env": env,
    }
    if user is not None:
        kwargs["user"] = user
    if group is not None:
        kwargs["group"] = group
    if cwd is not None:
        kwargs["cwd"] = str(cwd)
    proc = subprocess.Popen(cmd, **kwargs)  # type: ignore[arg-type]
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


_SIGN_GLOBS = (
    "/boot/efi/EFI/BOOT/BOOTX64.EFI",
    "/boot/efi/EFI/BOOT/BOOTX64.efi",
    "/boot/efi/EFI/EnigmarsOS/BOOTX64.EFI",
    "/boot/efi/EFI/EnigmarsOS/vmlinuz-*",
    "/boot/vmlinuz-*",
    "/efi/EFI/BOOT/BOOTX64.EFI",
    "/efi/EFI/EnigmarsOS/BOOTX64.EFI",
    "/efi/EFI/EnigmarsOS/vmlinuz-*",
)


def _sbctl_enroll() -> int:
    sbctl = shutil.which("sbctl") or "/usr/bin/sbctl"
    if not Path(sbctl).is_file():
        print("sbctl is not installed", file=sys.stderr)
        return 1
    _stream([sbctl, "setup", "--setup"])
    if not Path("/var/lib/sbctl/keys/db").is_dir():
        rc = _stream([sbctl, "create-keys"])
        if rc != 0:
            return rc
    rc = _stream([sbctl, "enroll-keys", "-m"])
    if rc != 0:
        return rc
    for pattern in _SIGN_GLOBS:
        for path in glob.glob(pattern):
            if Path(path).is_file():
                _stream([sbctl, "sign", "-s", path])
    _stream([sbctl, "sign-all"])
    return 0


def _invoking_user() -> tuple[int, int, str, str]:
    raw = os.environ.get("PKEXEC_UID") or os.environ.get("SUDO_UID")
    if not raw or not raw.isdigit():
        raise ValueError("cannot determine invoking user (PKEXEC_UID); run via pkexec from your session")
    uid = int(raw)
    if uid == 0:
        raise ValueError("refuse to compile AUR helpers as root")
    try:
        pw = pwd.getpwuid(uid)
    except KeyError as exc:
        raise ValueError(f"unknown PKEXEC_UID {uid}") from exc
    return uid, pw.pw_gid, pw.pw_name, pw.pw_dir or f"/tmp/enigmars-build-{uid}"


def _chown_tree(path: Path, uid: int, gid: int) -> None:
    for root, dirs, files in os.walk(path):
        os.chown(root, uid, gid)
        for name in dirs + files:
            try:
                os.chown(os.path.join(root, name), uid, gid)
            except OSError:
                pass


def _pacman_has(name: str) -> bool:
    pacman = shutil.which("pacman") or "/usr/bin/pacman"
    proc = subprocess.run(
        [pacman, "-Si", "--", name],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": SAFE_PATH},
    )
    return proc.returncode == 0


def _setup_aur_helper(name: str) -> int:
    if _pm() != "pacman":
        print("AUR helpers require pacman (Arch / EnigmarsOS).", file=sys.stderr)
        return 1
    spec = spec_for(name)
    pacman = shutil.which("pacman") or "/usr/bin/pacman"
    for cand in (Path("/usr/bin") / spec.binary, Path("/usr/local/bin") / spec.binary):
        if cand.is_file() and os.access(cand, os.X_OK):
            print(f"{spec.binary} already installed at {cand}")
            return 0

    if _pacman_has(spec.name):
        print(f"{spec.name} is in the pacman sync db; installing with pacman")
        return _stream([pacman, "-S", "--needed", "--noconfirm", "--", spec.name])

    print(f"{spec.name} is not in official repos; building from {spec.git_url}")
    rc = _stream([pacman, "-S", "--needed", "--noconfirm", "--", *spec.pacman_deps])
    if rc != 0:
        return rc

    git = shutil.which("git") or "/usr/bin/git"
    uid, gid, user, home = _invoking_user()
    cache = Path("/var/cache/enigmars-util")
    cache.mkdir(parents=True, exist_ok=True)
    os.chmod(cache, 0o755)
    workdir = cache / f"build-{spec.name}"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(mode=0o700)
    os.chown(workdir, uid, gid)
    for sub in (".gocache", ".gopath", ".gomod", ".cargo", "tmp"):
        p = workdir / sub
        p.mkdir()
        os.chown(p, uid, gid)

    src = workdir / spec.name
    child_env = {
        "HOME": home,
        "USER": user,
        "LOGNAME": user,
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "GOCACHE": str(workdir / ".gocache"),
        "GOPATH": str(workdir / ".gopath"),
        "GOMODCACHE": str(workdir / ".gomod"),
        "GOPROXY": "https://proxy.golang.org,direct",
        "CGO_ENABLED": "1",
        "CARGO_HOME": str(workdir / ".cargo"),
        "CARGO_TERM_COLOR": "never",
        "TMPDIR": str(workdir / "tmp"),
    }
    print(f"cloning {spec.git_url}")
    rc = _stream(
        [git, "clone", "--depth", "1", "--", spec.git_url, str(src)],
        extra_env={
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ALLOW_PROTOCOL": "https",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
        },
    )
    if rc != 0:
        return rc
    if not (src / spec.marker).is_file():
        print(f"clone missing {spec.marker}", file=sys.stderr)
        return 1
    _chown_tree(workdir, uid, gid)

    if spec.kind == "make":
        make = shutil.which("make") or "/usr/bin/make"
        print(f"compiling {spec.name} (make PREFIX=/usr build)")
        rc = _stream(
            [make, "-C", str(src), "PREFIX=/usr", "build"],
            user=uid,
            group=gid,
            cwd=src,
            extra_env=child_env,
        )
        binary = src / spec.binary
    elif spec.kind == "cargo":
        cargo = shutil.which("cargo") or "/usr/bin/cargo"
        cargo_cmd = [cargo, "build", "--release"]
        if (src / "Cargo.lock").is_file():
            cargo_cmd.append("--locked")
        print(f"compiling {spec.name} (cargo; this can take several minutes)")
        rc = _stream(
            cargo_cmd,
            user=uid,
            group=gid,
            cwd=src,
            extra_env=child_env,
        )
        binary = src / "target" / "release" / spec.binary
    else:
        print(f"unknown build kind {spec.kind}", file=sys.stderr)
        return 1
    if rc != 0:
        return rc
    if not binary.is_file():
        print(f"build did not produce {binary}", file=sys.stderr)
        return 1

    dest = Path("/usr/bin") / spec.binary
    install = shutil.which("install") or "/usr/bin/install"
    print(f"installing {binary} -> {dest}")
    rc = _stream([install, "-Dm755", str(binary), str(dest)])
    if rc != 0:
        return rc
    conf = src / "paru.conf"
    if spec.name == "paru" and conf.is_file() and not Path("/etc/paru.conf").exists():
        _stream([install, "-Dm644", str(conf), "/etc/paru.conf"])
    shutil.rmtree(workdir, ignore_errors=True)
    print(f"{spec.binary} installed at {dest}")
    return 0


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
        elif verb == "aur-helper-setup":
            if len(extra) != 1:
                raise ValueError("aur-helper-setup accepts exactly one of: yay, paru")
            extra = [validate_aur_helper(extra[0])]
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
        elif verb == "sbctl-enroll":
            rc = _sbctl_enroll()
        elif verb == "firmware-reboot":
            systemctl = shutil.which("systemctl") or "/usr/bin/systemctl"
            print("Rebooting into firmware setup…")
            rc = _stream([systemctl, "reboot", "--firmware-setup"])
        elif verb == "aur-helper-setup":
            name = validate_aur_helper(extra[0])
            detail = f"{verb} {name}"
            rc = _setup_aur_helper(name)
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
