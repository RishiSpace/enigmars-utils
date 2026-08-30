from __future__ import annotations

import unittest

from enigmars_util.paths import icon_path


class PathsTest(unittest.TestCase):
    def test_icon_is_enigmarsos_mark(self) -> None:
        path = icon_path()
        self.assertTrue(path.is_file(), path)
        self.assertTrue(
            path.name.startswith("EnigmarsOS") or path.name.startswith("enigmarsos"),
            path,
        )
