#!/usr/bin/env python3
"""Repository wrapper for tools/build_surface_tool."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOL_SRC = ROOT / "tools" / "build_surface_tool" / "src"
if str(TOOL_SRC) not in sys.path:
    sys.path.insert(0, str(TOOL_SRC))

from build_surface_tool.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
