from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"tools"/"corridor_tool"/"src"
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))
from corridor_tool.cli import main
if __name__=="__main__": raise SystemExit(main())
