"""Item facts the loader carries from items.csv: form and stack size.

Stack size added 2026-10-23 so a client of the portfolio record (and, later,
anything else) gets it through gamedata, the one loader, rather than reading
items.csv itself.
"""
from __future__ import annotations

import pathlib

import pytest

from production_adapter import load

REPO = pathlib.Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def data():
    return load(REPO)


def test_every_item_has_a_positive_integer_stack_size(data):
    bad = [i for i, x in data.items.items()
           if not isinstance(x.stack_size, int) or x.stack_size <= 0]
    assert bad == []


def test_stack_sizes_are_the_stated_ones(data):
    # cached_stack_size as items.csv states it (build 502094)
    assert data.items["Desc_PolymerResin_C"].stack_size == 200
    assert data.items["Desc_IronScrew_C"].stack_size == 500
    assert data.items["Desc_Coal_C"].stack_size == 100


def test_fluids_carry_the_fluid_stack_and_their_form(data):
    fuel = data.items["Desc_LiquidFuel_C"]
    assert (fuel.form, fuel.stack_size) == ("liquid", 50000)
    assert {x.form for x in data.items.values()} == {"solid", "liquid", "gas"}
