from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from enigmars_util.extras import EXTRAS_REPO, EXTRAS_SETUP, ExtrasStatus, probe_extras
from enigmars_util.names import MAX_PKGS, validate_package_list
from enigmars_util.packages import PackageError, Pkg, backend_for
from enigmars_util.privileged import extras_repo_setup_cmd, pkg_install_cmd
from enigmars_util.profile import HostProfile
from enigmars_util.ui.jobs import Work
from enigmars_util.ui.widgets import JobPane, button, confirm, warn


class ExtrasPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profile: HostProfile | None = None
        self._status: ExtrasStatus | None = None
        self._work: Work | None = None
        self._gen = 0
        self._pending_chunks: list[str] = []
        root = QVBoxLayout(self)

        title = QLabel("Enigmars Packages")
        title.setObjectName("cardTitle")
        root.addWidget(title)
        self.caption = QLabel(
            f"Packages from the {EXTRAS_REPO} pacman repo (app-track, enigmars-utils, …)."
        )
        self.caption.setObjectName("muted")
        self.caption.setWordWrap(True)
        root.addWidget(self.caption)

        self.setup = QPlainTextEdit()
        self.setup.setReadOnly(True)
        self.setup.setPlainText(EXTRAS_SETUP.strip())
        self.setup.setMaximumBlockCount(20)
        self.setup.setFixedHeight(96)
        self.setup.setVisible(False)
        root.addWidget(self.setup)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        root.addWidget(self.list, 1)

        self.installed_hint = QLabel("")
        self.installed_hint.setObjectName("muted")
        self.installed_hint.setWordWrap(True)
        root.addWidget(self.installed_hint)

        row = QHBoxLayout()
        row.addWidget(button("Refresh", self.refresh))
        self.add_repo_btn = button("Add repo and refresh", self._add_repo)
        self.add_repo_btn.setVisible(False)
        self.install_sel_btn = button("Install selected", self._install_selected)
        self.install_all_btn = button("Install all missing", self._install_all)
        row.addWidget(self.add_repo_btn)
        row.addWidget(self.install_sel_btn)
        row.addWidget(self.install_all_btn)
        row.addStretch()
        root.addLayout(row)

        self.job = JobPane()
        self.job.finished.connect(self._job_done)
        root.addWidget(self.job)

    def set_profile(self, profile: HostProfile) -> None:
        self._profile = profile
        self.refresh()

    def refresh(self) -> None:
        if not self._profile:
            return
        if self._profile.native_pm != "pacman":
            self._apply_status(
                ExtrasStatus(
                    False,
                    (),
                    (),
                    (),
                    "Enigmars Packages is for pacman (EnigmarsOS / Arch).",
                )
            )
            return
        self._gen += 1
        gen = self._gen
        self.caption.setText("Checking enigmars-extras…")

        def work() -> ExtrasStatus | Exception:
            try:
                return probe_extras()
            except Exception as exc:  # noqa: BLE001
                return exc

        thread = Work(work, self)
        self._work = thread

        def done(obj: object) -> None:
            if gen != self._gen:
                return
            if isinstance(obj, ExtrasStatus):
                self._apply_status(obj)
                return
            if isinstance(obj, Exception):
                warn(self, "Enigmars Packages", str(obj))
                self.caption.setText(str(obj))

        thread.result.connect(done)
        thread.start()

    def _apply_status(self, status: ExtrasStatus) -> None:
        self._status = status
        self.list.clear()
        self.caption.setText(status.detail)
        self.setup.setVisible(not status.configured)
        mutate = bool(self._profile and self._profile.can_mutate_native)
        pacman = bool(self._profile and self._profile.native_pm == "pacman")
        has_missing = bool(status.missing)
        self.add_repo_btn.setVisible(pacman and not status.configured)
        self.add_repo_btn.setEnabled(mutate and pacman and not status.configured)
        self.install_sel_btn.setEnabled(mutate and has_missing)
        self.install_all_btn.setEnabled(mutate and has_missing)
        if not status.configured:
            self.installed_hint.setText(
                "Use Add repo and refresh to write /etc/pacman.d/enigmars-extras.conf, "
                "Include it from pacman.conf, and run pacman -Sy."
            )
            return
        for pkg in status.missing:
            item = QListWidgetItem(f"{pkg.name}  {pkg.version}".rstrip())
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
            )
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(int(Qt.ItemDataRole.UserRole), pkg)
            self.list.addItem(item)
        if status.installed:
            names = ", ".join(p.name for p in status.installed)
            self.installed_hint.setText(f"Already installed: {names}")
        elif status.missing:
            self.installed_hint.setText("Check packages to install, or use Install all missing.")
        else:
            self.installed_hint.setText("")

    def _checked_names(self) -> list[str]:
        names: list[str] = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item is None or item.checkState() != Qt.CheckState.Checked:
                continue
            pkg = item.data(int(Qt.ItemDataRole.UserRole))
            if isinstance(pkg, Pkg):
                names.append(pkg.name)
        return names

    def _add_repo(self) -> None:
        if not self._profile or self._profile.native_pm != "pacman":
            warn(self, "Enigmars Packages", "Adding enigmars-extras requires pacman.")
            return
        if not self._profile.can_mutate_native:
            warn(self, "Enigmars Packages", "Package changes are not available on this system.")
            return
        body = (
            "Add the enigmars-extras pacman repo and refresh databases?\n\n"
            "This writes /etc/pacman.d/enigmars-extras.conf, Includes it from "
            "/etc/pacman.conf if needed, then runs pacman -Sy.\n\n"
            f"{EXTRAS_SETUP.strip()}"
        )
        if not confirm(self, "Add enigmars-extras", body):
            return
        try:
            self._pending_chunks = []
            self.job.run(extras_repo_setup_cmd(), "extras-repo-setup")
        except FileNotFoundError as exc:
            warn(self, "Helper", str(exc))

    def _install_selected(self) -> None:
        names = self._checked_names()
        if not names:
            warn(self, "Enigmars Packages", "Check one or more packages, or use Install all missing.")
            return
        self._install(names)

    def _install_all(self) -> None:
        if not self._status or not self._status.missing:
            warn(self, "Enigmars Packages", "Nothing missing from enigmars-extras.")
            return
        self._install([p.name for p in self._status.missing])

    def _install(self, names: list[str]) -> None:
        if not self._profile or not self._profile.can_mutate_native:
            warn(self, "Install", "Native package installs are not available on this system.")
            return
        try:
            names = validate_package_list(names)
        except ValueError as exc:
            warn(self, "Install", str(exc))
            return
        backend = backend_for(self._profile)
        try:
            tx = backend.preview_install(names)
            body = "Install from enigmars-extras:\n" + "\n".join(tx.lines)
        except PackageError as exc:
            body = "Install from enigmars-extras:\n" + "\n".join(names) + f"\n\n({exc})"
        if not confirm(self, "Confirm install", body):
            return
        try:
            # Helper caps one transaction; chunk if the extras repo grows.
            first, rest = names[:MAX_PKGS], names[MAX_PKGS:]
            self.job.run(pkg_install_cmd(first), "pkg-install")
            self._pending_chunks = rest
        except FileNotFoundError as exc:
            warn(self, "Helper", str(exc))

    def _job_done(self, ok: bool) -> None:
        pending = getattr(self, "_pending_chunks", [])
        if ok and pending:
            nxt, rest = pending[:MAX_PKGS], pending[MAX_PKGS:]
            self._pending_chunks = rest
            try:
                self.job.run(pkg_install_cmd(nxt), "pkg-install")
                return
            except FileNotFoundError as exc:
                warn(self, "Helper", str(exc))
        self._pending_chunks = []
        if ok:
            self.refresh()
