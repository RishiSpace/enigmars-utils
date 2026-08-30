from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from enigmars_util.catalog import Tweak, tweaks_for
from enigmars_util.profile import HostProfile
from enigmars_util.tweaks import TweakError, apply_tweak, is_applied, preview, undo_tweak
from enigmars_util.ui.widgets import Card, button, confirm, info, warn


class TweaksPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profile: HostProfile | None = None
        self._tweaks: list[Tweak] = []
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Tweaks are filtered for this desktop. Each change is reversible."))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.inner = QWidget()
        self.list = QVBoxLayout(self.inner)
        self.list.addStretch()
        scroll.setWidget(self.inner)
        root.addWidget(scroll, 1)

    def set_profile(self, profile: HostProfile) -> None:
        self._profile = profile
        self._tweaks = tweaks_for(profile)
        while self.list.count():
            item = self.list.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        groups: dict[str, list[Tweak]] = {}
        for t in self._tweaks:
            groups.setdefault(t.group, []).append(t)
        for group, items in groups.items():
            card = Card(group)
            for t in items:
                card.body.addWidget(self._row(t))
            self.list.addWidget(card)
        if not self._tweaks:
            self.list.addWidget(Card("No tweaks", "No catalog entries match this desktop."))
        self.list.addStretch()

    def _row(self, tweak: Tweak) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 4, 0, 4)
        col = QVBoxLayout()
        title = QLabel(tweak.title)
        title.setObjectName("cardTitle")
        summary = QLabel(tweak.summary)
        summary.setObjectName("muted")
        summary.setWordWrap(True)
        col.addWidget(title)
        col.addWidget(summary)
        layout.addLayout(col, 1)
        state = QLabel("applied" if is_applied(tweak.id) else tweak.risk)
        state.setObjectName("accent")
        layout.addWidget(state)

        def do_apply() -> None:
            try:
                rows = preview(tweak)
            except TweakError as exc:
                warn(self, tweak.title, str(exc))
                return
            lines = "\n".join(f"{k}: {cur} → {new}" for k, cur, new in rows)
            if not confirm(self, tweak.title, f"Apply this tweak?\n\n{lines}"):
                return
            try:
                apply_tweak(tweak)
                info(self, tweak.title, "Applied.")
                state.setText("applied")
            except TweakError as exc:
                warn(self, tweak.title, str(exc))

        def do_undo() -> None:
            try:
                undo_tweak(tweak)
                info(self, tweak.title, "Restored previous value.")
                state.setText(tweak.risk)
            except TweakError as exc:
                warn(self, tweak.title, str(exc))

        layout.addWidget(button("Apply", do_apply))
        layout.addWidget(button("Undo", do_undo))
        return row
