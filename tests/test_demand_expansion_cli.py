"""The reference-output writer: files land, bytes repeat, names resolve."""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
CLI_PATH = REPO / "tools" / "demand_expansion_cli.py"

_spec = importlib.util.spec_from_file_location("demand_expansion_cli", CLI_PATH)
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)

FILES = (
    "dependency_coefficients.csv", "phase_demand.csv", "unresolved.csv",
    "provenance.json", "dataset.json", "report.md",
)


def test_generate_writes_the_six_files_and_repeats_byte_for_byte(tmp_path, capsys):
    a, b = tmp_path / "a", tmp_path / "b"
    assert cli.main(["generate", "--out", str(a)]) == 0
    assert cli.main(["generate", "--out", str(b)]) == 0
    for name in FILES:
        assert (a / name).is_file(), name
        if name != "provenance.json" and name != "dataset.json":
            assert (a / name).read_bytes() == (b / name).read_bytes(), name
        assert b"\r" not in (a / name).read_bytes(), name
    prov = json.loads((a / "provenance.json").read_text(encoding="utf-8"))
    assert prov["docs_sha256"].startswith("a81d250e96aa")
    assert prov["generated_at"] is not None
    assert prov["config_id"] == "default-2026-10-10/recipe1/pa1/fluid-mL"
    # the two provenance files differ only by the clock
    pb = json.loads((b / "provenance.json").read_text(encoding="utf-8"))
    pb["generated_at"] = prov["generated_at"]
    assert pb == prov
    assert "119 targets" in capsys.readouterr().out


def test_generate_under_a_scenario_names_its_configuration(tmp_path):
    out = tmp_path / "sor"
    assert cli.main([
        "generate", "--out", str(out), "--recipe-multiplier", "1.25",
        "--project-assembly-multiplier", "2", "--fluid-rounding", "m3",
    ]) == 0
    head = (out / "phase_demand.csv").read_text(encoding="utf-8").splitlines()
    assert head[0].startswith("config_id,item_id,")
    motor = [l for l in head if l.startswith("default-2026-10-10/recipe1.25/pa2/fluid-m3,Desc_Motor_C,")]
    assert [l.split(",")[5] for l in motor] == ["0.0", "0.0", "3000.0", "8250.0", "6600.0"]


def test_item_shows_destinations_and_phases(capsys):
    assert cli.main(["item", "Motor"]) == 0
    out = capsys.readouterr().out
    assert "Thermal Propulsion Rocket" in out
    assert "         9  d2  Thermal Propulsion Rocket" in out
    assert "phase 4:       2250" in out
    assert "phase 5:       1800+" in out


def test_target_expands_or_refuses_by_name(capsys):
    assert cli.main(["target", "Plastic"]) == 0
    assert "Coproducts" in capsys.readouterr().out
    assert cli.main(["target", "Biochemical Sculptor"]) == 2
    assert "AmbiguousRoute: Desc_FicsiteIngot_C" in capsys.readouterr().out


def test_an_unknown_or_ambiguous_name_is_refused():
    with pytest.raises(SystemExit, match="matches 0 items"):
        cli.main(["item", "Smart Plates"])
