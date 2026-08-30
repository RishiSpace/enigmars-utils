from __future__ import annotations

import unittest

from enigmars_util.catalog import KernelFlavor
from enigmars_util.kernel import (
    KernelRow,
    KernelSafetyError,
    assert_can_remove,
    inventory,
    packages_to_remove,
    running_matches,
)
from enigmars_util.profile import HostProfile


def _row(pkg: str, installed: bool, running: bool) -> KernelRow:
    return KernelRow(
        flavor=KernelFlavor(package=pkg, label=pkg, recommended=False, headers=None),
        installed=installed,
        running=running,
        version="",
    )


class KernelTest(unittest.TestCase):
    def test_running_matches(self) -> None:
        self.assertTrue(running_matches("linux-enigmarsos", "7.1.10-2-enigmarsos"))
        self.assertFalse(running_matches("linux", "7.1.10-2-enigmarsos"))
        self.assertTrue(running_matches("linux-lts", "6.12.10-1-lts"))
        self.assertTrue(running_matches("linux-zen", "6.13.1-zen1-1-zen"))
        self.assertTrue(running_matches("linux", "6.13.7-arch1-1"))
        self.assertFalse(running_matches("linux-lts", "6.13.7-arch1-1"))
        self.assertTrue(running_matches("linux-cachyos", "7.2.0-1-cachyos"))
        self.assertFalse(running_matches("linux", "7.2.0-1-cachyos"))

    def test_refuse_last_kernel(self) -> None:
        rows = [_row("linux", True, True)]
        with self.assertRaises(KernelSafetyError):
            assert_can_remove(rows, rows[0])

    def test_allow_remove_fallback(self) -> None:
        rows = [_row("linux-enigmarsos", True, True), _row("linux", True, False)]
        assert_can_remove(rows, rows[1])

    def test_refuse_not_installed(self) -> None:
        rows = [_row("linux", True, True), _row("linux-lts", False, False)]
        with self.assertRaises(KernelSafetyError):
            assert_can_remove(rows, rows[1])

    def test_inventory_hides_missing_and_fills_version(self) -> None:
        class FakeBE:
            def installed_versions(self) -> dict[str, str]:
                return {"linux": "6.13.1-arch1-1"}

            def available_set(self, names: list[str]) -> set[str]:
                return {"linux", "linux-lts"}

        profile = HostProfile(
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
        )
        rows = inventory(profile, FakeBE())  # type: ignore[arg-type]
        pkgs = {r.flavor.package for r in rows}
        self.assertIn("linux", pkgs)
        self.assertIn("linux-lts", pkgs)
        self.assertNotIn("linux-enigmarsos", pkgs)
        linux = next(r for r in rows if r.flavor.package == "linux")
        self.assertTrue(linux.installed)
        self.assertTrue(linux.running)
        self.assertEqual(linux.version, "6.13.1-arch1-1")

    def test_packages_to_remove_headers(self) -> None:
        row = KernelRow(
            flavor=KernelFlavor("linux-lts", "LTS", False, "linux-lts-headers"),
            installed=True,
            running=False,
            version="1",
        )
        self.assertEqual(
            packages_to_remove(row, {"linux-lts": "1", "linux-lts-headers": "1"}),
            ["linux-lts", "linux-lts-headers"],
        )


if __name__ == "__main__":
    unittest.main()
