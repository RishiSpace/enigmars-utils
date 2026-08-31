from __future__ import annotations

import unittest

from enigmars_util.health import assess, gpu_item, kernel_item, overall_level, secure_boot_item, security_item
from enigmars_util.profile import Gpu, HostProfile
from enigmars_util.secureboot import SecureBootStatus


def _profile(**kwargs: object) -> HostProfile:
    base = dict(
        distro_id="arch",
        distro_like=("arch",),
        pretty_name="Arch Linux",
        version_id="",
        family="arch",
        desktop="plasma",
        session="wayland",
        native_pm="pacman",
        flatpak=False,
        snap=False,
        immutable=False,
        can_mutate_native=True,
        bootloader="limine",
        kernel_release="6.13.1-arch1-1",
        firewall="active",
    )
    base.update(kwargs)
    return HostProfile(**base)  # type: ignore[arg-type]


def _sb(**kwargs: object) -> SecureBootStatus:
    base = dict(
        uefi=True,
        sbctl_present=True,
        sbctl_installed=True,
        secure_boot=True,
        setup_mode=False,
        enrolled=True,
        microsoft_keys=True,
        guid="abc",
        vendors=("microsoft",),
    )
    base.update(kwargs)
    return SecureBootStatus(**base)  # type: ignore[arg-type]


class HealthTest(unittest.TestCase):
    def test_gpu_nvidia_missing_module(self) -> None:
        p = _profile(gpus=(Gpu("NVIDIA VGA", "nvidia"),), nvidia_loaded=False)
        item = gpu_item(p)
        self.assertEqual(item.level, "warn")
        self.assertEqual(item.page, "drivers")

    def test_gpu_nvidia_ok(self) -> None:
        p = _profile(gpus=(Gpu("NVIDIA VGA", "nvidia"),), nvidia_loaded=True)
        self.assertEqual(gpu_item(p).level, "ok")

    def test_kernel_modules_missing(self) -> None:
        p = _profile()
        self.assertEqual(kernel_item(p, modules_present=False).level, "bad")
        self.assertEqual(kernel_item(p, modules_present=True).level, "ok")

    def test_secure_boot_states(self) -> None:
        self.assertEqual(secure_boot_item(_sb()).level, "ok")
        self.assertEqual(secure_boot_item(_sb(secure_boot=False, enrolled=False)).level, "warn")
        self.assertEqual(secure_boot_item(_sb(uefi=False, secure_boot=None)).level, "unknown")

    def test_security_firewall_off(self) -> None:
        p = _profile(firewall="inactive")
        item = security_item(p, apparmor=True)
        self.assertEqual(item.level, "warn")

    def test_overall_worst_wins(self) -> None:
        p = _profile(gpus=(), firewall="inactive")
        items = assess(p, _sb(secure_boot=False), modules_present=True, apparmor=True)
        self.assertEqual(overall_level(items), "warn")
        ids = {i.id for i in items}
        self.assertEqual(ids, {"gpu", "kernel", "secure-boot", "security"})


if __name__ == "__main__":
    unittest.main()
