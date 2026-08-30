from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QProcess, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from enigmars_util.audit import log_action
from enigmars_util.protocol import RESULT_PREFIX


class Card(QFrame):
    def __init__(self, title: str, body: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        t = QLabel(title)
        t.setObjectName("cardTitle")
        layout.addWidget(t)
        if body:
            b = QLabel(body)
            b.setObjectName("muted")
            b.setWordWrap(True)
            layout.addWidget(b)
        self.body = layout


class Chip(QLabel):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("accent")
        self.setMargin(4)


class JobPane(QWidget):
    finished = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._proc: QProcess | None = None
        self._verb = ""
        self._buf = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(4000)
        self.log.setPlaceholderText("Command output appears here.")
        row = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel)
        row.addStretch()
        row.addWidget(self.cancel_btn)
        layout.addWidget(self.log)
        layout.addLayout(row)

    def busy(self) -> bool:
        return self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning

    def run(self, cmd: list[str], verb: str) -> None:
        if self.busy():
            QMessageBox.information(self, "Busy", "A privileged job is already running.")
            return
        self._verb = verb
        self._buf = ""
        self.log.appendPlainText("$ " + " ".join(cmd))
        proc = QProcess(self)
        self._proc = proc
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(self._read)
        proc.finished.connect(self._done)
        self.cancel_btn.setEnabled(True)
        proc.start(cmd[0], cmd[1:])
        if proc.state() == QProcess.ProcessState.NotRunning and proc.error() != QProcess.ProcessError.UnknownError:
            self.log.appendPlainText(proc.errorString())
            self.cancel_btn.setEnabled(False)
            self.finished.emit(False)

    def cancel(self) -> None:
        if self._proc and self.busy():
            self._proc.terminate()

    def _read(self) -> None:
        if not self._proc:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._consume(data)

    def _consume(self, data: str) -> None:
        self._buf += data
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.startswith(RESULT_PREFIX):
                continue
            self.log.appendPlainText(line)

    def _done(self, code: int, _status: QProcess.ExitStatus) -> None:
        if self._buf:
            self._consume(self._buf + "\n")
            self._buf = ""
        self.cancel_btn.setEnabled(False)
        ok = code == 0
        self.log.appendPlainText("Finished." if ok else f"Failed (exit {code}).")
        log_action(self._verb, "job", ok)
        self.finished.emit(ok)
        self._proc = None


def confirm(parent: QWidget, title: str, text: str) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
    return box.exec() == QMessageBox.StandardButton.Ok


def warn(parent: QWidget, title: str, text: str) -> None:
    QMessageBox.warning(parent, title, text)


def info(parent: QWidget, title: str, text: str) -> None:
    QMessageBox.information(parent, title, text)


def hbox(*widgets: QWidget, stretch: bool = True) -> QWidget:
    w = QWidget()
    layout = QHBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    for item in widgets:
        layout.addWidget(item)
    if stretch:
        layout.addStretch()
    return w


def button(label: str, slot: Callable[[], None]) -> QPushButton:
    b = QPushButton(label)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.clicked.connect(slot)
    return b
