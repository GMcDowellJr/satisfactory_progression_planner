"""Heading-lattice rail routing (5-degree headings), research prototype.

Hybrid-A* on the 8 m ramp-class grid from research/rail_slope_reach:
  state      continuous pose (east, north, heading k*5deg); closed set keyed by
             (KEY_M cell, heading); 8 m pruning measurably missed routes and
             faster lines on 2026-10-24, so the default is 4 m
  moves      straights of STRAIGHTS_M; arcs of each radius in a declared set,
             turning +/- the smallest multiple of 5deg whose arc is >= MIN_ARC_M;
             a run names a main-line minimum radius (a blueprint family of that
             radius and gentler); tighter radii only within APPROACH_M of
             either hub (throat)
  track      each move is one constant-grade deck between the ground at its two
             ends; rejected if |grade| > MAX_GRADE, if the ground rises more
             than CUT_TOL_M above the deck anywhere, if the deck stands more
             than MAX_PILLAR_M above the ground, or if it crosses a blocked
             cell (no data, deep or unknown water)
  cost       travel time, both directions averaged (uphill one way is
             downhill the other); a move whose deck is more than
             VIADUCT_M above ground costs VIADUCT_COST x its time

Real-world rail rules used for speed (declared assumptions, not game data):
  curves     v = sqrt(A_LAT * R), no superelevation in game, so all lateral
             acceleration is unbalanced; A_LAT = 1.0 m/s2 (upper end of
             real-world cant-deficiency practice)
  grades     uphill v = K_POWER / (grade + C_ROLL)  (power-limited climb,
             rolling resistance 0.2%); K_POWER calibrated so a train holds
             54 km/h on the steepest allowed grade (wiki: "at least 54 km/h"
             uphill if not overloaded); downhill capped only by V_MAX
  V_MAX      120 km/h (game top speed on flat track)

Not modelled: acceleration/braking between speed limits, vertical-curve
(grade-change) speed limits, transition spirals, station layout, water
crossings. Known defect (2026-10-24): decks are checked against 8 m cell
means; rechecked at 1 m, routes cut >2 m into the ground on 27-367 m each
and stand up to 75 m over narrow gullies. Check decks at 1 m before use.
"""
import heapq, json, math, sys, time
from pathlib import Path
import numpy as np
from numba import njit

HERE = Path(__file__).resolve().parent
RS = HERE.parent / 'rail_slope_reach' / 'out'
OUT = HERE / 'out'; OUT.mkdir(exist_ok=True)

POLICY = dict(
    heading_step_deg=5.0,
    max_grade=0.25,            # 2:8; 4:8 dropped (wiki: a 4 m ramp cannot carry rail)
    cut_tol_m=2.0,
    viaduct_m=4.0, viaduct_cost=1.5,
    max_pillar_m=16.0,         # deck height cap; the tallest span accepted in the 2026-10-24 session
    straights_m=[4.0, 8.0, 16.0, 48.0, 96.0],  # short ones let a pose adjust; real straights run any length
    min_arc_m=16.0,
    a_lat=1.0, c_roll=0.002, v_max_kmh=120.0, v_climb_floor_kmh=54.0,
    box_margin_m=1500.0, goal_tol_m=32.0,
    approach_m=300.0,          # hub throat: any radius allowed within this of either hub
    key_off_m=0.0,             # shift of the closed-set grid (sensitivity runs use key_m/2)
    key_m=4.0,                 # closed-set cell: one pose kept per key cell and heading
)
P = POLICY
V_MAX = P['v_max_kmh'] / 3.6
K_POWER = P['v_climb_floor_kmh'] / 3.6 * (P['max_grade'] + P['c_roll'])
R_FULL = V_MAX ** 2 / P['a_lat']        # radius at which curves cost no speed
# Radii named by the speed they allow under A_LAT (km/h -> m), plus 46 m (6x6 quarter circle, wiki).
SPEEDS = (120, 90, 72, 60, 51, 40)
TIGHT = sorted({round((v / 3.6) ** 2 / P['a_lat'], 1) for v in SPEEDS} | {46.0}, reverse=True)
# name -> (radii offered, main-line minimum radius). Main line: straights plus arcs of that radius
# or gentler from TIGHT (a small blueprint family); tighter radii only inside approach_m of a hub.
# 'any' (minimum 0) allows every radius everywhere: the lower bound. An exact single radius was
# tried first on 2026-10-24 and its route/no-route answer flipped with pruning detail (4 m vs 2 m
# cells, adding short straights), so it did not measure the terrain.
RADIUS_SETS = {f'R{round(r)}': (TIGHT, r) for r in TIGHT if r > 100}
RADIUS_SETS['any'] = (TIGHT, 0.0)

# Foundation-step profile (Greg, 2026-10-24): a curve blueprint turns 5deg from one 8 m foundation
# to the next, so chained it is one fixed radius, 4 / sin(2.5deg) = 91.7 m, everywhere including
# the hubs. Moves are whole foundations: 1, 2, 6 or 12 straight, or one foundation rotated 5deg.
R_BP5 = 4.0 / math.sin(math.radians(2.5))
PROFILES = {
    'bp5': dict(straights_m=[8.0, 16.0, 48.0, 96.0], min_arc_m=8.0, sets={'BP5': ([R_BP5], 0.0)}),
}
NH = int(round(360 / P['heading_step_deg']))


@njit(cache=True)
def bil(Z, r, c):
    n0, n1 = Z.shape
    if r < 0 or c < 0 or r > n0 - 1.001 or c > n1 - 1.001:
        return np.nan
    i = int(r); j = int(c); fr = r - i; fc = c - j
    return (Z[i, j] * (1 - fr) * (1 - fc) + Z[i + 1, j] * fr * (1 - fc)
            + Z[i, j + 1] * (1 - fr) * fc + Z[i + 1, j + 1] * fr * fc)


@njit(cache=True)
def move(x, y, th, R, d, L):
    """End pose of a move: straight (R==0) of length L, or arc radius R turning d rad."""
    if R == 0.0:
        return x + L * math.cos(th), y + L * math.sin(th), th
    s = 1.0 if d > 0 else -1.0
    t2 = th + d
    return x + s * R * (math.sin(t2) - math.sin(th)), y - s * R * (math.cos(t2) - math.cos(th)), t2


@njit(cache=True)
def check(Z, BL, E0, N0, B, x, y, th, R, d, L, maxg, cut, maxpil):
    """Returns (ok, grade signed, pillar max)."""
    m = int(math.ceil(L / 8.0))
    x1, y1, _ = move(x, y, th, R, d, L)
    z0 = bil(Z, (N0 - y) / B, (x - E0) / B); z1 = bil(Z, (N0 - y1) / B, (x1 - E0) / B)
    if not (z0 == z0 and z1 == z1):
        return False, 0.0, 0.0
    g = (z1 - z0) / L
    if abs(g) > maxg:
        return False, 0.0, 0.0
    pil = 0.0
    for i in range(m + 1):
        f = i / m
        if R == 0.0:
            xi, yi, _ = move(x, y, th, 0.0, 0.0, L * f)
        else:
            xi, yi, _ = move(x, y, th, R, d * f, 0.0)
        r = (N0 - yi) / B; c = (xi - E0) / B
        ri = int(round(r)); ci = int(round(c))
        if ri < 0 or ci < 0 or ri >= BL.shape[0] or ci >= BL.shape[1] or BL[ri, ci]:
            return False, 0.0, 0.0
        zg = bil(Z, r, c)
        if not (zg == zg):
            return False, 0.0, 0.0
        deck = z0 + (z1 - z0) * f
        if zg > deck + cut:
            return False, 0.0, 0.0
        if deck - zg > pil:
            pil = deck - zg
            if pil > maxpil:
                return False, 0.0, 0.0
    return True, g, pil


@njit(cache=True)
def tcost(L, g, R, vmax, alat, kpow, croll, pil, vm, vc):
    vcur = vmax
    if R > 0.0:
        vcur = min(vmax, math.sqrt(alat * R))
    vup = min(vcur, kpow / (abs(g) + croll))
    t = 0.5 * L * (1.0 / vup + 1.0 / vcur)
    if pil > vm:
        t *= vc
    return t


@njit(cache=True)
def search(Z, BL, E0, N0, B, KB, KE0, KN0, r0, c0, nr, nc, nh, sx, sy, gx, gy, goal_tol,
           radii, straights, min_arc, hstep, maxg, cut, vmax, alat, kpow, croll, vm, vc, rmain, appr, maxpil):
    NS = nr * nc * nh
    G = np.full(NS, np.inf, np.float32)
    PAR = np.full(NS, -1, np.int64)
    X = np.zeros(NS, np.float32); Y = np.zeros(NS, np.float32)
    MV = np.full(NS, -1, np.int16)
    DONE = np.zeros(NS, np.bool_)
    # move table: (R, d, L)
    nm = len(straights) + 2 * len(radii)
    MR = np.zeros(nm); MD = np.zeros(nm); ML = np.zeros(nm)
    for i in range(len(straights)):
        ML[i] = straights[i]
    for j in range(len(radii)):
        R = radii[j]; k = max(1, int(math.ceil(min_arc / (R * hstep))))
        for s in range(2):
            i = len(straights) + 2 * j + s
            MR[i] = R; MD[i] = k * hstep * (1.0 if s == 0 else -1.0); ML[i] = R * k * hstep
    heap = [(0.0, np.int64(0))]
    heap.pop()
    cs = int((KN0 - sy) / KB) - r0; cc = int((sx - KE0) / KB) - c0
    for h in range(nh):
        s = (cs * nc + cc) * nh + h
        G[s] = 0.0; X[s] = sx; Y[s] = sy
        heap.append((math.hypot(gx - sx, gy - sy) / vmax, np.int64(s)))
    heapq.heapify(heap)
    exp = 0
    while len(heap) > 0:
        f, s = heapq.heappop(heap)
        if DONE[s]:
            continue
        DONE[s] = True; exp += 1
        x = X[s]; y = Y[s]; h = s % nh; th = h * hstep
        if math.hypot(gx - x, gy - y) <= goal_tol:
            return s, exp, G, PAR, X, Y, MV, MR, MD, ML
        near = min(math.hypot(x - sx, y - sy), math.hypot(gx - x, gy - y)) <= appr
        for i in range(nm):
            if rmain > 0.0 and MR[i] > 0.0 and MR[i] < rmain and not near:
                continue
            ok, g, pil = check(Z, BL, E0, N0, B, x, y, th, MR[i], MD[i], ML[i], maxg, cut, maxpil)
            if not ok:
                continue
            x1, y1, t1 = move(x, y, th, MR[i], MD[i], ML[i])
            h1 = int(round(t1 / hstep)) % nh
            rr = int((KN0 - y1) / KB) - r0; c1 = int((x1 - KE0) / KB) - c0
            if rr < 0 or c1 < 0 or rr >= nr or c1 >= nc:
                continue
            s1 = (rr * nc + c1) * nh + h1
            if DONE[s1]:
                continue
            g1 = G[s] + tcost(ML[i], g, MR[i], vmax, alat, kpow, croll, pil, vm, vc)
            if g1 < G[s1]:
                G[s1] = g1; PAR[s1] = s; X[s1] = x1; Y[s1] = y1; MV[s1] = i
                heapq.heappush(heap, (g1 + math.hypot(gx - x1, gy - y1) / vmax, np.int64(s1)))
    return np.int64(-1), exp, G, PAR, X, Y, MV, MR, MD, ML


def route(Z, BL, E0, N0, B, a, b, radii, rmain):
    m = P['box_margin_m']; KB = P['key_m']; nk = int(Z.shape[0] * B / KB) + 1
    KE0 = E0 - KB - P['key_off_m']; KN0 = N0 + KB + P['key_off_m']   # key grid, one cell of slack
    xs = [a[0], b[0]]; ys = [a[1], b[1]]
    r0 = max(0, int((KN0 - (max(ys) + m)) / KB)); r1 = min(nk, int((KN0 - (min(ys) - m)) / KB) + 1)
    c0 = max(0, int((min(xs) - m - KE0) / KB)); c1 = min(nk, int((max(xs) + m - KE0) / KB) + 1)
    hstep = math.radians(P['heading_step_deg'])
    t0 = time.time()
    s, exp, G, PAR, X, Y, MV, MR, MD, ML = search(
        Z, BL, E0, N0, float(B), float(KB), KE0, KN0, r0, c0, r1 - r0, c1 - c0, NH, float(a[0]), float(a[1]), float(b[0]), float(b[1]),
        P['goal_tol_m'], np.array(radii), np.array(P['straights_m']), P['min_arc_m'], hstep, P['max_grade'],
        P['cut_tol_m'], V_MAX, P['a_lat'], K_POWER, P['c_roll'], P['viaduct_m'], P['viaduct_cost'],
        float(rmain), P['approach_m'], P['max_pillar_m'])
    secs = time.time() - t0
    if s < 0:
        return dict(found=False, expanded=int(exp), secs=round(secs, 1))
    chain = []
    while s >= 0:
        chain.append(int(s)); s = PAR[s]
    chain = chain[::-1]
    moves = []
    for p, q in zip(chain, chain[1:]):
        i = int(MV[q]); th = (p % NH) * hstep
        x, y = float(X[p]), float(Y[p])
        ok, g, pil = check(Z, BL, E0, N0, float(B), x, y, th, MR[i], MD[i], ML[i], P['max_grade'], P['cut_tol_m'], P['max_pillar_m'])
        pts = []
        k = max(2, int(math.ceil(ML[i] / 8)) + 1)
        for f in np.linspace(0, 1, k):
            xi, yi, _ = move(x, y, th, MR[i], MD[i] * f, ML[i] * f) if MR[i] > 0 else move(x, y, th, 0.0, 0.0, ML[i] * f)
            pts.append([round(xi, 1), round(yi, 1)])
        t = tcost(ML[i], g, MR[i], V_MAX, P['a_lat'], K_POWER, P['c_roll'], pil, P['viaduct_m'], P['viaduct_cost'])
        moves.append(dict(R=round(float(MR[i]), 1), turn_deg=round(math.degrees(MD[i])), L=round(float(ML[i]), 1),
                          grade=round(float(g), 4), pillar=round(float(pil), 1), t=round(float(t), 2), pts=pts))
    end = [float(X[chain[-1]]), float(Y[chain[-1]])]
    return dict(found=True, expanded=int(exp), secs=round(secs, 1), moves=moves,
                km=round(sum(m['L'] for m in moves) / 1000, 3), minutes=round(sum(m['t'] for m in moves) / 60, 2),
                end_gap_m=round(math.hypot(end[0] - b[0], end[1] - b[1]), 1))


def main(links=None, sets=None, out='lattice.json'):
    R = json.load(open(RS / 'slope_reach.json')); n = R['n']; B = R['grid_m']; E0, N0 = R['east0'], R['north0']
    Z = np.load(RS / 'Z.npy').astype(np.float64); BL = np.load(RS / 'blocked.npy')
    snaps = R['classes']['2:8']['snaps']
    pos = {k: (E0 + (v['node'] % n) * B, N0 - (v['node'] // n) * B) for k, v in snaps.items()}
    links = links or json.load(open(HERE / 'links.json'))
    res = dict(policy=P, r_full_m=round(R_FULL, 1), k_power=round(K_POWER, 3),
               radius_sets={k: dict(radii=[round(r, 1) for r in v[0]], mainline_min=round(v[1], 1)) for k, v in RADIUS_SETS.items()}, hubs=pos, links={})
    for a, b in links:
        for name in (sets or RADIUS_SETS):
            r = route(Z, BL, E0, N0, B, pos[a], pos[b], *RADIUS_SETS[name])
            res['links'].setdefault(f'{a}-{b}', {})[name] = r
            print(f'{a}-{b} {name}: ' + (f"{r['km']} km {r['minutes']} min" if r['found'] else 'NO ROUTE')
                  + f" ({r['expanded']} states, {r['secs']} s)", flush=True)
    json.dump(res, open(OUT / out, 'w', newline='\n'))


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('links', nargs='*', help='e.g. C1-C2 (default: links.json)')
    ap.add_argument('--sets', help='comma list of radius sets (default: all)')
    ap.add_argument('--key-m', type=float, help='closed-set cell size, m (sensitivity runs)')
    ap.add_argument('--margin-m', type=float, help='search box margin, m (sensitivity runs)')
    ap.add_argument('--key-off-m', type=float, help='shift of the closed-set grid, m')
    ap.add_argument('--profile', choices=sorted(PROFILES), help='move set and radius sets to use instead of the sweep')
    ap.add_argument('--out', default='lattice.json')
    a = ap.parse_args()
    if a.key_m:
        P['key_m'] = a.key_m
    if a.margin_m:
        P['box_margin_m'] = a.margin_m
    if a.profile:
        pr = PROFILES[a.profile]
        P['straights_m'] = pr['straights_m']; P['min_arc_m'] = pr['min_arc_m']
        RADIUS_SETS.clear(); RADIUS_SETS.update(pr['sets'])
        P['profile'] = a.profile
    if a.key_off_m:
        P['key_off_m'] = a.key_off_m
    main(links=[tuple(s.split('-')) for s in a.links] or None, sets=a.sets.split(',') if a.sets else None, out=a.out)
