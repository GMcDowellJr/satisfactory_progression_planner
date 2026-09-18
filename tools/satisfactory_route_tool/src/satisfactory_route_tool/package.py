from __future__ import annotations

import io
import zipfile
from pathlib import Path


class PlannerPackage:
    """Read an unpacked planner directory or a planner ZIP without extracting it."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._zip = None
        self._prefix = ""
        if self.path.is_file() and self.path.suffix.lower() == ".zip":
            self._zip = zipfile.ZipFile(self.path)
            names = [n for n in self._zip.namelist() if n and not n.endswith("/")]
            roots = {n.split("/", 1)[0] for n in names if "/" in n}
            self._prefix = (sorted(roots)[0] + "/") if len(roots) == 1 else ""
        elif not self.path.is_dir():
            raise FileNotFoundError(path)

    def read_bytes(self, rel: str) -> bytes:
        rel = rel.replace("\\", "/")
        if self._zip is not None:
            return self._zip.read(self._prefix + rel)
        return (self.path / rel).read_bytes()

    def read_text(self, rel: str, encoding="utf-8") -> str:
        return self.read_bytes(rel).decode(encoding)

    def exists(self, rel: str) -> bool:
        rel = rel.replace("\\", "/")
        if self._zip is not None:
            try:
                self._zip.getinfo(self._prefix + rel)
                return True
            except KeyError:
                return False
        return (self.path / rel).exists()
