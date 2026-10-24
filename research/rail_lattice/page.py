"""Build the 'Rail Curve Sweep' page: the whole hub network in one view (research prototype).

Inputs
  research/rail_lattice/out/sweep_off0.json, sweep_off2.json   lattice sweeps (lattice.py)
  research/rail_slope_reach/out/*                              ramp-class reach, 2:8 and 4:8
                                                               grid networks (network.py)
  research/phase4_rail_hubs/out/phase4-rail-hubs.html          the Phase 4 page (build.py, or
                                                               the published artifact saved
                                                               there): corridors, rail-tool
                                                               routes, site picks, neighborhoods
  tools/site_planner_web/precomputed/basemap_502094.*          basemap
Output: research/rail_lattice/out/rail-curve-sweep.html (gitignored).

The reach and slope rasters are redrawn here in one ink/brown ramp so they no longer share
colours with the speed scale (Greg, 2026-10-24: the reach colours were unclear). Reach shows
1:8 and 2:8 only; 4:8 is dropped (wiki: a 4 m ramp cannot carry rail).
"""
import base64, io, json, math, re
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / 'out'
PRE = REPO / 'tools/site_planner_web/precomputed'
RS = REPO / 'research/rail_slope_reach'
P4 = REPO / 'research/phase4_rail_hubs/out/phase4-rail-hubs.html'


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


def png(img):
    from PIL import Image
    b = io.BytesIO(); Image.fromarray(img, 'RGBA').save(b, 'PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()


def rasters():
    """Reach (first class that joins a cell to C1's component, 1:8 or 2:8), islands (land of
    0.25 km2 or more not joined at 2:8), and steepest-direction slope, as ink/brown PNGs."""
    R = json.loads((RS / 'out/slope_reach.json').read_text(encoding='utf-8')); n = R['n']; B = R['grid_m']
    reach = np.load(RS / 'out/reach.npy'); Z = np.load(RS / 'out/Z.npy'); BL = np.load(RS / 'out/blocked.npy')
    lab2 = np.load(RS / 'out/lab_2.npy').reshape(n, n)
    img = np.zeros((n, n, 4), np.uint8)
    img[reach == 1] = (28, 36, 33, 165); img[reach == 2] = (28, 36, 33, 80)
    core = R['classes']['2:8']['snaps']['C1']['comp']; sizes = np.bincount(lab2.ravel())
    img[(~BL) & (lab2 != core) & (sizes[lab2] * B * B >= 0.25e6)] = (91, 127, 166, 140)
    gy, gx = np.gradient(Z, B, B); g = np.hypot(gx, gy); land = ~BL & np.isfinite(g)
    gimg = np.zeros((n, n, 4), np.uint8)
    gimg[land & (g > .125) & (g <= .25)] = (138, 90, 43, 90); gimg[land & (g > .25)] = (110, 62, 24, 190)
    return dict(reach=png(img), slope=png(gimg), x=R['east0'] - B / 2, y=-R['north0'] - B / 2, size=n * B)


def earlier():
    """Layers from the Phase 4 page and the ramp-class networks, for comparison."""
    s = P4.read_text(encoding='utf-8')
    P = json.loads(re.search(r'const D=(\{.*?\});\n', s, re.S).group(1))
    net = json.loads((RS / 'out/network.json').read_text(encoding='utf-8'))
    return dict(
        corridors=[dict(a=r['a'], b=r['b'], km=r['route_km'], pts=r['pts']) for r in P['routes']],
        railtool=[dict(a=r['a'], b=r['b'], km=r['rail']['km'], valid=r['rail']['valid'], pts=r['rail']['pts'])
                  for r in P['routes'] if r.get('rail')],
        picks=[dict(role=m['role'], e=m['e'], n=m['n']) for h in P['hubs'] for m in h['members']],
        nbhd=[[o['e'], o['n']] for o in P['others']],
        grid={c: [dict(a=l['a'], b=l['b'], km=l['km'], pts=l['pts'],
                       spans=[dict(f=sp['from_core'], t=sp['to'], m=sp['span_m'], h=sp['max_pillar_m']) for sp in l['spans']])
                  for l in net[c]['links']] for c in ('2:8', '4:8')})


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
    # Foundation-step profile (lattice.py --profile bp5), when present: 5deg per 8 m foundation.
    pairs = [(L, L2)]
    if (OUT / 'bp5_off0.json').exists():
        pairs.append(tuple(json.loads((OUT / f).read_text(encoding='utf-8')) for f in ('bp5_off0.json', 'bp5_off2.json')))
    order = [k for k in sets if k != 'any'] + (['BP5'] if len(pairs) > 1 else []) + ['any']
    radius = {k: v['mainline_min'] for k, v in sets.items()}
    if len(pairs) > 1:
        radius['BP5'] = pairs[1][0]['radius_sets']['BP5']['radii'][0]
    links = []
    for key in L['links']:
        a, b = key.split('-')
        g = grid.get(frozenset((a, b)))
        row = dict(a=a, b=b, grid_km=g['km'] if g else None, grid_pts=g['pts'] if g else [], runs={})
        for A, A2 in pairs:
            for name, r0 in A['links'][key].items():
                r1 = A2['links'][key][name]
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
    D = dict(policy=P, k_power=k_pow, sets={k: radius[k] for k in order},
             radii=sets['any']['radii'], hubs=L['hubs'], names={h['key']: h['name'] for h in hubs},
             links=links, bm=dict(x=bm['x_m'], y=bm['y_m'], w=bm['width_m'], h=bm['height_m']),
             ras=rasters(), prev=earlier(),
             img='data:image/png;base64,' + base64.b64encode((PRE / bm['image']).read_bytes()).decode())
    html = (HERE / 'page_template.html').read_text(encoding='utf-8').replace('/*DATA*/null', json.dumps(D, separators=(',', ':')))
    (OUT / 'rail-curve-sweep.html').write_text(html, encoding='utf-8', newline='\n')
    print('wrote', OUT / 'rail-curve-sweep.html', len(html) // 1024, 'KB')


if __name__ == '__main__':
    main()
