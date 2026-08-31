from __future__ import annotations

import os
import unittest

from enigmars_util.privileged import helper_executable
from enigmars_util_helper.__main__ import main


class HelperTest(unittest.TestCase):
    def test_refuses_non_root(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("running as root")
        rc = main(["pkg-update"])
        self.assertEqual(rc, 2)

    def test_unknown_verb(self) -> None:
        rc = main(["rm", "-rf", "/"])
        self.assertEqual(rc, 2)

    def test_bad_package_before_root(self) -> None:
        rc = main(["pkg-install", "foo;bar"])
        self.assertEqual(rc, 2)

    def test_sbctl_enroll_rejects_extra_args(self) -> None:
        rc = main(["sbctl-enroll", "extra"])
        self.assertEqual(rc, 2)

    def test_aur_helper_rejects_unknown_and_extra(self) -> None:
        self.assertEqual(main(["aur-helper-setup"]), 2)
        self.assertEqual(main(["aur-helper-setup", "pikaur"]), 2)
        self.assertEqual(main(["aur-helper-setup", "yay", "extra"]), 2)
        self.assertEqual(main(["aur-helper-setup", "yay;rm"]), 2)

    def test_appimage_helper_from_appdir(self) -> None:
        import os
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as raw:
            helper = Path(raw) / "usr/libexec/enigmars-util-helper"
            helper.parent.mkdir(parents=True)
            helper.write_text("#!/bin/sh\n")
            helper.chmod(0o755)
            old = os.environ.get("APPDIR")
            os.environ["APPDIR"] = raw
            try:
                found = helper_executable()
            finally:
                if old is None:
                    os.environ.pop("APPDIR", None)
                else:
                    os.environ["APPDIR"] = old
            if found == Path("/usr/libexec/enigmars-util-helper"):
                self.skipTest("system helper already installed")
            self.assertEqual(found, helper)


if __name__ == "__main__":
    unittest.main()
