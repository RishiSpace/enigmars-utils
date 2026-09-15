from __future__ import annotations

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from enigmars_util.kernel import (
    KernelRow,
    KernelSafetyError,
    assert_can_remove,
    inventory,
    packages_to_install,
    packages_to_remove,
)
from enigmars_util.kernel_repos import (
    KERNEL_DROPINS,
    KERNEL_INCLUDES,
    KERNEL_REPOS,
    KERNEL_SETUPS,
    KernelRepoStatus,
    probe_kernel_repos,
)
from enigmars_util.packages import backend_for
from enigmars_util.privileged import kernel_repo_setup_cmd, pkg_install_cmd, pkg_remove_cmd
from enigmars_util.profile import HostProfile
from enigmars_util.ui.jobs import Work
from enigmars_util.ui.widgets import Card, JobPane, button, confirm, warn


class KernelPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profile: HostProfile | None = None
        self._rows: list[KernelRow] = []
        self._work: Work | None = None
        self._gen = 0
        self._last_mutated = False
        self._repo_work: Work | None = None
        self._repo_gen = 0
        root = QVBoxLayout(self)
        self.caption = QLabel("Kernels from the native package manager.")
        self.caption.setObjectName("muted")
        self.caption.setWordWrap(True)
        root.addWidget(self.caption)

        self._repos_card = Card(
            "EnigmarsOS kernels",
            "linux-enigmarsos (rolling) and linux-enigmarsos-lts ship in EnigmarsOS repos. "
            "Enable them here on any pacman system.",
        )
        repo_row = QHBoxLayout()
        repo_row.setContentsMargins(0, 4, 0, 4)
        self.kernel_repo_status = QLabel("Checking EnigmarsOS kernel repos…")
        self.kernel_repo_status.setObjectName("muted")
        self.kernel_repo_status.setWordWrap(True)
        repo_row.addWidget(self.kernel_repo_status, 1)
        self.kernel_repo_btn = button("Enable kernel repos", self._enable_kernel_repos)
        self.kernel_repo_btn.setToolTip(
            "Write the linux-enigmarsos drop-ins, Include them from pacman.conf, and refresh databases"
        )
        repo_row.addWidget(self.kernel_repo_btn)
        self._repos_card.body.addLayout(repo_row)
        root.addWidget(self._repos_card)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Kernel", "Package", "Version", "Installed", "Available", "Running"])
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(self.table.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        row = QHBoxLayout()
        row.addWidget(button("Refresh", self.refresh))
        row.addWidget(button("Install", self._install))
        row.addWidget(button("Remove", self._remove))
        row.addStretch()
        root.addLayout(row)
        self.job = JobPane()
        self.job.finished.connect(self._job_done)
        root.addWidget(self.job)

    def set_profile(self, profile: HostProfile) -> None:
        self._profile = profile
        note = ""
        if profile.enigmarsos:
            note = " EnigmarsOS restages kernels onto the ESP after install/remove."
        if not profile.can_mutate_native:
            note += " Package mutations are disabled on this system."
        self.caption.setText(
            f"Running {profile.kernel_release}. Bootloader: {profile.bootloader}.{note}"
        )
        self._repos_card.setVisible(profile.native_pm == "pacman")
        self._refresh_kernel_repos()
        self.refresh()

    def _refresh_kernel_repos(self) -> None:
        self._repo_gen += 1
        gen = self._repo_gen
        profile = self._profile
        if profile is None or profile.native_pm != "pacman":
            self.kernel_repo_status.setText("EnigmarsOS kernel repos need pacman (EnigmarsOS / Arch).")
            self.kernel_repo_btn.setEnabled(False)
            return
        self.kernel_repo_status.setText("Checking EnigmarsOS kernel repos…")
        self.kernel_repo_btn.setEnabled(False)

        def work() -> KernelRepoStatus | Exception:
            try:
                return probe_kernel_repos()
            except Exception as exc:  # noqa: BLE001
                return exc

        thread = Work(work, self)
        self._repo_work = thread

        def done(obj: object) -> None:
            if gen != self._repo_gen:
                return
            mutate = bool(profile.can_mutate_native)
            if isinstance(obj, Exception):
                self.kernel_repo_status.setText(f"Could not check kernel repos: {obj}")
                self.kernel_repo_btn.setEnabled(mutate)
                return
            if not isinstance(obj, KernelRepoStatus):
                return
            self.kernel_repo_status.setText(obj.detail)
            if obj.missing:
                self.kernel_repo_btn.setText("Enable kernel repos")
            else:
                self.kernel_repo_btn.setText("Repair / reinstall")
            self.kernel_repo_btn.setEnabled(mutate)

        thread.result.connect(done)
        thread.start()

    def _enable_kernel_repos(self) -> None:
        if not self._profile or self._profile.native_pm != "pacman":
            warn(self, "EnigmarsOS kernels", "EnigmarsOS kernel repos need pacman.")
            return
        if not self._profile.can_mutate_native:
            warn(self, "EnigmarsOS kernels", "Package changes are not available on this system.")
            return
        lines = []
        for repo in KERNEL_REPOS:
            lines.append(f"{KERNEL_DROPINS[repo]}:\n{KERNEL_SETUPS[repo].strip()}")
        body = (
            "Enable the EnigmarsOS kernel repos?\n\n"
            + "\n\n".join(lines)
            + "\n\nThis Includes both drop-ins from /etc/pacman.conf "
            f"({', '.join(KERNEL_INCLUDES[r] for r in KERNEL_REPOS)}) "
            "and refreshes sync databases (pacman -Sy).\n\n"
            "Afterwards linux-enigmarsos and linux-enigmarsos-lts can be "
            "installed from the table below."
        )
        if not confirm(self, "Enable EnigmarsOS kernel repos", body):
            return
        try:
            self.job.run(kernel_repo_setup_cmd(), "kernel-repo-setup")
        except FileNotFoundError as exc:
            warn(self, "Helper", str(exc))

    def refresh(self) -> None:
        if not self._profile:
            return
        profile = self._profile
        backend = backend_for(profile)
        self._gen += 1
        gen = self._gen

        def work() -> list[KernelRow]:
            return inventory(profile, backend)

        thread = Work(work, self)
        self._work = thread

        def done(obj: object) -> None:
            if gen != self._gen:
                return
            if isinstance(obj, Exception):
                warn(self, "Kernel", str(obj))
                return
            if not isinstance(obj, list):
                return
            self._rows = [r for r in obj if isinstance(r, KernelRow)]
            self._fill()

        thread.result.connect(done)
        thread.start()

    def _fill(self) -> None:
        self.table.setRowCount(len(self._rows))
        for i, row in enumerate(self._rows):
            rec = " (recommended)" if row.flavor.recommended and self._profile and self._profile.enigmarsos else ""
            self.table.setItem(i, 0, QTableWidgetItem(row.flavor.label + rec))
            self.table.setItem(i, 1, QTableWidgetItem(row.flavor.package))
            self.table.setItem(i, 2, QTableWidgetItem(row.version))
            self.table.setItem(i, 3, QTableWidgetItem("yes" if row.installed else "no"))
            self.table.setItem(i, 4, QTableWidgetItem("yes" if row.available else "no"))
            self.table.setItem(i, 5, QTableWidgetItem("yes" if row.running else ""))
        self.table.resizeColumnsToContents()
        if self._profile:
            note = ""
            if self._profile.enigmarsos:
                note = " EnigmarsOS restages kernels onto the ESP after install/remove."
            if not self._profile.can_mutate_native:
                note += " Package mutations are disabled on this system."
            self.caption.setText(
                f"Running {self._profile.kernel_release}. Bootloader: {self._profile.bootloader}.{note}"
            )

    def _selected(self) -> KernelRow | None:
        idx = self.table.currentRow()
        if idx < 0 or idx >= len(self._rows):
            return None
        return self._rows[idx]

    def _install(self) -> None:
        row = self._selected()
        if not row or not self._profile:
            return
        if not self._profile.can_mutate_native:
            warn(self, "Kernel", "Cannot install kernels on this system from this app.")
            return
        if row.flavor.package == "(running)":
            warn(self, "Kernel", "No kernel catalog for this system (unknown distro family).")
            return
        if row.installed:
            warn(self, "Kernel", f"{row.flavor.package} is already installed.")
            return
        if not row.available:
            warn(
                self,
                "Kernel",
                f"{row.flavor.package} is not in the sync databases.\n\n"
                "For linux-enigmarsos / linux-enigmarsos-lts, use "
                "\"Enable kernel repos\" above, then Refresh.\n"
                "Otherwise run a system update first so pacman knows the package.",
            )
            return
        names = packages_to_install(row)
        if not confirm(self, "Install kernel", "Install:\n" + "\n".join(names)):
            return
        try:
            self._last_mutated = True
            self.job.run(pkg_install_cmd(names), "pkg-install")
        except FileNotFoundError as exc:
            warn(self, "Helper", str(exc))

    def _remove(self) -> None:
        row = self._selected()
        if not row or not self._profile:
            return
        if not self._profile.can_mutate_native:
            warn(self, "Kernel", "Cannot remove kernels on this system from this app.")
            return
        try:
            assert_can_remove(self._rows, row)
        except KernelSafetyError as exc:
            warn(self, "Kernel", str(exc))
            return
        versions = backend_for(self._profile).installed_versions()
        names = packages_to_remove(row, versions)
        if not confirm(self, "Remove kernel", "Remove:\n" + "\n".join(names)):
            return
        try:
            self._last_mutated = True
            self.job.run(pkg_remove_cmd(names), "pkg-remove")
        except FileNotFoundError as exc:
            warn(self, "Helper", str(exc))

    def _job_done(self, ok: bool) -> None:
        self.refresh()
        self._refresh_kernel_repos()
        if not ok or not self._last_mutated:
            return
        self._last_mutated = False
        if confirm(self, "Reboot", "Kernel packages changed. Reboot now?"):
            QProcess.startDetached("systemctl", ["reboot"])
