from __future__ import annotations

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from enigmars_util.probe import probe_host
from enigmars_util.profile import HostProfile
from enigmars_util.ui.pages.about import AboutPage
from enigmars_util.ui.pages.drivers import DriversPage
from enigmars_util.ui.pages.home import HomePage
from enigmars_util.ui.pages.kernel import KernelPage
from enigmars_util.ui.pages.packages import PackagesPage
from enigmars_util.ui.pages.tweaks import TweaksPage


class _ProbeThread(QThread):
    done = Signal(object)

    def run(self) -> None:
        self.done.emit(probe_host())


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Enigmars Utils")
        self.setMinimumSize(960, 640)
        self.resize(1080, 720)
        self._profile: HostProfile | None = None

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        nav = QFrame()
        nav.setObjectName("nav")
        nav.setFixedWidth(180)
        nav_l = QVBoxLayout(nav)
        self._nav_btns: dict[str, QPushButton] = {}
        self.stack = QStackedWidget()
        self.home = HomePage(self.show_page, on_update=self._home_update)
        self.tweaks = TweaksPage()
        self.packages = PackagesPage()
        self.kernel = KernelPage()
        self.drivers = DriversPage()
        self.about = AboutPage()
        pages = (
            ("home", "Home", self.home),
            ("tweaks", "Tweaks", self.tweaks),
            ("packages", "Packages", self.packages),
            ("kernel", "Kernel", self.kernel),
            ("drivers", "Drivers", self.drivers),
            ("about", "About", self.about),
        )
        for key, label, widget in pages:
            self.stack.addWidget(widget)
            btn = QPushButton(label)
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self.show_page(k))
            nav_l.addWidget(btn)
            self._nav_btns[key] = btn
        nav_l.addStretch()
        layout.addWidget(nav)
        layout.addWidget(self.stack, 1)
        self._order = [p[0] for p in pages]
        self.show_page("home")

        self._probe = _ProbeThread(self)
        self._probe.done.connect(self._on_profile)
        self._probe.start()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._probe.isRunning():
            self._probe.wait(4000)
        for worker in (getattr(self.packages, "_search_work", None), getattr(self.kernel, "_work", None)):
            if worker is not None and worker.isRunning():
                worker.wait(4000)
        super().closeEvent(event)

    def _home_update(self) -> None:
        self.show_page("packages")
        self.packages._update()

    def show_page(self, key: str) -> None:
        if key not in self._order:
            return
        self.stack.setCurrentIndex(self._order.index(key))
        for name, btn in self._nav_btns.items():
            btn.setChecked(name == key)

    def _on_profile(self, profile: object) -> None:
        if not isinstance(profile, HostProfile):
            return
        self._profile = profile
        self.setWindowTitle("Enigmars Utils")
        for page in (self.home, self.tweaks, self.packages, self.kernel, self.drivers, self.about):
            page.set_profile(profile)
