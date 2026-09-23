"""The oracle's second job: `worked_case_A4` through the realization bodies.

`tools/busmodel` has two jobs. The first — reproduce the record — its own suite
carries. The second is to give `realization.buses` something to be checked
against that is not itself. Until amendment 8 the two layers sized on different
bases and a comparison would have disagreed for a known reason; from A8 both
sized on USAGE. Since amendment 12 both size on the STORAGE TOGGLE — busmodel
under `SizingBasis.STORAGE`, realization unconditionally — so every row below
is a check on D1. The USAGE agreement A9 recorded is kept below, with every
line's storage off, because A12 did not retract it.

**The translation is the risk, not the bodies.** busmodel DECLARES out-of-scope
demand (`Declaration.external_per_min`); realization DERIVES it from a
`SolveResponse` as `machine_equivalents * rate - automated`. So the response
built here carries exactly one `RecipeUse` — the root, whose equivalents are
`external / rate` — and every other bus names its recipe and is DECLARED, so
its derived external is zero by absence, which is what busmodel declares for
it. `test_the_translation_is_what_it_claims` pins that, so a disagreement below
is attributable to a body and not to this file.

Residuals are NOT compared as numbers. The two layers define them differently
and both definitions are recorded: busmodel's `supply - demand` includes the
withdrawal and external in `demand`; realization's `supply - automated` leaves
them out on purpose (`residual_for`). And a MATCHED bus reports its CLOCKED
supply in busmodel and its nameplate in realization. The test compares what
each layer means by the same quantity instead.
"""
from __future__ import annotations

import dataclasses
import pathlib

import pytest

from busmodel import declarations as D
from busmodel.model import SizingBasis, solve
from production_adapter import gamedata
from production_adapter.contracts import (
    ItemFlow, PowerReport, RecipeUse, SolveResponse,
)
from production_adapter.scenario import MARGINAL_PEAK_DEBOTTLENECK
from realization import buses as B
from realization.contracts import (
    BusDeclaration, Disposition, RealizationRequest, RecipeProvenance, SourceEdge,
)

REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def scaled():
    return gamedata.load(REPO).with_scenario(MARGINAL_PEAK_DEBOTTLENECK)


@pytest.fixture(scope="module")
def caps():
    return gamedata.load_logistics(REPO)[0]


def _translate(decl, data):
    request = RealizationRequest(
        design_tier=4,
        buses=tuple(
            BusDeclaration(
                bus_id=b.bus_id, item_id=b.item_id, recipe_id=b.recipe_id,
                sources=tuple(SourceEdge(e.input_item, e.source_bus_id) for e in b.sources),
                stores=b.stores,
                withdrawal_per_min=b.withdrawal_per_min,
                extra_producers=b.extra_producers,
                # The record path carried across, so the two layers see the
                # same disposition on the record's BACK_UP-with-withdrawal
                # lines. This file is a test; the inspection in busmodel's
                # `test_refusals.py` covers `tools/*/src` only.
                recorded_disposition=b.recorded_disposition,
            )
            for b in decl.buses
        ),
    )
    recipes = []
    for bus_id, per_min in decl.external_per_min.items():
        spec = decl.bus(bus_id)
        recipe = data.recipes[spec.recipe_id]
        rate = next(r for item, r in recipe.outputs if item == spec.item_id)
        recipes.append(RecipeUse(spec.recipe_id, recipe.producer_class, per_min / rate, 1.0))
    response = SolveResponse(
        recipes=tuple(recipes),
        items=tuple(ItemFlow(decl.bus(k).item_id, 1.0, 1.0) for k in decl.external_per_min),
        raw_inputs=(),
        power=PowerReport(0.0, 0.0, 0.0, 0.0),
        machines=(),
        backend="oracle-translation",
    )
    return request, response


def _storage_off(decl):
    """Every line with storage OFF and no record path: the toggle alone. Under
    STORAGE this is USAGE by construction (busmodel `test_refusals.py`)."""
    return dataclasses.replace(
        decl,
        buses=tuple(
            dataclasses.replace(b, stores=False, recorded_disposition=None)
            for b in decl.buses
        ),
    )


def _run(decl, scaled, caps):
    oracle = solve(decl, scaled)   # the default, STORAGE
    request, response = _translate(decl, scaled)
    bodies = {b.bus_id: b for b in B.buses_from_response(response, scaled, request, caps)}
    return decl, oracle, request, response, bodies


@pytest.fixture(scope="module", params=["storage", "storage_off"])
def both(request, scaled, caps):
    """A12: the worked case as declared (its WITHDRAWN lines store), and with
    every line's storage off — A9's USAGE agreement, restated on the toggle."""
    decl = D.worked_case_a4(scaled)
    if request.param == "storage_off":
        decl = _storage_off(decl)
    return _run(decl, scaled, caps)


def test_the_translation_is_what_it_claims(both, scaled):
    """One SOLVED bus — the root, at busmodel's declared external — and every
    other bus DECLARED, so no other bus can acquire an external term."""
    decl, _oracle, request, response, _bodies = both
    attributed = B._attribute(response, scaled, request)
    solved = {k for k, v in attributed.items() if v.provenance is RecipeProvenance.SOLVED}
    assert solved == set(decl.external_per_min) == {"smart_plating"}
    assert attributed["smart_plating"].machine_equivalents == pytest.approx(1.0)


def test_every_bus_agrees_on_machines_and_automated_demand(both):
    decl, oracle, _request, _response, bodies = both
    for spec in decl.buses:
        o, r = oracle[spec.bus_id], bodies[spec.bus_id]
        assert r.machines == o.machines, spec.bus_id
        assert r.automated_demand_per_min == pytest.approx(o.automated_demand_per_min), spec.bus_id
        assert r.withdrawal_per_min == pytest.approx(o.withdrawal_per_min), spec.bus_id


def test_every_consumer_agrees_on_usage_and_peak(both):
    """Both layers report a peak per consumer since amendment 8. Keyed by the
    consumer's recipe on the realization side and its bus on busmodel's; within
    one bus the worked case never has two consumers on one recipe."""
    decl, oracle, _request, _response, bodies = both
    recipe_of = {b.bus_id: b.recipe_id for b in decl.buses}
    for spec in decl.buses:
        mine = {(c.recipe_id, round(c.draw_per_min, 6), round(c.peak_per_min, 6))
                for c in bodies[spec.bus_id].consumers}
        theirs = {(recipe_of[c.bus_id] if c.bus_id is not None else None,
                   round(c.draw_per_min, 6), round(c.peak_per_min, 6))
                  for c in oracle[spec.bus_id].consumers}
        assert mine == theirs, spec.bus_id


def test_supply_agrees_where_both_layers_mean_nameplate(both):
    """Every state but MATCHED reports nameplate in both layers. Under MATCHED
    busmodel reports the clocked supply and realization's lanes report their
    rate at their clock — the same figure by a different road."""
    decl, oracle, _request, _response, bodies = both
    for spec in decl.buses:
        o, r = oracle[spec.bus_id], bodies[spec.bus_id]
        if spec.disposition is Disposition.MATCHED:
            clocked = sum(l.output_rate_per_min for l in r.lanes)
            assert clocked == pytest.approx(o.supply_per_min), spec.bus_id
        else:
            assert r.supply_per_min == pytest.approx(o.supply_per_min), spec.bus_id


def test_storage_off_is_amendment_6s_usage_column(scaled, caps):
    """A6.3, USAGE: 23 machines, and Iron Ingot at 115.89/min on 4 Smelters.
    Restated from the record, not from either body. Since A12 reached by
    turning every line's storage off."""
    _decl, oracle, _request, _response, bodies = _run(
        _storage_off(D.worked_case_a4(scaled)), scaled, caps,
    )
    assert sum(b.machines for b in bodies.values()) == 23 == oracle.total_machines
    assert bodies["iron_ingot"].machines == 4
    assert bodies["iron_ingot"].automated_demand_per_min == pytest.approx(115.89, abs=0.005)


def test_storage_on_is_amendment_6s_record_column(scaled, caps):
    """A12: the worked case as declared, both layers on the toggle. 29 machines
    and Iron Ingot at 204.00/min on 7 Smelters — A6.3's AVERAGE column,
    because the record's WITHDRAWN lines are exactly its storing lines.
    Restated from the record, not from either body."""
    _decl, oracle, _request, _response, bodies = _run(
        D.worked_case_a4(scaled), scaled, caps,
    )
    assert sum(b.machines for b in bodies.values()) == 29 == oracle.total_machines
    assert bodies["iron_ingot"].machines == 7
    assert bodies["iron_ingot"].automated_demand_per_min == pytest.approx(204.00, abs=0.005)
