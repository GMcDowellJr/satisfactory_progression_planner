"""Power as a carry-forward mix — scratch driver, 2026-10-26. NOT repo code.
Reuses node_ceiling.py (which reuses work_axis.py), exec'd from beside this.

Decided by Greg (2026-10-26 21:22): reading B. Plants built in earlier
phases keep running at the size they were built; the newest source covers
only the growth in demand. Plants are sized at the 1/1/1 pace (21:22,
"1/1/1 pace"). Geothermal enters from the phase where the MAM placement
puts Research_Caterium_7_2 (drop-pod access at the start is impractical,
Greg 21:22), as a capped add-on.

    demand     D_p = phase energy (power_axis.demand: manufacturing + ore +
               water, all x P, normal purity, highest open mark) / T_ref_p.
               MW at the reference pace, the "same pace" endpoint.
    sources    Biomass (Leaves, hand-fed, D21), Coal, Fuel, Nuclear (GENS),
               net MW per generator and machine-min per generator-minute from
               work_axis.plant (fuel chain + extractors + water, x P).
               Geothermal: one generator per geyser, used pure first, then
               normal, then impure. 200 MW base, purity 0.5/1/2x ASSUMED
               (no purity multiplier in the reference data), not P-scaled,
               no parasitic load. Cap: the default world's 31 geysers.
    rule       phase by phase. Carried generator COUNTS stay; their net MW is
               re-read at the new phase's extractor mark. If D_p exceeds the
               carried supply, the shortfall goes first to geothermal (if
               open, up to its cap), then to the newest open source that
               nets > 0. A newest source that nets <= 0 is skipped and the
               next newest covers it (named in the output). "Newest" is by
               unlock at the window's top tier (D12): Fuel at 5-5 covers phase
               3's growth, Nuclear at 8-1 phase 4's, though both open late in
               their windows.
    dispatch   every built plant runs at the same load factor D_p / supply,
               so a phase with lower demand idles all plants equally.
    work       plant machine-min = generator-minutes x machine-min per
               generator-minute; total = factory (PA + ms + MAM + ext, as
               §5.6) + plant, / the 1/1/1 total under the same rule.
    nodes      the mix's raw draw at the 1/1/1 pace (factory bill / T_ref plus
               the plant's fuel chains) against the default world's sockets
               (node_ceiling.segments: world purity, phase mark, belt). Listed
               when over. This is a check of one plan, not the ceiling k.

Usage: python -I carry_forward.py <repo> [R:P:E ...] [--no-geo]   (--no-geo: geothermal left out, for comparison)
"""
import sys, pathlib
here = pathlib.Path(__file__).parent
cf_args = [a for a in sys.argv[2:] if a != "--no-geo"]
NO_GEO = "--no-geo" in sys.argv[2:]
sys.argv = [str(here / "node_ceiling.py"), sys.argv[1]]
src = open(here / "node_ceiling.py").read().split('print("world sockets used"')[0]
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(src, str(here / "node_ceiling.py"), "exec"))

GEO_NODE = "Research_Caterium_7_2_C"
GEO_PHASE = None if NO_GEO else placed.get(GEO_NODE)
GEO_MW = {"pure": 400.0, "normal": 200.0, "impure": 100.0}      # ASSUMED 0.5/1/2 x 200
GEYSERS = collections.Counter(r["purity"] for r in csv.DictReader(open(WORLD))
                              if "Geyser" in r["socket_id"])
GEO_STACK = [GEO_MW[p] for p in ("pure", "normal", "impure") for _ in range(GEYSERS[p])]
GEO_CAP = sum(GEO_STACK)
ORDER = ["Biomass", "Coal", "Fuel", "Nuclear"]       # unlock order (D6)
K_ = 1e-3


def geo_count(mw):
    n, left = 0, mw
    for m in GEO_STACK:
        if left <= 1e-9:
            break
        n += min(1.0, left / m); left -= m
    return n


def raws_for(data, bill, ph):
    bill = {i: q for i, q in bill.items() if q > 0 and i in names}
    if not bill:
        return {}
    r = be.solve(SolveRequest(outputs=tuple(OutputTarget(i, q * K_) for i, q in bill.items()),
                              allowed_recipes=priced_recipes(ph)), data)
    return {x.item_id: x.rate_per_min / K_ for x in r.raw_inputs if x.item_id not in PICKUPS}


def run(R, P, E):
    data = scenario_data(R, P)
    counts = {}          # source -> generators built
    geo_mw = 0.0
    out = []
    for ph in TOP:
        open_now = [gname(g) for g in gens_open(ph)]
        gens = {gname(g): g for g in gens_open(ph)}
        info = {s: plant(R, P, ph, gens[s]) for s in open_now}      # (net MW, machine-min per gen-min)
        D = sum(demand(R, P, ph, E)) / T_REF[ph]
        supply = geo_mw + sum(c * info[s][0] for s, c in counts.items() if info[s][0] > 0)
        note = []
        if D > supply:
            short = D - supply
            if GEO_PHASE is not None and ph >= GEO_PHASE and geo_mw < GEO_CAP:
                add = min(short, GEO_CAP - geo_mw); geo_mw += add; short -= add
            if short > 1e-9:
                for s in reversed([x for x in ORDER if x in open_now]):
                    if info[s][0] > 0:
                        counts[s] = counts.get(s, 0.0) + short / info[s][0]
                        break
                    note.append(f"{s} nets {info[s][0]:.0f} MW: skipped")
            supply = D
        load = D / supply if supply > 0 else 0.0
        t = T_REF[ph]
        plant_w = sum(c * load * t * info[s][1] for s, c in counts.items() if info[s][0] > 0)
        plant_w += geo_count(geo_mw) * load * t
        parts, _ = phase_work(R, P, E, ph)
        fac_w = sum(parts.values())
        # node check at the 1/1/1 pace
        pab, msb, mmb = bills(ph)
        bill = collections.Counter()
        for i, q in pab.items(): bill[i] += E * q / t
        for b in (msb, mmb):
            for i, q in b.items(): bill[i] += q / t
        draw = collections.Counter(raws_for(data, bill, ph))
        for s, c in counts.items():
            g = gens[s]
            if info[s][0] <= 0 or g.fuel_item_id in PICKUPS:
                continue
            for i, q in raws_for(data, {g.fuel_item_id: g.burn_rate_per_min}, ph).items():
                draw[i] += c * load * q
            for i, q in g.supplemental:
                draw[i] += c * load * q
        caps = segments(ph, P)[1]
        over = {names.get(i, i): round(draw[i] / caps[i], 2) for i in draw
                if i in caps and caps[i] > 0 and draw[i] > caps[i] * 1.0001}
        missing = sorted(names.get(i, i) for i in draw if draw[i] > 1e-6 and i not in caps and i != WATER)
        out.append(dict(ph=ph, D=D, counts=dict(counts), geo=geo_mw, load=load, fac=fac_w,
                        plant=plant_w, over=over, missing=missing, note=note,
                        net={s: info[s][0] for s in open_now}))
    return out


def show(R, P, E, base_rows):
    rows = run(R, P, E)
    print(f"== R{R:g} P{P:g} E{E:g}   plant sized at the 1/1/1 pace; work x vs 1/1/1 under the same rule"
          f"   (geothermal from ph{GEO_PHASE}, cap {GEO_CAP:,.0f} MW)")
    for r, b in zip(rows, base_rows):
        mix = ", ".join(f"{s} {c:,.0f}" for s, c in r["counts"].items() if c > 0.5)
        if r["geo"] > 0:
            mix += f", Geo {r['geo']:,.0f} MW"
        tot = (r["fac"] + r["plant"]) / (b["fac"] + b["plant"])
        print(f"  ph{r['ph']} D {r['D']:9,.0f} MW  load {r['load']:.2f}  [{mix}]  "
              f"work {tot:6.2f} = factory {r['fac']/(b['fac']+b['plant']):.2f} + plant {r['plant']/(b['fac']+b['plant']):.2f}"
              + (f"  OVER {r['over']}" if r["over"] else "")
              + (f"  {'; '.join(r['note'])}" if r["note"] else "")
              + (f"  unmapped {r['missing']}" if r["missing"] else ""))


BASE_ROWS = run(1.0, 1.0, 1.0)
print("geysers:", dict(GEYSERS), "geothermal MAM phase:", GEO_PHASE)
for a in (cf_args or ["1:1:1", "1.25:1:1", "2:1:1", "1:5:1", "1.25:5:1", "2:5:1", "1:1:10"]):
    show(*(float(x) for x in a.split(":")), BASE_ROWS)
