from __future__ import annotations

import unittest
from pathlib import Path

from enigmars_util.extras import (
    EXTRAS_INCLUDE,
    EXTRAS_REPO,
    extras_configured,
    extras_include_present,
    parse_pacman_conf_includes,
    parse_pacman_conf_repos,
    parse_pacman_sl,
    parse_repo_list,
    probe_extras,
    with_extras_include,
)


class ExtrasParseTest(unittest.TestCase):
    def test_conf_section_and_include(self) -> None:
        text = (
            "[options]\n"
            "HoldPkg = pacman\n"
            "Include = /etc/pacman.d/mirrorlist\n"
            "[core]\n"
            "Include = /etc/pacman.d/mirrorlist\n"
            "[enigmars-extras]\n"
            "SigLevel = Optional TrustAll\n"
            "Server = https://example.invalid/$repo/$arch\n"
        )
        self.assertEqual(parse_pacman_conf_repos(text), ["core", "enigmars-extras"])
        self.assertEqual(
            parse_pacman_conf_includes(text),
            ["/etc/pacman.d/mirrorlist", "/etc/pacman.d/mirrorlist"],
        )
        self.assertTrue(extras_configured(["core", "extra", EXTRAS_REPO]))
        self.assertFalse(extras_configured(["core", "extra"]))

    def test_pacman_conf_repo_list(self) -> None:
        self.assertEqual(
            parse_repo_list("core\nextra\nenigmars-extras\n"),
            ["core", "extra", "enigmars-extras"],
        )

    def test_sl_missing_and_installed(self) -> None:
        text = (
            "enigmars-extras app-track 1.1.0-1\n"
            "enigmars-extras enigmars-utils 1.0.0-1 [installed]\n"
            "extra firefox 140.0-1\n"
            "enigmars-extras bad;name 1-1\n"
        )
        pkgs = parse_pacman_sl(text)
        self.assertEqual([p.name for p in pkgs], ["app-track", "enigmars-utils"])
        self.assertFalse(pkgs[0].installed)
        self.assertTrue(pkgs[1].installed)
        self.assertEqual(pkgs[0].repo, EXTRAS_REPO)
        self.assertEqual(pkgs[0].version, "1.1.0-1")

    def test_walk_include(self) -> None:
        from unittest import mock

        from enigmars_util.extras import _walk_pacman_conf

        files = {
            Path("/etc/pacman.conf"): (
                "[options]\n"
                "Include = /etc/pacman.d/*.conf\n"
                "[core]\n"
            ),
            Path("/etc/pacman.d/enigmars-extras.conf"): (
                "[enigmars-extras]\n"
                "Server = file:///tmp/repo\n"
            ),
        }

        def read_text(path: Path) -> str:
            return files.get(path, "")

        with mock.patch(
            "enigmars_util.extras.glob.glob",
            return_value=["/etc/pacman.d/enigmars-extras.conf"],
        ):
            repos = _walk_pacman_conf(Path("/etc/pacman.conf"), read_text)
        self.assertEqual(repos, ["core", "enigmars-extras"])

    def test_include_is_idempotent(self) -> None:
        base = "[options]\nHoldPkg = pacman\n[core]\nInclude = /etc/pacman.d/mirrorlist\n"
        once = with_extras_include(base)
        self.assertIn(EXTRAS_INCLUDE, once)
        self.assertTrue(extras_include_present(once))
        twice = with_extras_include(once)
        self.assertEqual(once, twice)
        inline = "[core]\n[enigmars-extras]\nServer = https://example.invalid\n"
        self.assertEqual(with_extras_include(inline), inline)

    def test_probe_without_pacman_is_safe(self) -> None:
        import shutil
        from unittest import mock

        with mock.patch.object(shutil, "which", return_value=None):
            status = probe_extras()
        self.assertFalse(status.configured)
        self.assertIn("pacman", status.detail.lower())


if __name__ == "__main__":
    unittest.main()
