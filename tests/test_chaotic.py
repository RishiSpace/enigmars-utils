from __future__ import annotations

import unittest
from pathlib import Path

from enigmars_util.chaotic import (
    CHAOTIC_INCLUDE,
    CHAOTIC_REPO,
    chaotic_include_present,
    chaotic_repo_present,
    probe_chaotic,
    with_chaotic_include,
)


class ChaoticConfTest(unittest.TestCase):
    def test_detect_repo_and_include(self) -> None:
        text = "[core]\nInclude = /etc/pacman.d/mirrorlist\n[chaotic-aur]\nInclude = /etc/pacman.d/chaotic-mirrorlist\n"
        self.assertTrue(chaotic_repo_present(text))
        self.assertTrue(chaotic_include_present(text))
        self.assertFalse(chaotic_repo_present("[core]\n"))
        self.assertFalse(chaotic_include_present("[core]\n"))
        commented = "# [chaotic-aur]\n# Include = /etc/pacman.d/chaotic-mirrorlist\n"
        self.assertFalse(chaotic_repo_present(commented))
        self.assertFalse(chaotic_include_present(commented))

    def test_include_is_idempotent(self) -> None:
        base = "[options]\nHoldPkg = pacman\n[core]\nInclude = /etc/pacman.d/mirrorlist\n"
        once = with_chaotic_include(base)
        self.assertIn(CHAOTIC_INCLUDE, once)
        self.assertIn(f"[{CHAOTIC_REPO}]", once)
        self.assertEqual(with_chaotic_include(once), once)
        inline = "[core]\n[chaotic-aur]\nInclude = /etc/pacman.d/chaotic-mirrorlist\n"
        self.assertEqual(with_chaotic_include(inline), inline)

    def test_probe_without_pacman_is_safe(self) -> None:
        import shutil
        from unittest import mock

        with mock.patch.object(shutil, "which", return_value=None):
            status = probe_chaotic()
        self.assertFalse(status.configured)
        self.assertIn("pacman", status.detail.lower())

    def test_probe_repo_lists(self) -> None:
        from unittest import mock

        missing = Path("/nonexistent-chaotic-mirrorlist")
        with mock.patch("shutil.which", return_value="/usr/bin/pacman"):
            ok = probe_chaotic(["core", CHAOTIC_REPO], mirrorlist=missing)
            self.assertTrue(ok.configured)
            self.assertFalse(ok.mirrorlist_present)
            off = probe_chaotic(["core", "extra"], mirrorlist=missing)
            self.assertFalse(off.configured)


if __name__ == "__main__":
    unittest.main()
