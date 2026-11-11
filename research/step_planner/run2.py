# run2.py -- driver for model2: milestone tagging, bills, factory sim, machines, power block.
import csv, math
from collections import defaultdict
import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))  # EDIT (a): sibling imports under python -I; outputs into this folder
import model2 as M
P = M.P

# ---- power-plant spec (Greg 2026-10-27, rev 14:13) ----
# P1 biomass burners: Solid Biofuel when PMULT <= 1, Biomass direct when PMULT > 1 (2P, 5P)
# P2 coal | P3 keep coal, add fuel | P4 keep coal+fuel, add fuel | P5 add fuel.
# Nuclear is optional (not needed to finish): variant B only when NUCLEAR = True.
# PMULT = power-consumption multiplier (P of R/P/E): scales every consumer's MW, not generator output.
PMULT = 1.0
NUCLEAR = False
BIOFUEL = PMULT <= 1
POWER_BLDGS = [('Recipe_GeneratorBiomass_Automated_C', 'generator Biomass Burner (P1)')] + \
              ([('Recipe_Biofuel_C', 'recipe Solid Biofuel (P1 power, PMULT<=1)')] if BIOFUEL else []) + \
              [('Recipe_GeneratorCoal_C', 'generator Coal (P2+)'), ('Recipe_WaterPump_C', 'Water Extractor (coal gens, Alumina, N-chain)'),
               ('Recipe_Pipeline_C', 'Pipeline Mk.1 (fluids)'),
               ('Recipe_GeneratorFuel_C', 'generator Fuel (P3+)'), ('Recipe_ResidualFuel_C', 'recipe Residual Fuel (HOR -> Fuel)'),
               ('Recipe_OilPump_C', 'Oil Extractor'), ('Recipe_FrackingExtractor_C', 'Resource Well (Nitrogen Gas)'),
               ('Recipe_FrackingSmasher_C', 'Resource Well Pressurizer (Nitrogen Gas)')]
NUC_BLDGS = [('Recipe_GeneratorNuclear_C', 'generator Nuclear (P5 variant B)'), ('Recipe_NuclearFuelRod_C', 'recipe Uranium Fuel Rod (variant B)'),
             ('Recipe_UraniumCell_C', 'recipe Encased Uranium Cell (variant B)'), ('Recipe_SulfuricAcid_C', 'recipe Sulfuric Acid (variant B)')]
PRACT = [('Recipe_ConveyorBeltMk2_C', 'belt Mk.2'), ('Recipe_ConveyorBeltMk3_C', 'belt Mk.3'), ('Recipe_ConveyorBeltMk4_C', 'belt Mk.4'),
         ('Recipe_ConveyorBeltMk5_C', 'belt Mk.5'), ('Recipe_ConveyorBeltMk6_C', 'belt Mk.6'),
         ('Recipe_ConveyorAttachmentSplitter_C', 'splitter/merger'), ('Recipe_StorageContainerMk2_C', 'industrial storage (stockpile)'),
         ('Recipe_MinerMk2_C', 'Miner Mk.2'), ('Recipe_MinerMk3_C', 'Miner Mk.3'), ('Recipe_PipelineMK2_C', 'Pipeline Mk.2')]

# ---- 1. tag milestones (based on PA plan + power plan, not on optional milestone bills) ----
h0, _ = M.simulate({k: dict(M.PA[k]) for k in P})
used = {j for k in P for j, c in h0[k]['C'].items() if c > 1e-9} | {'Biomass', 'Fuel'} | ({'Solid Biofuel'} if BIOFUEL else set())
tags, req_items = M.tag_milestones(used, POWER_BLDGS, PRACT)
tagsB, _ = M.tag_milestones(used | {'Uranium Fuel Rod', 'Encased Uranium Cell', 'Sulfuric Acid'}, POWER_BLDGS+NUC_BLDGS, PRACT)
tB = {t['schematic_id']: t for t in tagsB}
for t in tags:
    b = tB[t['schematic_id']]
    t['tag_nuclear_variant'] = b['tag'] if b['tag'] != t['tag'] else ''
    if t['schematic_id'] == 'Schematic_7-3_C': t['tag_nuclear_variant'] = 'practical'; t['reason'] = (t['reason']+'; ' if t['reason'] else '')+'Hazmat Suit for uranium nodes (variant B)'
with open(HERE / 'milestones_tagged.csv', 'w', newline='') as f:  # EDIT (d): was cwd
    w = csv.writer(f, lineterminator="\n"); w.writerow(['schematic_id', 'name', 'tier', 'paid_in_phase', 'tag', 'tag_if_P5_nuclear', 'reason', 'cost'])  # EDIT (b)
    for t in tags: w.writerow([t['schematic_id'], t['name'], t['tier'], t['phase'], t['tag'], t['tag_nuclear_variant'], t['reason'],
                               '; '.join(f"{k} {v:g}" for k, v in t['cost'].items())])

def bills_for(sel):
    b = {k: defaultdict(float, M.PA[k]) for k in P}
    mb = {k: defaultdict(float) for k in P}
    for t in tags:
        if sel(t):
            for it, q in t['cost'].items(): b[t['phase']][it] += q; mb[t['phase']][it] += q
    return {k: dict(v) for k, v in b.items()}, mb
SCEN = {'all': lambda t: True, 'required': lambda t: t['tag'] == 'required', 'req+practical': lambda t: t['tag'] in ('required', 'practical'),
        'pa_only': lambda t: False}

# ---- 2. power block ----
def power_block(k, d_fac, hor_avail, st, variant, fuel_ok=True):
    # fuel_ok=False: Petroleum Power (5-5) not yet paid in this phase step; coal covers all growth (step model, model3.py)
    blk_mw = 0.0
    for _ in range(50):
        Dm = (d_fac+blk_mw)*PMULT; gens = {}; prod_dem = {}; extra_raw = defaultdict(float); fixed_mw = 0; notes = []
        if k == 1:
            n = math.ceil(Dm/30-1e-9); gens['Biomass Burner'] = n
            if BIOFUEL: prod_dem['Solid Biofuel'] = Dm/30*4          # load-following fuel burn
            else: prod_dem['Biomass'] = Dm/30*10
            notes.append(f"{'Solid Biofuel' if BIOFUEL else 'Biomass'}; Wood is hand-gathered")
        else:
            if k == 2 or (k >= 3 and not fuel_ok): st['coal'] = max(st.get('coal', 0), math.ceil(Dm/75-1e-9))
            nc = st['coal']; gens['Coal Generator'] = nc
            coal_load = min(Dm, 75*nc); extra_raw['Coal'] += coal_load/75*15; extra_raw['Water'] += coal_load/75*45
            rem = Dm-coal_load
            if k >= 3 and fuel_ok:
                nf_need = math.ceil(rem/250-1e-9) if not (k == 5 and variant == 'B') else 0
                nf = max(st.get('fuel', 0), nf_need); gens['Fuel Generator'] = nf
                fuel_load = min(rem, 250*nf); rem -= fuel_load
                fuel = fuel_load/250*20
                res = min(fuel, hor_avail*4/6); crude = fuel-res
                if res > 1e-9:
                    nr = math.ceil(res/40-1e-9); fixed_mw += nr*30*(res/(nr*40))**M.EXP
                    notes.append(f"Residual Fuel {res:.1f}/min from HOR {res*6/4:.1f} ({nr} Refinery)")
                if crude > 1e-9: prod_dem['Fuel'] = crude
                st['_fuel_now'] = nf
            if k == 5 and variant == 'B' and rem > 1e-9:
                nn = math.ceil(rem/2500-1e-9); gens['Nuclear Plant'] = nn
                prod_dem['Uranium Fuel Rod'] = rem/2500*0.2; extra_raw['Water'] += rem/2500*240
                notes.append(f"Nuclear waste {rem/2500*10:.1f}/min accumulates (no disposal before Ficsonium)")
        # block production machines
        mach = {}; mmw = 0
        if prod_dem:
            prod, raw = M.solve(prod_dem)
            for it, v in prod.items():
                if v > 1e-9:
                    l, n_, cl, tot, w_ = M.size(it, v, k); mach[it] = (v, tot, cl, w_); mmw += w_
            for r_, v in raw.items(): extra_raw[r_] += v
        ext, emw = M.extraction({r_: v for r_, v in extra_raw.items() if v > 0}, k)
        new = mmw+emw+fixed_mw
        if abs(new-blk_mw) < 1e-6: break
        blk_mw = new
    W_blk = sum(v/M.mrate(it) for it, (v, *_r) in mach.items())   # machine-equivalents (per minute of phase)
    return dict(D_total=(d_fac+blk_mw)*PMULT, block_mw=blk_mw*PMULT, gens=gens, mach=mach, raw=dict(extra_raw), ext=ext, notes=notes, W_blk=W_blk,
                cap_mw=30*gens.get('Biomass Burner', 0)+75*gens.get('Coal Generator', 0)+250*gens.get('Fuel Generator', 0)+2500*gens.get('Nuclear Plant', 0))

def W_bill(bill):
    """Machine-minutes to make a bill from scratch at 100% clock (fungible machine-minutes, D17)."""
    if not bill: return 0.0
    prod, _ = M.solve(dict(bill))
    return sum(v/M.mrate(j) for j, v in prod.items() if v > 1e-12)

def run(name, sel, stretch_T=True):
    """stretch_T (adopted 2026-10-27 14:26): simulate each phase over its base time instead of the 1/min T_PA."""
    bills, mb = bills_for(sel)
    T_PA = {k: max(M.PA[k].values()) for k in P}
    STR = {k: (W_bill(M.PA[k])+W_bill(mb[k]))/W_bill(M.PA[k]) for k in P}
    h, STOCK = M.simulate(bills, {k: T_PA[k]*STR[k] for k in P} if stretch_T else None)
    rows = []; summ = {}; st = {}; stB = {}; rawcap = defaultdict(float)
    for k in P:
        tot = 0; mw = 0
        for j, c in h[k]['C'].items():
            if c > 1e-9:
                l, n, cl, t_, w_ = M.size(j, c, k); tot += t_; mw += w_
                rows.append((k, j, c, l, n, cl, t_, w_))
        for r_, v in h[k]['raw_peak'].items(): rawcap[r_] = max(rawcap[r_], v)
        ext, emw = M.extraction(dict(rawcap), k)
        hor = max(0, -h[k]['raw_avg'].get('Heavy Oil Residue', 0))
        stB = dict(st)
        pbA = power_block(k, mw+emw, hor, st, 'A')
        pbB = power_block(k, mw+emw, hor, stB, 'B') if (k == 5 and NUCLEAR) else None
        if k >= 3: st['fuel'] = st.get('_fuel_now', 0)
        W_fac = sum(v/M.mrate(j) for j, v in h[k]['made'].items())     # machine-minutes made in phase (sim; includes stockpiling ahead)
        # Phase stretch (adopted 2026-10-27 14:24): per-phase-bill W, independent of stockpile carry-over.
        # base time = PA-only phase time x W(PA+milestones)/W(PA), factory held at PA-only size (D19 "same factory").
        W_pa = W_bill(M.PA[k]); W_ms = W_bill(mb[k]); stretch = (W_pa+W_ms)/W_pa
        summ[k] = dict(T=h[k]['T'], machines=tot, fac_mw=mw, ext_mw=emw, ext=ext, hor=hor, pbA=pbA, pbB=pbB, h=h[k],
                       W_fac=W_fac, W_plant=pbA['W_blk']*h[k]['T'], W_pa=W_pa, W_ms=W_ms, stretch=stretch, base_T=T_PA[k]*stretch)
    return dict(bills=bills, mb=mb, h=h, rows=rows, summ=summ, STOCK=STOCK)

if __name__ == '__main__':
    res = {n: run(n, s) for n, s in SCEN.items()}
    import pickle; pickle.dump({n: {k: v for k, v in r.items() if k != 'h'} for n, r in res.items()}, open(HERE / 'run2.pkl', 'wb'))  # EDIT (d): was cwd
    for n, r in res.items():
        print(f"\n===== scenario {n}")
        for k in P:
            s = r['summ'][k]; a = s['pbA']
            print(f"P{k} T={s['T']:5d} mach={s['machines']:4d} facMW={s['fac_mw']:8.1f} extMW={s['ext_mw']:7.1f} | "
                  f"blockMW={a['block_mw']:7.1f} total={a['D_total']:8.1f} gens={a['gens']} cap={a['cap_mw']}")
            if s['pbB']: b = s['pbB']; print(f"   P5-B nuclear: blockMW={b['block_mw']:.1f} total={b['D_total']:.1f} gens={b['gens']} notes={b['notes']}")
            print("   notes:", a['notes'], "| HOR avail", round(s['hor'], 1))

def write_outputs(res):
    # milestone bills
    items = sorted({it for r in res.values() for k in P for it in r['mb'][k]})
    with open(HERE / 'milestone_bill_by_phase.csv', 'w', newline='') as f:  # EDIT (d)
        w = csv.writer(f, lineterminator="\n"); w.writerow(['item']+[f'{s}_P{k}' for s in res for k in P])  # EDIT (b)
        for it in items: w.writerow([it]+[round(res[s]['mb'][k].get(it, 0), 2) for s in res for k in P])
    # machines + MW, per scenario
    for s, r in res.items():
        by = defaultdict(dict)
        for (k, j, c, l, n, cl, t_, w_) in r['rows']: by[j][k] = (c, l, n, cl, t_, w_)
        with open(HERE / f'pa2_machines_{s}.csv', 'w', newline='') as f:  # EDIT (d)
            w = csv.writer(f, lineterminator="\n")  # EDIT (b)
            w.writerow(['item', 'producer', 'stockpiled']+[f'P{k}_{x}' for k in P for x in ('capacity', 'lines', 'machines_per_line', 'clock_pct', 'machines', 'MW')]+[f'P{k}_stock_end' for k in P])
            for j in M.ORDER:
                if j not in by: continue
                row = [j, M.producer(j), 'Y' if j in r['STOCK'] else '']
                for k in P:
                    v = by[j].get(k)
                    row += [f'{v[0]:.4g}', v[1], v[2], f'{v[3]:.4f}', v[4], f'{v[5]:.1f}'] if v else ['0', '', '', '', 0, '0']
                row += [round(r['h'][k]['S'][j], 1) for k in P]
                w.writerow(row)
    # power
    with open(HERE / 'power_by_phase.csv', 'w', newline='') as f:  # EDIT (d)
        w = csv.writer(f, lineterminator="\n")  # EDIT (b)
        w.writerow(['scenario', 'phase', 'variant', 'T_min', 'factory_machines', 'factory_machine_MW', 'factory_extraction_MW',
                    'power_block_MW', 'total_demand_MW', 'biomass_burners', 'coal_gens', 'fuel_gens', 'nuclear_plants', 'gen_capacity_MW',
                    'power_raw_per_min', 'power_block_machines', 'notes', 'W_sim_factory_machine_min', 'W_plant_machine_min',
                    'W_bill_PA', 'W_bill_milestones', 'phase_stretch', 'base_time_min', 'base_time_h'])
        for s, r in res.items():
            for k in P:
                sm = r['summ'][k]
                for var, pb in (('A', sm['pbA']), ('B', sm['pbB'])):
                    if pb is None: continue
                    g = pb['gens']
                    w.writerow([s, k, var if k == 5 else '', sm['T'], sm['machines'], round(sm['fac_mw'], 1), sm['ext_mw'], round(pb['block_mw'], 1),
                                round(pb['D_total'], 1), g.get('Biomass Burner', 0), g.get('Coal Generator', 0), g.get('Fuel Generator', 0),
                                g.get('Nuclear Plant', 0), pb['cap_mw'],
                                '; '.join(f'{k_} {v:.1f}' for k_, v in sorted(pb['raw'].items(), key=lambda x: -abs(x[1])) if abs(v) > 0.05),
                                '; '.join(f'{k_} {v[1]}' for k_, v in pb['mach'].items()), ' | '.join(pb['notes']),
                                round(sm['W_fac']), round(sm['W_plant']),
                                round(sm['W_pa']), round(sm['W_ms']), round(sm['stretch'], 3), round(sm['base_T']), round(sm['base_T']/60, 2)])
