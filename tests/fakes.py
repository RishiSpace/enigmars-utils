from __future__ import annotations


class FakeFS:
    def __init__(self, files: dict[str, str] | None = None, bins: set[str] | None = None) -> None:
        self.files = files or {}
        self.bins = bins or set()

    def read(self, path: str) -> str | None:
        return self.files.get(path)

    def exists(self, path: str) -> bool:
        return path in self.files

    def which(self, name: str) -> str | None:
        if name in self.bins:
            return f"/usr/bin/{name}"
        return None
