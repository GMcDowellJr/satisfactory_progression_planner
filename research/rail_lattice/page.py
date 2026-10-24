"""Build the 'Rail Curve Sweep' page from lattice.json (research prototype).

Inputs: research/rail_lattice/out/lattice.json, research/rail_slope_reach/out/network.json
(2:8 grid paths, for comparison), research/rail_slope_reach/hubs.json, and the site
planner basemap. Output: research/rail_lattice/out/rail-curve-sweep.html (gitignored).
"""
import base64, json, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / 'out'
PRE = REPO / 'tools/site_planner_web/precomputed'
RS = REPO / 'research/rail_slope_reach'


def thin(pts, step=24.0):
    """Keep the ends and a point every `step` metres; enough to draw 5deg arcs smoothly."""
    keep = [pts[0]]; acc = 0.0
    for p, q in zip(pts, pts[1:]):
        acc += math.dist(p, q)
        if acc >= step:
            keep.append(q); acc = 0.0
    if keep[-1] != pts[-1]:
        keep.append(pts[-1])
    return [[round(x), round(y)] for x, y in keep]


def speed(m, P, v_max, k_pow):
    """Speed limit on a move, km/h: curve limit, and the climb limit in the uphill direction."""
    vc = v_max if m['R'] == 0 else min(v_max, math.sqrt(P['a_lat'] * m['R']))
    vu = min(vc, k_pow / (abs(m['grade']) + P['c_roll']))
    return round(vc * 3.6), round(vu * 3.6)


def main():
    # Two sweeps whose closed-set grids are offset by half a cell. Every route either finds is a
    # valid route, so the faster one is reported and the case is flagged when the two disagree.
    L, L2 = (json.loads((OUT / f).read_text(encoding='utf-8')) for f in ('sweep_off0.json', 'sweep_off2.json'))
    P = L['policy']; v_max = P['v_max_kmh'] / 3.6; k_pow = L['k_power']
    net = json.loads((RS / 'out/network.json').read_text(encoding='utf-8'))['2:8']['links']
    grid = {frozenset((l['a'], l['b'])): l for l in net}
    hubs = json.loads((RS / 'hubs.json').read_text(encoding='utf-8'))
    bm = json.loads((PRE / 'basemap_502094.json').read_text(encoding='utf-8'))
    sets = L['radius_sets']
    links = []
    for key, runs in L['links'].items():
        a, b = key.split('-')
        g = grid.get(frozenset((a, b)))
        row = dict(a=a, b=b, grid_km=g['km'] if g else None, grid_pts=g['pts'] if g else [], runs={})
        for name, r0 in runs.items():
            r1 = L2['links'][key][name]
            found = [x for x in (r0, r1) if x['found']]
            r = min(found, key=lambda x: x['minutes']) if found else r0
            ts = [x['minutes'] for x in found]
            unstable = len(found) == 1 or (len(found) == 2 and abs(ts[0] - ts[1]) > 0.05 * min(ts))
            if not r['found']:
                row['runs'][name] = dict(found=False); continue
            mv = []
            for m in r['moves']:
                vc, vu = speed(m, P, v_max, k_pow)
                mv.append(dict(R=m['R'], L=m['L'], g=m['grade'], pil=m['pillar'], vc=vc, vu=vu, pts=thin(m['pts'])))
            steep = sum(m['L'] for m in r['moves'] if abs(m['grade']) > 0.125)
            row['runs'][name] = dict(found=True, km=r['km'], minutes=r['minutes'], gap=r['end_gap_m'],
                                     steep_m=round(steep), viaduct_m=round(sum(m['L'] for m in r['moves'] if m['pillar'] > P['viaduct_m'])),
                                     moves=mv,
                                     unstable=unstable, alt_minutes=[x['minutes'] if x['found'] else None for x in (r0, r1)],
                                     curves={str(round(rad)): sum(1 for m in r['moves'] if m['R'] == rad)
                                             for rad in sorted({m['R'] for m in r['moves'] if m['R'] > 0}, reverse=True)})
        links.append(row)
    D = dict(policy=P, k_power=k_pow, sets={k: v['mainline_min'] for k, v in sets.items()},
             radii=sets['any']['radii'], hubs=L['hubs'], names={h['key']: h['name'] for h in hubs},
             links=links, bm=dict(x=bm['x_m'], y=bm['y_m'], w=bm['width_m'], h=bm['height_m']),
             img='data:image/png;base64,' + base64.b64encode((PRE / bm['image']).read_bytes()).decode())
    html = (HERE / 'page_template.html').read_text(encoding='utf-8').replace('/*DATA*/null', json.dumps(D, separators=(',', ':')))
    (OUT / 'rail-curve-sweep.html').write_text(html, encoding='utf-8', newline='\n')
    print('wrote', OUT / 'rail-curve-sweep.html', len(html) // 1024, 'KB')


if __name__ == '__main__':
    main()
