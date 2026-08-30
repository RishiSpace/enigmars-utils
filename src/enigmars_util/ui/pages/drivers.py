from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from enigmars_util.catalog import app_package_for, load_apps
from enigmars_util.privileged import pkg_install_cmd
from enigmars_util.profile import HostProfile
from enigmars_util.ui.widgets import Card, JobPane, button, confirm, warn


class DriversPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profile: HostProfile | None = None
        root = QVBoxLayout(self)
        self.card = Card("Graphics", "Waiting for probe…")
        self.body = QLabel()
        self.body.setWordWrap(True)
        self.card.body.addWidget(self.body)
        root.addWidget(self.card)
        self.nvidia = Card(
            "NVIDIA",
            "Nouveau/Mesa is enough for a desktop. Proprietary modules give full performance.",
        )
        self.nvidia.body.addWidget(button("Install NVIDIA open kernel module", self._install_nvidia))
        root.addWidget(self.nvidia)
        self.job = JobPane()
        root.addWidget(self.job)
        root.addStretch()

    def set_profile(self, profile: HostProfile) -> None:
        self._profile = profile
        lines = [
            f"Session: {profile.session}",
            f"NVIDIA proprietary module loaded: {'yes' if profile.nvidia_loaded else 'no'}",
            f"vulkaninfo: {'present' if profile.vulkan_tools else 'not installed'}",
            "",
        ]
        if profile.gpus:
            lines.append("GPUs:")
            lines.extend(f"  • {g.pci}" for g in profile.gpus)
        else:
            lines.append("No GPU reported (lspci missing or no VGA/3D device).")
        self.body.setText("\n".join(lines))
        has_nvidia = any(g.vendor == "nvidia" for g in profile.gpus)
        self.nvidia.setVisible(has_nvidia)

    def _install_nvidia(self) -> None:
        if not self._profile or not self._profile.can_mutate_native:
            warn(self, "NVIDIA", "Cannot install packages on this system from this app.")
            return
        pkg = None
        for app in load_apps():
            if app.id == "nvidia-open":
                pkg = app_package_for(app, self._profile)
                break
        if not pkg:
            warn(self, "NVIDIA", "No NVIDIA package mapping for this distro family.")
            return
        if not confirm(self, "NVIDIA", f"Install {pkg}?"):
            return
        try:
            self.job.run(pkg_install_cmd([pkg]), "pkg-install")
        except FileNotFoundError as exc:
            warn(self, "Helper", str(exc))
