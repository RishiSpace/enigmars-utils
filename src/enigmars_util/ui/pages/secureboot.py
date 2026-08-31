from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from enigmars_util.privileged import firmware_reboot_cmd, pkg_install_cmd, sbctl_enroll_cmd
from enigmars_util.profile import HostProfile
from enigmars_util.secureboot import (
    ENABLE_SB_INSTRUCTIONS,
    SETUP_MODE_INSTRUCTIONS,
    SecureBootStatus,
    arm_resume,
    clear_resume,
    consume_oneshot,
    load_resume_phase,
    probe_secure_boot,
)
from enigmars_util.ui.widgets import Card, Chip, JobPane, button, confirm, info, warn


def _yn(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "yes" if value else "no"


class SecureBootPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profile: HostProfile | None = None
        self._status: SecureBootStatus | None = None
        root = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner_l = QVBoxLayout(inner)

        self.status_card = Card("Secure Boot")
        self.chips = QHBoxLayout()
        self.status_card.body.addLayout(self.chips)
        self.body = QLabel("Reading firmware…")
        self.body.setObjectName("muted")
        self.body.setWordWrap(True)
        self.status_card.body.addWidget(self.body)
        inner_l.addWidget(self.status_card)

        self.help = Card("What to do next")
        self.help_body = QLabel("")
        self.help_body.setWordWrap(True)
        self.help.body.addWidget(self.help_body)
        inner_l.addWidget(self.help)

        actions = QGridLayout()
        for i, (label, cb) in enumerate(
            (
                ("Refresh", self.refresh),
                ("Install sbctl", self._install_sbctl),
                ("Reboot to firmware (Setup Mode)", self._reboot_setup_mode),
                ("Set up Secure Boot keys", self._enroll),
                ("Reboot to firmware (enable Secure Boot)", self._reboot_enable),
            )
        ):
            actions.addWidget(button(label, cb), i // 3, i % 3)
        inner_l.addLayout(actions)
        inner_l.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)
        self.job = JobPane()
        self.job.finished.connect(self._job_done)
        self._expect_enroll = False
        root.addWidget(self.job)

    def set_profile(self, profile: HostProfile) -> None:
        self._profile = profile
        consume_oneshot()
        self.refresh()

    def refresh(self) -> None:
        self._status = probe_secure_boot()
        st = self._status
        while self.chips.count():
            item = self.chips.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for text in (
            f"UEFI: {_yn(st.uefi)}",
            f"sbctl installed: {_yn(st.sbctl_installed if st.sbctl_present else False)}",
            f"enrolled: {_yn(st.enrolled)}",
            f"Secure Boot: {_yn(st.secure_boot)}",
            f"Setup Mode: {_yn(st.setup_mode)}",
        ):
            self.chips.addWidget(Chip(text))
        self.chips.addStretch()

        vendors = ", ".join(st.vendors) if st.vendors else "none"
        guid = st.guid or "—"
        binary = "yes" if st.sbctl_present else "no"
        self.body.setText(
            f"sbctl on PATH: {binary}\n"
            f"sbctl install (database): {_yn(st.sbctl_installed)}\n"
            f"Enrollment (owner GUID): {guid}\n"
            f"Microsoft keys enrolled: {_yn(st.microsoft_keys)}\n"
            f"Vendor keys: {vendors}\n"
            f"Secure Boot enabled: {_yn(st.secure_boot)}\n"
            f"Setup Mode: {_yn(st.setup_mode)}"
        )
        self.help_body.setText(self._advice(st))
        if st.secure_boot and st.enrolled and not st.setup_mode:
            clear_resume()

    def _advice(self, st: SecureBootStatus) -> str:
        phase = load_resume_phase()
        if not st.uefi:
            return "This machine is not using UEFI, so firmware Secure Boot is not available."
        if not st.sbctl_present:
            return "sbctl is not installed. Install it, then put the firmware in Setup Mode before enrolling keys."
        if st.secure_boot and st.enrolled and not st.setup_mode:
            extra = " Microsoft keys are present." if st.microsoft_keys else " Microsoft keys are not listed — enroll again if a GPU Option ROM fails to load."
            return "Secure Boot is on, sbctl keys are enrolled, and Setup Mode is off." + extra
        if st.setup_mode:
            return (
                "Firmware is in Setup Mode. Enroll keys now (this includes Microsoft keys "
                "needed for NVIDIA firmware and Windows dual-boot), then reboot to firmware "
                "and enable Secure Boot."
            )
        if phase == "enable-sb":
            return ENABLE_SB_INSTRUCTIONS
        if phase == "enroll":
            return (
                "Setup Mode is still off. Reboot to firmware again and enter Setup Mode, "
                "then return here to enroll keys.\n\n" + SETUP_MODE_INSTRUCTIONS
            )
        return (
            "To use custom sbctl keys, the firmware must be in Setup Mode first.\n\n"
            + SETUP_MODE_INSTRUCTIONS
        )

    def _install_sbctl(self) -> None:
        if not self._profile or not self._profile.can_mutate_native:
            warn(self, "sbctl", "Cannot install packages on this system from this app.")
            return
        if not confirm(self, "Install sbctl", "Install the sbctl package?"):
            return
        try:
            self.job.run(pkg_install_cmd(["sbctl"]), "pkg-install")
        except FileNotFoundError as exc:
            warn(self, "Helper", str(exc))

    def _reboot_setup_mode(self) -> None:
        if not confirm(self, "Reboot to firmware", SETUP_MODE_INSTRUCTIONS + "\n\nReboot into firmware setup now?"):
            return
        arm_resume("enroll")
        self._firmware_reboot()

    def _reboot_enable(self) -> None:
        if not confirm(self, "Reboot to firmware", ENABLE_SB_INSTRUCTIONS + "\n\nReboot into firmware setup now?"):
            return
        arm_resume("enable-sb")
        self._firmware_reboot()

    def _firmware_reboot(self) -> None:
        try:
            self.job.run(firmware_reboot_cmd(), "firmware-reboot")
        except FileNotFoundError as exc:
            warn(self, "Helper", str(exc))

    def _enroll(self) -> None:
        st = self._status
        if st is None:
            return
        if not st.uefi:
            warn(self, "Secure Boot", "UEFI is required.")
            return
        if not st.sbctl_present:
            warn(self, "Secure Boot", "Install sbctl first.")
            return
        if not st.setup_mode:
            warn(
                self,
                "Setup Mode",
                "Firmware is not in Setup Mode. Reboot to firmware and enter Setup Mode first.",
            )
            return
        if not confirm(
            self,
            "Enroll keys",
            "Create sbctl keys if needed, enroll them into the firmware, "
            "and include Microsoft keys (-m). Boot files on the ESP will be signed.\n\n"
            "Continue?",
        ):
            return
        self._expect_enroll = True
        try:
            self.job.run(sbctl_enroll_cmd(), "sbctl-enroll")
        except FileNotFoundError as exc:
            self._expect_enroll = False
            warn(self, "Helper", str(exc))

    def _job_done(self, ok: bool) -> None:
        self.refresh()
        if not self._expect_enroll:
            return
        self._expect_enroll = False
        if ok:
            arm_resume("enable-sb")
            info(self, "Keys enrolled", ENABLE_SB_INSTRUCTIONS)
