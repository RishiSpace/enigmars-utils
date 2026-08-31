"""Launch-size helpers. Keep window on-screen and large enough to avoid Home scrolling."""

from __future__ import annotations

from PySide6.QtCore import QSize


def clamp_launch_size(preferred: QSize, available: QSize, *, margin: int = 48) -> QSize:
    """Fit preferred size into available screen, leaving a margin for panels."""
    max_w = max(1, available.width() - margin)
    max_h = max(1, available.height() - margin)
    return QSize(min(preferred.width(), max_w), min(preferred.height(), max_h))
