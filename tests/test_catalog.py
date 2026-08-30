from __future__ import annotations

import unittest

from enigmars_util.catalog import load_apps, load_kernels, load_tweaks, tweaks_for
from enigmars_util.packages import _parse_pacman_search
from enigmars_util.probe import probe_host
from enigmars_util.tweaks import windows_pack
from tests.fakes import FakeFS


class CatalogTest(unittest.TestCase):
    def test_load_tweaks(self) -> None:
        tweaks = load_tweaks()
        ids = {t.id for t in tweaks}
        self.assertIn("plasma.double-click", ids)
        self.assertIn("gnome.double-click", ids)

    def test_windows_pack_plasma_only(self) -> None:
        fs = FakeFS(files={"/var/lib/pacman": ""}, bins={"pacman"})
        profile = probe_host(
            fs=fs,
            environ={"XDG_CURRENT_DESKTOP": "KDE"},
            os_release_text='ID=arch\nPRETTY_NAME="Arch Linux"\n',
            lspci_text="",
        )
        ids = {t.id for t in windows_pack(profile)}
        self.assertIn("plasma.double-click", ids)
        self.assertIn("plasma.night-color", ids)
        self.assertNotIn("gnome.double-click", ids)
        self.assertNotIn("plasma.no-userfeedback", ids)

    def test_filter_plasma(self) -> None:
        fs = FakeFS(files={"/var/lib/pacman": ""}, bins={"pacman"})
        profile = probe_host(
            fs=fs,
            environ={"XDG_CURRENT_DESKTOP": "KDE"},
            os_release_text='ID=arch\nID_LIKE=arch\nPRETTY_NAME="Arch Linux"\n',
            lspci_text="",
        )
        ids = {t.id for t in tweaks_for(profile)}
        self.assertIn("plasma.double-click", ids)
        self.assertNotIn("gnome.double-click", ids)

    def test_kernels_arch(self) -> None:
        pkgs = [k.package for k in load_kernels("arch")]
        self.assertIn("linux-enigmarsos", pkgs)
        self.assertIn("linux-cachyos", pkgs)
        self.assertIn("linux", pkgs)

    def test_apps(self) -> None:
        apps = load_apps()
        self.assertTrue(any(a.id == "firefox" for a in apps))

    def test_pacman_search_parse(self) -> None:
        text = (
            "extra/firefox 140.0-1 [installed]\n"
            "    Fast web browser\n"
            "extra/firefox-developer-edition 141.0b1-1\n"
            "    Developer edition\n"
        )
        pkgs = _parse_pacman_search(text)
        self.assertEqual(pkgs[0].name, "firefox")
        self.assertTrue(pkgs[0].installed)
        self.assertEqual(pkgs[0].description, "Fast web browser")
        self.assertEqual(pkgs[1].name, "firefox-developer-edition")
        self.assertFalse(pkgs[1].installed)


if __name__ == "__main__":
    unittest.main()
