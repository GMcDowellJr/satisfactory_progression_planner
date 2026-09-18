from __future__ import annotations
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'tools'/'build_surface_tool'/'src'
sys.path.insert(0,str(SRC))

from build_surface_tool.cli import main

if __name__ == '__main__':
    args=['--policy', str(ROOT/'planning_data/analysis/policies/build_surfaces_v3.json')]
    args.extend(sys.argv[1:])
    raise SystemExit(main(args))
