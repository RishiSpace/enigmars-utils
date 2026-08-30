from __future__ import annotations

import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from enigmars_util import __version__
from enigmars_util.paths import icon_path
from enigmars_util.ui.main_window import MainWindow
from enigmars_util.ui.theme import apply_theme


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if os.geteuid() == 0:
        app = QApplication(argv)
        QMessageBox.critical(
            None,
            "Enigmars Utils",
            "Do not run this program as root. Use the polkit helper for privileged actions.",
        )
        return 1
    app = QApplication(argv)
    app.setApplicationName("Enigmars Utils")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("EnigmarsOS")
    apply_theme(app)
    icon = icon_path()
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
