from __future__ import annotations

import unittest

from PySide6.QtCore import QSize

from enigmars_util.ui.layout import clamp_launch_size


class ClampLaunchSizeTest(unittest.TestCase):
    def test_uses_preferred_when_screen_is_large(self) -> None:
        got = clamp_launch_size(QSize(1200, 900), QSize(1920, 1080), margin=48)
        self.assertEqual(got, QSize(1200, 900))

    def test_shrinks_to_available_minus_margin(self) -> None:
        got = clamp_launch_size(QSize(1600, 1200), QSize(1366, 768), margin=48)
        self.assertEqual(got, QSize(1366 - 48, 768 - 48))

    def test_tiny_screen(self) -> None:
        got = clamp_launch_size(QSize(1200, 900), QSize(800, 480), margin=48)
        self.assertEqual(got.width(), 752)
        self.assertEqual(got.height(), 432)


if __name__ == "__main__":
    unittest.main()
