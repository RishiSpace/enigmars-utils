from __future__ import annotations

import argparse
import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from enigmars_util import __version__
from enigmars_util.paths import icon_path
from enigmars_util.ui.main_window import MainWindow
from enigmars_util.ui.theme import apply_theme


def _parse(argv: list[str]) -> tuple[str | None, list[str]]:
    parser = argparse.ArgumentParser(prog="enigmars-util", add_help=True)
    parser.add_argument("--page", default="", help="Open a tab (home, tweaks, packages, kernel, drivers, secure-boot, about)")
    args, rest = parser.parse_known_args(argv[1:])
    page = args.page.strip() or None
    return page, [argv[0], *rest]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    page, qt_argv = _parse(argv)
    if os.geteuid() == 0:
        app = QApplication(qt_argv)
        QMessageBox.critical(
            None,
            "Enigmars Utils",
            "Do not run this program as root. Use the polkit helper for privileged actions.",
        )
        return 1
    app = QApplication(qt_argv)
    app.setApplicationName("Enigmars Utils")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("EnigmarsOS")
    apply_theme(app)
    icon = icon_path()
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    win = MainWindow(start_page=page)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
