from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from enigmars_util.paths import state_dir


def audit_path() -> Path:
    return state_dir() / "audit.log"


def log_action(verb: str, detail: str, ok: bool) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{stamp} ok={int(ok)} verb={verb} {detail}\n"
    path = audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
