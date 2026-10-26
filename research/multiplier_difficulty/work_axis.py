"""Work multiplier with power plant and extractors (D24) — scratch, 2026-10-26.
NOT repo code. Reuses mam_bill.py and power_axis.py (exec'd from beside this).

Work components, machine-minutes for the whole phase bill, each / W_total(1/1/1):
    PA, ms, MAM    LP recipe machine-equivalents (as §5.3)
    ext            factory extractors: raw rate / per-extractor rate, highest
                   open mark (D12), normal purity. NEW: §5.2–5.4 did not count
                   extractors at all; shown as its own component (D22).
    plant          per generator type (D25, whole set): generators + the
                   recipe machines making their fuel + the extractors for that
                   fuel and its water. Generator-minutes = demand energy /
                   net MW per generator (§5.5). Biomass (hand-fed Leaves): the
                   burners only.
Baseline 1/1/1 uses the SAME generator type, so each generator gets its own
multiplier; nothing is chosen.

Usage: python -I work_axis.py <repo> R:P:E [R:P:E ...]
"""
import sys, pathlib
here = pathlib.Path(__file__).parent
WORK_SCEN = [tuple(float(x) for x in a.split(":")) for a in sys.argv[2:]] or [(1.0, 5.0, 1.0)]
sys.argv = [str(here / "power_axis.py"), sys.argv[1]]
src = open(here / "power_axis.py").read().split("base_d = {ph")[0]
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(src, "power_axis", "exec"))


def per_unit_extractor(item, ph):
    open_cls = set(unlocks.extractors_open_at_tier(repo, TOP[ph]).get(item, ()))
    for c in MARK:
        if c in open_cls and c in EMAP.get(item, ()):
            return 1.0 / (RATE.get((c, "normal")) or RATE.get((c, "none")))
    return 0.0


def solve_full(data, bill, ph, P):
    """(recipe machine-min, extractor machine-min, energy MW-min) for a bill."""
    bill = {i: q for i, q in bill.items() if q > 0 and i in names}
    if not bill:
        return 0.0, 0.0, 0.0
    r = be.solve(SolveRequest(outputs=tuple(OutputTarget(i, q * K) for i, q in bill.items()),
                              allowed_recipes=priced_recipes(ph)), data)
    ext = en = 0.0
    for x in r.raw_inputs:
        if x.item_id in PICKUPS:
            continue
        ext += x.rate_per_min / K * per_unit_extractor(x.item_id, ph)
        en += x.rate_per_min / K * mw_per_unit(x.item_id, ph) * P
    return sum(u.machine_equivalents for u in r.recipes) / K, ext, r.power.scenario_mw / K + en


def plant(R, P, ph, g):
    """(net MW per generator, machine-min per generator-minute incl. itself)."""
    data = scenario_data(R, P)
    mach = ext = en = 0.0
    if g.fuel_item_id not in PICKUPS:
        mach, ext, en = solve_full(data, {g.fuel_item_id: g.burn_rate_per_min}, ph, P)
    for i, q in g.supplemental:
        ext += q * per_unit_extractor(i, ph)
        en += q * mw_per_unit(i, ph) * P
    return g.power_mw - en, 1.0 + mach + ext


def phase_work(R, P, E, ph):
    data = scenario_data(R, P)
    pab, msb, mmb = bills(ph)
    parts = {}
    tot_ext = tot_en = 0.0
    for k, b in (("PA", {i: E * q for i, q in pab.items()}), ("ms", msb), ("MAM", mmb)):
        m, x, e = solve_full(data, b, ph, P)
        parts[k] = m; tot_ext += x; tot_en += e
    parts["ext"] = tot_ext
    plants = {}
    for c in unlocks.generators_open_at_tier(repo, TOP[ph], tuple(GENS)):
        net, per_gen = plant(R, P, ph, GENS[c])
        plants[c.split("_")[1].replace("Generator", "")] = tot_en / net * per_gen if net > 0 else float("inf")
    return parts, plants


base_w = {ph: phase_work(1.0, 1.0, 1.0, ph) for ph in TOP}
for R, P, E in WORK_SCEN:
    print(f"== R{R:g} P{P:g} E{E:g}   per generator: total = PA + ms + MAM + ext + plant   (vs 1/1/1, same generator)")
    for ph in TOP:
        parts, plants = phase_work(R, P, E, ph)
        bparts, bplants = base_w[ph]
        cells = []
        for gname, pw in plants.items():
            b = sum(bparts.values()) + bplants[gname]
            comp = [parts[k] / b for k in ("PA", "ms", "MAM", "ext")] + [pw / b]
            cells.append(f"{gname} {sum(comp):.2f} = " + "+".join(f"{c:.2f}" for c in comp))
        print(f"  ph{ph}  " + " | ".join(cells))
