from __future__ import annotations

import shutil

from PySide6.QtCore import Qt, QTimer, QProcess
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from enigmars_util.catalog import CatalogApp, app_package_for, load_apps
from enigmars_util.packages import PackageBackend, PackageError, Pkg, backend_for
from enigmars_util.privileged import pkg_install_cmd, pkg_remove_cmd, pkg_update_cmd
from enigmars_util.profile import HostProfile
from enigmars_util.ui.jobs import Work
from enigmars_util.ui.widgets import JobPane, button, confirm, warn


class PackagesPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profile: HostProfile | None = None
        self._backend: PackageBackend | None = None
        self._apps: list[CatalogApp] = []
        self._search_work: Work | None = None
        self._search_gen = 0
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search packages…")
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(280)
        self.search.textChanged.connect(lambda _: self._debounce.start())
        self._debounce.timeout.connect(self._do_search)
        top.addWidget(self.search, 1)
        top.addWidget(button("Update system", self._update))
        top.addWidget(button("Install selected", self._install))
        top.addWidget(button("Remove selected", self._remove))
        top.addWidget(button("Install catalog item", self._install_catalog_btn))
        self.discover_btn = button("Software Center", self._discover)
        top.addWidget(self.discover_btn)
        root.addLayout(top)

        self.hint = QLabel("")
        self.hint.setObjectName("muted")
        root.addWidget(self.hint)

        split = QSplitter()
        self.catalog = QListWidget()
        self.results = QListWidget()
        split.addWidget(self.catalog)
        split.addWidget(self.results)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 2)
        root.addWidget(split, 1)

        self.job = JobPane()
        root.addWidget(self.job)
        self.catalog.itemDoubleClicked.connect(self._install_catalog)

    def set_profile(self, profile: HostProfile) -> None:
        self._profile = profile
        self._backend = backend_for(profile)
        self._apps = load_apps()
        self.catalog.clear()
        if not profile.can_mutate_native:
            self.hint.setText("Native package changes are disabled on this system (immutable or unknown PM).")
        else:
            self.hint.setText(f"Using {profile.native_pm_label}. Search native repos; catalog is on the left.")
        self.discover_btn.setVisible(bool(shutil.which("plasma-discover") or shutil.which("gnome-software")))
        for app in self._apps:
            pkg = app_package_for(app, profile)
            if not pkg and not (profile.flatpak and app.flatpak):
                continue
            item = QListWidgetItem(f"{app.title}  —  {app.summary}")
            item.setData(int(Qt.ItemDataRole.UserRole), app)
            self.catalog.addItem(item)

    def _discover(self) -> None:
        for exe in ("plasma-discover", "gnome-software"):
            if shutil.which(exe):
                QProcess.startDetached(exe)
                return

    def _selected_names(self) -> list[str]:
        names: list[str] = []
        for item in self.results.selectedItems():
            pkg = item.data(int(Qt.ItemDataRole.UserRole))
            if isinstance(pkg, Pkg):
                names.append(pkg.name)
        return names

    def _do_search(self) -> None:
        if not self._backend or not self._profile:
            return
        q = self.search.text().strip()
        self.results.clear()
        if len(q) < 2:
            return
        backend = self._backend
        self._search_gen += 1
        gen = self._search_gen
        self.hint.setText("Searching…")

        def work() -> list[Pkg] | Exception:
            try:
                return backend.search(q)
            except Exception as exc:  # noqa: BLE001
                return exc

        thread = Work(work, self)
        self._search_work = thread

        def done(obj: object) -> None:
            if gen != self._search_gen:
                return
            if self._profile and self._profile.can_mutate_native:
                self.hint.setText(
                    f"Using {self._profile.native_pm_label}. Search native repos; catalog is on the left."
                )
            if isinstance(obj, Exception):
                warn(self, "Search", str(obj))
                return
            if not isinstance(obj, list):
                return
            self.results.clear()
            for pkg in obj:
                if not isinstance(pkg, Pkg):
                    continue
                mark = " [installed]" if pkg.installed else ""
                item = QListWidgetItem(f"{pkg.name}  {pkg.version}{mark}\n{pkg.description}")
                item.setData(int(Qt.ItemDataRole.UserRole), pkg)
                self.results.addItem(item)

        thread.result.connect(done)
        thread.start()

    def _install_catalog_btn(self) -> None:
        item = self.catalog.currentItem()
        if item is None:
            warn(self, "Catalog", "Select a catalog app on the left.")
            return
        self._install_catalog(item)

    def _install_catalog(self, item: QListWidgetItem) -> None:
        app = item.data(int(Qt.ItemDataRole.UserRole))
        if not isinstance(app, CatalogApp) or not self._profile:
            return
        pkg = app_package_for(app, self._profile)
        if not pkg:
            warn(self, app.title, "No package mapping for this distro family.")
            return
        self._run_install([pkg])

    def _install(self) -> None:
        names = self._selected_names()
        if not names:
            warn(self, "Install", "Select a search result first, or pick a catalog app.")
            return
        self._run_install(names)

    def _run_install(self, names: list[str]) -> None:
        if not self._profile or not self._profile.can_mutate_native:
            warn(self, "Install", "Native package installs are not available on this system.")
            return
        if not self._backend:
            return
        try:
            tx = self._backend.preview_install(names)
        except PackageError as exc:
            warn(self, "Preview", str(exc))
            return
        body = "Install:\n" + "\n".join(tx.lines)
        if not confirm(self, "Confirm install", body):
            return
        try:
            self.job.run(pkg_install_cmd(names), "pkg-install")
        except FileNotFoundError as exc:
            warn(self, "Helper", str(exc))

    def _remove(self) -> None:
        names = self._selected_names()
        if not names or not self._backend or not self._profile:
            return
        if not self._profile.can_mutate_native:
            warn(self, "Remove", "Native package changes are not available on this system.")
            return
        try:
            tx = self._backend.preview_remove(names)
        except PackageError as exc:
            warn(self, "Preview", str(exc))
            return
        if not confirm(self, "Confirm remove", "Remove:\n" + "\n".join(tx.lines)):
            return
        try:
            self.job.run(pkg_remove_cmd(names), "pkg-remove")
        except FileNotFoundError as exc:
            warn(self, "Helper", str(exc))

    def _update(self) -> None:
        if not self._profile:
            return
        if not self._profile.can_mutate_native:
            warn(self, "Update", "System updates through this app are not available here.")
            return
        extra = ""
        if self._backend:
            try:
                ups = self._backend.upgrades()
                extra = "\n".join(ups[:40]) or "(could not list pending upgrades; update will still refresh)"
            except Exception:
                extra = "(upgrade list unavailable)"
        if not confirm(self, "Update system", f"Run a full system update?\n\n{extra}"):
            return
        try:
            self.job.run(pkg_update_cmd(), "pkg-update")
        except FileNotFoundError as exc:
            warn(self, "Helper", str(exc))
