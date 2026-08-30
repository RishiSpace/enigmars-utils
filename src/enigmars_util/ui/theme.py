from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

ACCENT = "#00E5FF"
PURPLE = "#7B2FFF"
BG = "#000000"
CARD = "#0C0C0C"
BORDER = "#1E1E1E"
TEXT = "#F5F5F5"
MUTED = "#8A8A8A"

AMOLED_QSS = f"""
QMainWindow, QWidget#root {{
    background-color: {BG};
    color: {TEXT};
    font-family: Inter, "Noto Sans", sans-serif;
    font-size: 13px;
}}
QLabel#hero {{
    font-size: 26px;
    font-weight: 600;
}}
QLabel#accent {{
    color: {ACCENT};
    font-size: 13px;
}}
QLabel#muted {{
    color: {MUTED};
}}
QLabel#cardTitle {{
    font-size: 15px;
    font-weight: 600;
}}
QFrame#card, QFrame#nav {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QPushButton {{
    background-color: #121212;
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px 14px;
    color: {TEXT};
}}
QPushButton:hover {{
    border: 1px solid {ACCENT};
    color: {ACCENT};
}}
QPushButton:pressed {{
    background-color: #1a1a1a;
}}
QPushButton#navBtn {{
    text-align: left;
    padding: 10px 14px;
    border: 1px solid transparent;
    background: transparent;
}}
QPushButton#navBtn:checked {{
    border: 1px solid {ACCENT};
    color: {ACCENT};
    background-color: #101010;
}}
QLineEdit, QPlainTextEdit, QTextEdit {{
    background-color: #101010;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 8px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: #000;
}}
QTableWidget, QListWidget, QTreeWidget {{
    background-color: {CARD};
    alternate-background-color: #101010;
    border: 1px solid {BORDER};
    border-radius: 10px;
    gridline-color: {BORDER};
    color: {TEXT};
}}
QHeaderView::section {{
    background-color: #101010;
    color: {MUTED};
    border: none;
    padding: 6px;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QCheckBox, QLabel {{
    color: {TEXT};
}}
QSplitter::handle {{
    background: {BORDER};
}}
QMessageBox {{
    background-color: {BG};
    color: {TEXT};
}}
QScrollBar:vertical {{
    background: {CARD};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 24px;
    border-radius: 4px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


def apply_theme(app: QApplication, enigmarsos: bool = True) -> None:
    # Product chrome is always the AMOLED sheet. objectName styles (cards, hero)
    # do not exist in a stock Fusion theme, so skipping QSS leaves the UI unreadable.
    del enigmarsos
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(BG))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Base, QColor(CARD))
    pal.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Button, QColor("#121212"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(MUTED))
    app.setPalette(pal)
    app.setStyleSheet(AMOLED_QSS)
