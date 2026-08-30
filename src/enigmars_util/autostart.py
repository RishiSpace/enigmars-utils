from __future__ import annotations

from enigmars_util.paths import autostart_path

DESKTOP = """[Desktop Entry]
Type=Application
Name=Enigmars Utils
Exec=enigmars-util
Icon=enigmarsos
X-KDE-autostart-phase=1
X-GNOME-Autostart-enabled=true
"""


def enabled() -> bool:
    return autostart_path().is_file()


def set_enabled(on: bool) -> None:
    path = autostart_path()
    if on:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DESKTOP, encoding="utf-8")
    elif path.exists():
        path.unlink()
