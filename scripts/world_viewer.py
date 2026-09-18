#!/usr/bin/env python3
"""Repository-local wrapper for tools/world_viewer without requiring installation."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "world_viewer" / "src"))

from world_viewer.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
