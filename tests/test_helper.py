from __future__ import annotations

import os
import unittest

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


if __name__ == "__main__":
    unittest.main()
