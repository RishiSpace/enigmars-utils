from __future__ import annotations

import unittest

from enigmars_util.aur_helpers import SPECS, spec_for
from enigmars_util.names import validate_aur_helper
from enigmars_util.privileged import aur_helper_setup_cmd


class AurHelpersTest(unittest.TestCase):
    def test_specs_are_https_github(self) -> None:
        self.assertEqual(set(SPECS), {"yay", "paru"})
        for name, spec in SPECS.items():
            self.assertEqual(spec.name, name)
            self.assertTrue(spec.git_url.startswith("https://github.com/"))
            self.assertTrue(spec.git_url.endswith(".git"))
            self.assertIn("git", spec.pacman_deps)
            self.assertIn("base-devel", spec.pacman_deps)
            self.assertEqual(spec_for(name).git_url, spec.git_url)

    def test_spec_for_rejects_other_helpers(self) -> None:
        with self.assertRaises(ValueError):
            spec_for("pikaur")
        with self.assertRaises(ValueError):
            validate_aur_helper("https://evil.example/yay")
        with self.assertRaises(ValueError):
            aur_helper_setup_cmd("pikaur")


if __name__ == "__main__":
    unittest.main()
