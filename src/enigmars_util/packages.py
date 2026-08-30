"""Package query backends. Mutations go through the privileged helper."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from enigmars_util.names import validate_package_list, validate_package_name, validate_search_query
from enigmars_util.profile import HostProfile

_TIMEOUT = 20


@dataclass(frozen=True)
class Pkg:
    name: str
    version: str
    description: str
    repo: str
    installed: bool


@dataclass(frozen=True)
class Transaction:
    action: str  # install | remove | update
    names: tuple[str, ...]
    lines: tuple[str, ...]


class PackageError(Exception):
    pass


def _run(cmd: list[str], timeout: int = _TIMEOUT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=timeout)


def _which(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise PackageError(f"{name} is not installed")
    return path


class PackageBackend:
    id = "none"

    def search(self, query: str) -> list[Pkg]:
        raise PackageError("no package manager")

    def installed(self) -> list[Pkg]:
        raise PackageError("no package manager")

    def is_installed(self, name: str) -> bool:
        return False

    def upgrades(self) -> list[str]:
        return []

    def preview_install(self, names: list[str]) -> Transaction:
        names = validate_package_list(names)
        return Transaction("install", tuple(names), ("(no preview)",))

    def preview_remove(self, names: list[str]) -> Transaction:
        names = validate_package_list(names)
        return Transaction("remove", tuple(names), ("(no preview)",))

    def installed_versions(self) -> dict[str, str]:
        try:
            return {p.name: p.version for p in self.installed()}
        except PackageError:
            return {}

    def available_set(self, names: list[str]) -> set[str]:
        return {n for n in names if self.is_installed(n)}


class PacmanBackend(PackageBackend):
    id = "pacman"

    def _pacman(self) -> str:
        return _which("pacman")

    def search(self, query: str) -> list[Pkg]:
        q = validate_search_query(query)
        if not q:
            return []
        proc = _run([self._pacman(), "-Ss", "--", q], timeout=30)
        return _parse_pacman_search(proc.stdout or "")

    def installed(self) -> list[Pkg]:
        proc = _run([self._pacman(), "-Q"], timeout=30)
        pkgs: list[Pkg] = []
        for line in (proc.stdout or "").splitlines():
            parts = line.split()
            if len(parts) >= 2:
                pkgs.append(Pkg(parts[0], parts[1], "", "local", True))
        return pkgs

    def is_installed(self, name: str) -> bool:
        name = validate_package_name(name)
        proc = _run([self._pacman(), "-Qq", "--", name])
        return proc.returncode == 0

    def upgrades(self) -> list[str]:
        proc = _run([self._pacman(), "-Qu"], timeout=30)
        lines = []
        for line in (proc.stdout or "").splitlines():
            name = line.split()[0] if line.split() else ""
            if name:
                lines.append(line.strip())
        return lines

    def preview_install(self, names: list[str]) -> Transaction:
        names = validate_package_list(names)
        proc = _run([self._pacman(), "-Sp", "--print-format", "%n %v", "--", *names])
        lines = tuple(ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip())
        if proc.returncode != 0 and not lines:
            err = (proc.stderr or "preview failed").strip()
            raise PackageError(err)
        return Transaction("install", tuple(names), lines or ("(nothing to install)",))

    def preview_remove(self, names: list[str]) -> Transaction:
        names = validate_package_list(names)
        proc = _run([self._pacman(), "-Rsp", "--print-format", "%n %v", "--", *names])
        lines = tuple(ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip())
        return Transaction("remove", tuple(names), lines or tuple(names))

    def available_set(self, names: list[str]) -> set[str]:
        found: set[str] = set()
        for raw in names:
            try:
                name = validate_package_name(raw)
            except ValueError:
                continue
            proc = _run([self._pacman(), "-Si", "--", name])
            if proc.returncode == 0:
                found.add(name)
        return found


class AptBackend(PackageBackend):
    id = "apt"

    def search(self, query: str) -> list[Pkg]:
        q = validate_search_query(query)
        if not q:
            return []
        proc = _run([_which("apt-cache"), "search", "--", q], timeout=30)
        pkgs: list[Pkg] = []
        for line in (proc.stdout or "").splitlines():
            name, _, desc = line.partition(" - ")
            name = name.strip()
            if name:
                pkgs.append(Pkg(name, "", desc.strip(), "apt", self.is_installed(name)))
        return pkgs[:80]

    def is_installed(self, name: str) -> bool:
        name = validate_package_name(name)
        proc = _run(["dpkg-query", "-W", "-f=${Status}", "--", name])
        return proc.returncode == 0 and "install ok installed" in (proc.stdout or "")

    def upgrades(self) -> list[str]:
        proc = _run([_which("apt-get"), "-s", "upgrade"], timeout=30)
        out = []
        for line in (proc.stdout or "").splitlines():
            if line.startswith("Inst "):
                out.append(line[5:].strip())
        return out

    def preview_install(self, names: list[str]) -> Transaction:
        names = validate_package_list(names)
        proc = _run([_which("apt-get"), "-s", "install", "--", *names])
        lines = tuple(
            ln.strip()
            for ln in (proc.stdout or "").splitlines()
            if ln.startswith("Inst ") or ln.startswith("Remv ")
        )
        return Transaction("install", tuple(names), lines or tuple(names))

    def preview_remove(self, names: list[str]) -> Transaction:
        names = validate_package_list(names)
        proc = _run([_which("apt-get"), "-s", "remove", "--", *names])
        lines = tuple(ln.strip() for ln in (proc.stdout or "").splitlines() if ln.startswith("Remv "))
        return Transaction("remove", tuple(names), lines or tuple(names))

    def installed_versions(self) -> dict[str, str]:
        proc = _run(["dpkg-query", "-W", "-f=${Package} ${Version}\n"])
        out: dict[str, str] = {}
        for line in (proc.stdout or "").splitlines():
            parts = line.split()
            if len(parts) >= 2:
                out[parts[0]] = parts[1]
        return out

    def available_set(self, names: list[str]) -> set[str]:
        found: set[str] = set()
        for raw in names:
            try:
                name = validate_package_name(raw)
            except ValueError:
                continue
            proc = _run(["apt-cache", "show", "--", name])
            if proc.returncode == 0 and (proc.stdout or "").strip():
                found.add(name)
        return found


class DnfBackend(PackageBackend):
    id = "dnf"

    def _dnf(self) -> str:
        return shutil.which("dnf5") or _which("dnf")

    def search(self, query: str) -> list[Pkg]:
        q = validate_search_query(query)
        if not q:
            return []
        proc = _run([self._dnf(), "search", "--", q], timeout=30)
        pkgs: list[Pkg] = []
        for line in (proc.stdout or "").splitlines():
            if "." not in line or line.startswith(" "):
                continue
            name = line.split()[0].split(".")[0]
            if name and name not in {"Name", "Last"}:
                pkgs.append(Pkg(name, "", line.strip(), "dnf", False))
        return pkgs[:80]

    def is_installed(self, name: str) -> bool:
        name = validate_package_name(name)
        proc = _run([self._dnf(), "list", "--installed", "--", name])
        return proc.returncode == 0 and name in (proc.stdout or "")

    def upgrades(self) -> list[str]:
        proc = _run([self._dnf(), "check-update"], timeout=40)
        return [ln.strip() for ln in (proc.stdout or "").splitlines()[1:] if ln.strip() and not ln.startswith("Last")]

    def preview_install(self, names: list[str]) -> Transaction:
        names = validate_package_list(names)
        return Transaction("install", tuple(names), tuple(names))

    def preview_remove(self, names: list[str]) -> Transaction:
        names = validate_package_list(names)
        return Transaction("remove", tuple(names), tuple(names))


class ZypperBackend(PackageBackend):
    id = "zypper"

    def search(self, query: str) -> list[Pkg]:
        q = validate_search_query(query)
        if not q:
            return []
        proc = _run([_which("zypper"), "--non-interactive", "search", "--", q], timeout=30)
        pkgs: list[Pkg] = []
        for line in (proc.stdout or "").splitlines():
            if "|" not in line or line.startswith("-") or "Name" in line:
                continue
            cols = [c.strip() for c in line.split("|")]
            if len(cols) >= 3:
                pkgs.append(Pkg(cols[1], "", cols[-1], "zypper", cols[0] == "i"))
        return pkgs[:80]

    def is_installed(self, name: str) -> bool:
        name = validate_package_name(name)
        proc = _run([_which("zypper"), "--non-interactive", "search", "-i", "--", name])
        return proc.returncode == 0 and name in (proc.stdout or "")

    def preview_install(self, names: list[str]) -> Transaction:
        names = validate_package_list(names)
        return Transaction("install", tuple(names), tuple(names))

    def preview_remove(self, names: list[str]) -> Transaction:
        names = validate_package_list(names)
        return Transaction("remove", tuple(names), tuple(names))


def _parse_pacman_search(text: str) -> list[Pkg]:
    pkgs: list[Pkg] = []
    current: Pkg | None = None
    for line in text.splitlines():
        if line.startswith("    "):
            if current is not None:
                pkgs[-1] = Pkg(
                    current.name,
                    current.version,
                    line.strip(),
                    current.repo,
                    current.installed,
                )
            continue
        if "/" not in line:
            continue
        repo, _, rest = line.partition("/")
        parts = rest.split()
        if not parts:
            continue
        name = parts[0]
        version = parts[1] if len(parts) > 1 else ""
        installed = "[installed]" in line
        current = Pkg(name, version, "", repo.strip(), installed)
        pkgs.append(current)
    return pkgs[:80]


class FlatpakBackend:
    def search(self, query: str) -> list[Pkg]:
        exe = shutil.which("flatpak")
        if not exe or not query.strip():
            return []
        proc = _run(
            [exe, "search", "--columns=application,name,description", "--", query.strip()],
            timeout=30,
        )
        pkgs: list[Pkg] = []
        for line in (proc.stdout or "").splitlines()[1:]:
            cols = [c.strip() for c in line.split("\t")] if "\t" in line else line.split(None, 2)
            if not cols:
                continue
            app_id = cols[0]
            title = cols[1] if len(cols) > 1 else app_id
            desc = cols[2] if len(cols) > 2 else ""
            pkgs.append(Pkg(app_id, "", f"{title} — {desc}", "flatpak", False))
        return pkgs[:40]


def backend_for(profile: HostProfile) -> PackageBackend:
    mapping: dict[str, type[PackageBackend]] = {
        "pacman": PacmanBackend,
        "apt": AptBackend,
        "dnf": DnfBackend,
        "zypper": ZypperBackend,
    }
    cls = mapping.get(profile.native_pm)
    if cls is None:
        return PackageBackend()
    return cls()
