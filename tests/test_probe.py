from __future__ import annotations

import unittest

from enigmars_util.probe import family_of, parse_os_release, probe_host
from tests.fakes import FakeFS

ENIGMARS = """
NAME="EnigmarsOS"
PRETTY_NAME="EnigmarsOS"
ID=enigmarsos
ID_LIKE=arch
VERSION_ID=
"""

UBUNTU = """
NAME="Ubuntu"
PRETTY_NAME="Ubuntu 24.04.1 LTS"
ID=ubuntu
ID_LIKE=debian
VERSION_ID="24.04"
"""

MINT = """
ID=linuxmint
ID_LIKE="ubuntu debian"
PRETTY_NAME="Linux Mint 22"
VERSION_ID="22"
"""

NIX = """
ID=nixos
PRETTY_NAME="NixOS 24.11"
"""

FEDORA = """
ID=fedora
PRETTY_NAME="Fedora Linux 41"
VERSION_ID="41"
"""


class ProbeTest(unittest.TestCase):
    def test_parse_os_release(self) -> None:
        fields = parse_os_release(UBUNTU)
        self.assertEqual(fields["ID"], "ubuntu")
        self.assertEqual(fields["VERSION_ID"], "24.04")

    def test_family(self) -> None:
        self.assertEqual(family_of("enigmarsos", ("arch",)), "arch")
        self.assertEqual(family_of("unknownos", ("ubuntu", "debian")), "debian")
        self.assertEqual(family_of("weird", ()), "unknown")

    def test_enigmarsos(self) -> None:
        fs = FakeFS(
            files={"/etc/os-release": ENIGMARS, "/var/lib/pacman": "", "/boot/efi/limine.conf": "timeout: 5\n"},
            bins={"pacman", "limine", "flatpak"},
        )
        p = probe_host(
            fs=fs,
            environ={"XDG_CURRENT_DESKTOP": "KDE", "XDG_SESSION_TYPE": "wayland"},
            os_release_text=ENIGMARS,
            kernel_release="7.1.10-2-enigmarsos",
            lspci_text="00:02.0 VGA compatible controller: Intel Corporation\n",
        )
        self.assertTrue(p.enigmarsos)
        self.assertEqual(p.family, "arch")
        self.assertEqual(p.desktop, "plasma")
        self.assertEqual(p.session, "wayland")
        self.assertEqual(p.native_pm, "pacman")
        self.assertTrue(p.can_mutate_native)
        self.assertEqual(p.bootloader, "limine")
        self.assertEqual(p.gpus[0].vendor, "intel")
        self.assertTrue(p.flatpak)

    def test_ubuntu_gnome_not_pacman(self) -> None:
        fs = FakeFS(
            files={
                "/etc/os-release": UBUNTU,
                "/var/lib/dpkg": "",
                "/var/lib/pacman": "",  # leftover, must not win
            },
            bins={"apt-get", "pacman", "gsettings"},
        )
        p = probe_host(
            fs=fs,
            environ={"XDG_CURRENT_DESKTOP": "ubuntu:GNOME", "XDG_SESSION_TYPE": "wayland"},
            os_release_text=UBUNTU,
            kernel_release="6.8.0-40-generic",
            lspci_text="",
        )
        self.assertEqual(p.family, "debian")
        self.assertEqual(p.native_pm, "apt")
        self.assertEqual(p.desktop, "gnome")
        self.assertFalse(p.enigmarsos)

    def test_mint(self) -> None:
        fs = FakeFS(files={"/var/lib/dpkg": ""}, bins={"apt-get"})
        p = probe_host(fs=fs, environ={"XDG_CURRENT_DESKTOP": "X-Cinnamon"}, os_release_text=MINT, lspci_text="")
        self.assertEqual(p.family, "debian")
        self.assertEqual(p.desktop, "cinnamon")
        self.assertEqual(p.native_pm, "apt")

    def test_nixos_immutable(self) -> None:
        fs = FakeFS(bins={"nix"})
        p = probe_host(fs=fs, environ={}, os_release_text=NIX, lspci_text="")
        self.assertTrue(p.immutable)
        self.assertFalse(p.can_mutate_native)
        self.assertEqual(p.native_pm, "nix")

    def test_fedora_hyprland(self) -> None:
        fs = FakeFS(files={"/var/lib/rpm": ""}, bins={"dnf"})
        p = probe_host(
            fs=fs,
            environ={"XDG_CURRENT_DESKTOP": "Hyprland:uwsm"},
            os_release_text=FEDORA,
            lspci_text="",
        )
        self.assertEqual(p.family, "fedora")
        self.assertEqual(p.native_pm, "dnf")
        self.assertEqual(p.desktop, "hyprland")


if __name__ == "__main__":
    unittest.main()
