from __future__ import annotations

from collections.abc import Callable
import shutil

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from enigmars_util import autostart
from enigmars_util.health import assess, overall_level
from enigmars_util.paths import icon_path
from enigmars_util.privileged import ufw_cmd
from enigmars_util.profile import HostProfile
from enigmars_util.secureboot import probe_secure_boot
from enigmars_util.tweaks import TweakError, apply_pack, windows_pack
from enigmars_util.ui.widgets import Card, Chip, HealthPanel, JobPane, button, confirm, info, warn

LOGO_SIZE = 72


class HomePage(QWidget):
    def __init__(
        self,
        goto: Callable[[str], None],
        on_update: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._goto = goto
        self._on_update = on_update
        self._profile: HostProfile | None = None

        root = QVBoxLayout(self)
        header = QHBoxLayout()
        self.logo = QLabel()
        self.logo.setFixedSize(LOGO_SIZE, LOGO_SIZE)
        header.addWidget(self.logo)
        titles = QVBoxLayout()
        self.hero = QLabel("Welcome")
        self.hero.setObjectName("hero")
        self.sub = QLabel("Detecting system…")
        self.sub.setObjectName("accent")
        titles.addWidget(self.hero)
        titles.addWidget(self.sub)
        header.addLayout(titles, 1)
        self.health = HealthPanel(self._goto)
        header.addWidget(self.health, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self.chips = QHBoxLayout()
        root.addLayout(self.chips)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        self._inner = inner
        self.grid = QGridLayout(inner)
        self.grid.setSpacing(12)
        actions = Card("Get started")
        row = QGridLayout()
        for i, (label, cb) in enumerate(
            (
                ("Update system", self._update),
                ("Tweaks", lambda: self._goto("tweaks")),
                ("Packages", lambda: self._goto("packages")),
                ("Kernels", lambda: self._goto("kernel")),
                ("Drivers", lambda: self._goto("drivers")),
                ("Secure Boot", lambda: self._goto("secure-boot")),
                ("About", lambda: self._goto("about")),
            )
        ):
            b = button(label, cb)
            b.setMinimumHeight(40)
            row.addWidget(b, i // 3, i % 3)
        actions.body.addLayout(row)
        self.grid.addWidget(actions, 0, 0, 1, 2)

        self.win = Card(
            "Coming from Windows?",
            "One click: double-click to open files, night light, and fewer animations. "
            "Each setting can be undone on the Tweaks page.",
        )
        self.win.body.addWidget(button("Apply Windows-convert pack", self._windows_pack))
        self.grid.addWidget(self.win, 1, 0)

        self.status = Card("System")
        self.status_body = QLabel("Waiting for probe…")
        self.status_body.setObjectName("muted")
        self.status_body.setWordWrap(True)
        self.status.body.addWidget(self.status_body)
        fw = QHBoxLayout()
        fw.addWidget(button("Enable firewall", lambda: self._firewall(True)))
        fw.addWidget(button("Disable firewall", lambda: self._firewall(False)))
        self.status.body.addLayout(fw)
        self.grid.addWidget(self.status, 1, 1)

        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        self.job = JobPane(compact=True)
        self.job.finished.connect(lambda _ok: self._refresh_health())
        root.addWidget(self.job)

        footer = QHBoxLayout()
        self.auto = QCheckBox("Show on login")
        self.auto.setChecked(autostart.enabled())
        self.auto.toggled.connect(autostart.set_enabled)
        footer.addWidget(self.auto)
        footer.addStretch()
        root.addLayout(footer)
        self._set_logo(None)

    def unscrolled_size(self) -> QSize:
        """Size needed to show Get started / cards without the inner scrollbar."""
        self._inner.adjustSize()
        inner = self._inner.sizeHint().expandedTo(self._inner.minimumSizeHint())
        header_h = max(self.health.sizeHint().height(), LOGO_SIZE)
        extra = header_h + 36 + self.job.sizeHint().height() + 40 + 32
        return QSize(max(inner.width() + 24, 720), inner.height() + extra)

    def _update(self) -> None:
        self._goto("packages")
        if self._on_update:
            self._on_update()

    def _set_logo(self, profile: HostProfile | None) -> None:
        del profile
        path = icon_path()
        if not path.is_file():
            return
        if path.suffix.lower() == ".svg":
            self.logo.setPixmap(QIcon(str(path)).pixmap(LOGO_SIZE, LOGO_SIZE))
            return
        pix = QPixmap(str(path)).scaled(
            LOGO_SIZE,
            LOGO_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.logo.setPixmap(pix)

    def set_profile(self, profile: HostProfile) -> None:
        self._profile = profile
        self.hero.setText(f"Welcome to {profile.pretty_name}")
        self.sub.setText(
            f"{profile.desktop} · {profile.session} · {profile.native_pm_label} · {profile.bootloader}"
        )
        self._refresh_health()
        while self.chips.count():
            item = self.chips.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for text in (
            profile.pretty_name,
            f"kernel {profile.kernel_release}",
            profile.desktop,
            profile.native_pm_label,
            f"firewall {profile.firewall}",
        ):
            self.chips.addWidget(Chip(text))
        self.chips.addStretch()

        gpu = profile.gpus[0].pci if profile.gpus else "GPU not reported"
        mutate = "yes" if profile.can_mutate_native else "no (read-only packages)"
        self.status_body.setText(
            f"Family: {profile.family}\n"
            f"Package manager: {profile.native_pm_label} (mutate: {mutate})\n"
            f"Flatpak: {'yes' if profile.flatpak else 'no'}\n"
            f"Bootloader: {profile.bootloader}\n"
            f"{gpu}"
        )
        self._set_logo(profile)

    def _refresh_health(self) -> None:
        if not self._profile:
            return
        items = assess(self._profile, probe_secure_boot())
        self.health.set_items(items, overall_level(items))

    def _windows_pack(self) -> None:
        if not self._profile:
            return
        pack = windows_pack(self._profile)
        if not pack:
            warn(self, "Windows convert", "No matching tweaks for this desktop.")
            return
        listing = "\n".join(f"• {t.title}" for t in pack)
        if not confirm(self, "Windows-convert pack", f"Apply these tweaks?\n\n{listing}"):
            return
        try:
            applied = apply_pack(pack)
        except TweakError as exc:
            warn(self, "Windows convert", str(exc))
            return
        if not applied:
            info(self, "Windows convert", "Those tweaks were already applied.")
            return
        info(self, "Windows convert", "Applied:\n" + "\n".join(applied))

    def _firewall(self, enable: bool) -> None:
        if not shutil.which("ufw"):
            warn(self, "Firewall", "ufw is not installed.")
            return
        label = "Enable UFW (deny incoming)?" if enable else "Disable UFW?"
        if not confirm(self, "Firewall", label):
            return
        try:
            self.job.run(ufw_cmd(enable), "ufw-enable" if enable else "ufw-disable")
        except FileNotFoundError as exc:
            warn(self, "Helper", str(exc))
