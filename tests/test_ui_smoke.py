from __future__ import annotations

import os
import unittest


@unittest.skipUnless(
    os.environ.get("ENIGMARS_UTIL_UI_TEST") == "1",
    "set ENIGMARS_UTIL_UI_TEST=1 to run offscreen UI smoke",
)
class UISmokeTest(unittest.TestCase):
    def test_window(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        from enigmars_util.ui.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        win = MainWindow()
        win.show()
        win.close()
        self.assertIsNotNone(app)
