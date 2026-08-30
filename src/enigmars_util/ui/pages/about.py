from __future__ import annotations

import tomllib
import webbrowser

from PySide6.QtWidgets import QVBoxLayout, QWidget

from enigmars_util.paths import data_root
from enigmars_util.profile import HostProfile
from enigmars_util.ui.widgets import Card, button


def _links(enigmarsos: bool) -> dict[str, str]:
    name = "enigmarsos.toml" if enigmarsos else "generic.toml"
    path = data_root() / "branding" / name
    if not path.is_file():
        return {
            "Documentation": "https://enigmarsos.rishispace.dev/docs",
            "Website": "https://enigmarsos.rishispace.dev",
            "GitHub": "https://github.com/RishiSpace/EnigmarsOS",
        }
    with path.open("rb") as fh:
        doc = tomllib.load(fh)
    links = doc.get("links") or {}
    return {str(k): str(v) for k, v in links.items()}


class AboutPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._card: Card | None = None
        self._layout.addStretch()

    def set_profile(self, profile: HostProfile) -> None:
        if self._card:
            self._layout.removeWidget(self._card)
            self._card.deleteLater()
        from enigmars_util import __version__

        self._card = Card(
            "About",
            f"{profile.pretty_name}\nEnigmars Utils {__version__}\nNo telemetry.",
        )
        for label, url in _links(profile.enigmarsos).items():
            self._card.body.addWidget(button(f"Open {label}", lambda u=url: webbrowser.open(u)))
        self._layout.insertWidget(0, self._card)
