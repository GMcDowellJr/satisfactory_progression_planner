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
             ends (1 m heightfield, nearest vertex on the centreline);
             rejected if |grade| > MAX_GRADE, if the ground anywhere under the
             deck's footprint (a strip 2 x FOOT_HALF_M wide: one foundation)
             rises more than CUT_TOL_M above the deck, if the deck stands more
             than MAX_PILLAR_M above the lowest ground under the footprint, or
             if it crosses a blocked 8 m cell (no data, deep or unknown water).
             The footprint is checked every 1 m against disc max/min rasters
             (radius FOOT_HALF_M): a strip is the union of discs centred on
             its centreline.
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
crossings. Fixed defect (2026-10-24, branch claude/rail-deck): decks were
checked against bilinear 8 m cell means, so routes cut >2 m into the ground on
27-367 m each and stood up to 75 m over narrow gullies; the check now reads
the 1 m heightfield through footprint rasters (above). The 8 m blocked-cell
lookup also rounded to the nearest cell index where the cell containing the
point is the floor (a half-cell, 4 m, offset); fixed in the same change.
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
    foot_half_m=4.0,           # deck footprint half-width: one 8 m foundation
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
HM = Path('planning_data/world/spatial/heightmap_build_502094')   # repo-root relative, as slope_reach.py
NODATA = -32768


def terrain_1m():
    """(3, H, W) int16 decimetres: [0] 1 m heightfield, [1] max and [2] min over a disc of radius
    FOOT_HALF_M around each vertex (no-data ignored; NODATA where the disc holds none). Cached in
    out/ keyed by the radius; the heightfield is local data (gitignored), never committed."""
    # Samples read the nearest vertex, up to sqrt(0.5) m from the true point, so the disc is widened by
    # that much: it then always covers the true footprint (conservative by at most 0.71 m).
    rad = P['foot_half_m'] + (math.sqrt(0.5) if P['foot_half_m'] > 0 else 0.0)
    cache = OUT / f'terrain_1m_r{rad:.3f}.npy'
    if cache.exists():
        return np.load(cache)
    from scipy import ndimage
    sys.path.insert(0, 'tools/corridor_tool/src')
    from corridor_tool.field import decode_i16
    meta = json.load(open(HM / 'meta.json')); H, W = meta['grid']['height'], meta['grid']['width']
    h = decode_i16(HM / 'height.i16.z', H, W)
    k = int(math.floor(rad)); yy, xx = np.mgrid[-k:k + 1, -k:k + 1]; disc = (xx * xx + yy * yy) <= rad * rad
    hi = ndimage.maximum_filter(h, footprint=disc, mode='constant', cval=NODATA)
    lo = ndimage.minimum_filter(np.where(h == NODATA, np.int16(32767), h), footprint=disc, mode='constant', cval=32767)
    lo[lo == 32767] = NODATA
    T = np.stack([h, hi, lo]).astype(np.int16)
    np.save(cache, T)
    return T


@njit(cache=True)
def move(x, y, th, R, d, L):
    """End pose of a move: straight (R==0) of length L, or arc radius R turning d rad."""
    if R == 0.0:
        return x + L * math.cos(th), y + L * math.sin(th), th
    s = 1.0 if d > 0 else -1.0
    t2 = th + d
    return x + s * R * (math.sin(t2) - math.sin(th)), y - s * R * (math.cos(t2) - math.cos(th)), t2


@njit(cache=True)
def z1m(T, k, E0, N0, x, y):
    """Layer k of terrain_1m at the nearest vertex (meta.json: vertex-aligned), metres; nan if none."""
    r = int(round(N0 - y)); c = int(round(x - E0))
    if r < 0 or c < 0 or r >= T.shape[1] or c >= T.shape[2]:
        return np.nan
    v = T[k, r, c]
    if v == NODATA:
        return np.nan
    return v / 10.0


@njit(cache=True)
def check(T, BL, E0, N0, B, x, y, th, R, d, L, maxg, cut, maxpil):
    """Returns (ok, grade signed, pillar max). T from terrain_1m; BL the 8 m blocked raster."""
    m = int(math.ceil(L))
    x1, y1, _ = move(x, y, th, R, d, L)
    z0 = z1m(T, 0, E0, N0, x, y); z1 = z1m(T, 0, E0, N0, x1, y1)
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
        ri = int(math.floor((N0 - yi) / B)); ci = int(math.floor((xi - E0) / B))
        if ri < 0 or ci < 0 or ri >= BL.shape[0] or ci >= BL.shape[1] or BL[ri, ci]:
            return False, 0.0, 0.0
        hi = z1m(T, 1, E0, N0, xi, yi); lo = z1m(T, 2, E0, N0, xi, yi)
        if not (hi == hi and lo == lo):
            return False, 0.0, 0.0
        deck = z0 + (z1 - z0) * f
        if hi > deck + cut:
            return False, 0.0, 0.0
        if deck - lo > pil:
            pil = deck - lo
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
    m = P['box_margin_m']; KB = P['key_m']; nk = int(BL.shape[0] * B / KB) + 1
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
            pts.append([round(xi, 3), round(yi, 3)])   # mm: a 1 m recheck must read the vertices the search read
        t = tcost(ML[i], g, MR[i], V_MAX, P['a_lat'], K_POWER, P['c_roll'], pil, P['viaduct_m'], P['viaduct_cost'])
        moves.append(dict(R=round(float(MR[i]), 1), turn_deg=round(math.degrees(MD[i])), L=round(float(ML[i]), 1),
                          grade=round(float(g), 4), pillar=round(float(pil), 1), t=round(float(t), 2), pts=pts))
    end = [float(X[chain[-1]]), float(Y[chain[-1]])]
    return dict(found=True, expanded=int(exp), secs=round(secs, 1), moves=moves,
                km=round(sum(m['L'] for m in moves) / 1000, 3), minutes=round(sum(m['t'] for m in moves) / 60, 2),
                end_gap_m=round(math.hypot(end[0] - b[0], end[1] - b[1]), 1))


# ------------------------------------------------------------------------------------------------
# Deck-height search with a curve kit and hub zones (Greg, 2026-10-24, 18:30-19:25):
#   curves flat, only straights climb (curve BPs can rise in game; flat is the choice for now);
#   grade 25% (manual placement is imprecise); deck height carried in the state (option A: a curve
#   holds it, a straight climbs or falls within the grade); curve angles a kit, any angle anywhere;
#   no clipping: no ground above the deck under the footprint; height above ground is priced, not
#   capped: each move costs time x (1 + mean height / H0), H0 swept as a frontier; a hard lid
#   (default 32 m, swept coarse then fine) on the deck's height over the lowest ground beneath it;
#   a hub is its neighbourhood: a disc of HUB_ZONE_M (neighborhoods_v020 policy radius_m, 350 m)
#   around the hub; routes may start or end anywhere in it, arriving at most ARRIVE_MAX_M up.
#   The output is a guide to direction and shape, adjusted in game, not a placement plan.
# Lossy pruning: one state per (key cell, heading); of two arrivals at different deck heights the
# first closed wins (as x, y already are). Height bins in the key need the hashed closed set.
DECK = dict(
    kit_deg=[5.0],
    straights_m=[8.0, 16.0, 48.0, 96.0],   # whole foundations: 1, 2, 6, 12
    clearance_m=0.0,           # ground may not rise above deck - clearance under the footprint
    lid_m=32.0,                # hard: deck height over the lowest ground under the footprint
    h0_m=8.0,                  # height at which a stretch counts double its time
    hub_zone_m=350.0,          # neighbourhood radius (neighborhoods_v020.json policy radius_m)
    arrive_max_m=4.0,          # deck height over the centreline ground where a route meets a hub zone
    split_min_m=0.5,           # straight end heights closer than this are one option
    hashed=True,               # closed set in a hash table (search_deck_h); --dense for search_deck
)
MAXS = 128                     # samples per move at 1 m: longest straight is 96 m


def kit_arcs(kit_deg):
    """One foundation rotated N deg: radius 4 / sin(N/2) (8 m foundation, rail attached), arc R*N."""
    R = np.array([4.0 / math.sin(math.radians(n) / 2) for n in kit_deg])
    D = np.array([math.radians(n) for n in kit_deg])
    return R, D, R * D


@njit(cache=True)
def sample_move(T, BL, E0, N0, B, x, y, th, R, d, L, HI, LO, G0):
    """Fill HI/LO (footprint max/min) and G0 (centreline ground) every 1 m along a move; returns
    the sample count - 1, or -1 if any sample is blocked, outside the map or has no data."""
    m = int(math.ceil(L))
    for i in range(m + 1):
        f = i / m
        if R == 0.0:
            xi, yi, _ = move(x, y, th, 0.0, 0.0, L * f)
        else:
            xi, yi, _ = move(x, y, th, R, d * f, 0.0)
        ri = int(math.floor((N0 - yi) / B)); ci = int(math.floor((xi - E0) / B))
        if ri < 0 or ci < 0 or ri >= BL.shape[0] or ci >= BL.shape[1] or BL[ri, ci]:
            return -1
        hi = z1m(T, 1, E0, N0, xi, yi); lo = z1m(T, 2, E0, N0, xi, yi); g0 = z1m(T, 0, E0, N0, xi, yi)
        if not (hi == hi and lo == lo and g0 == g0):
            return -1
        HI[i] = hi; LO[i] = lo; G0[i] = g0
    return m


@njit(cache=True)
def deck_eval(m, z0, z1, HI, LO, G0, clr, lid):
    """(ok, mean height over centreline ground) for a straight deck z0 -> z1 over the samples."""
    s = 0.0
    for i in range(m + 1):
        deck = z0 + (z1 - z0) * i / m
        if HI[i] > deck - clr + 1e-6 or deck - LO[i] > lid:
            return False, 0.0
        s += deck - G0[i]
    return True, s / (m + 1)


@njit(cache=True)
def search_deck(T, BL, E0, N0, B, KB, KE0, KN0, r0, c0, nr, nc, nh, SX, SY, SZ, gx, gy, gR,
                straights, AR, AD, AL, hstep, maxg, clr, lid, arrive, split, h0, vmax, alat, kpow, croll):
    NS = nr * nc * nh
    G = np.full(NS, np.inf, np.float32)
    PAR = np.full(NS, -1, np.int64)
    X = np.zeros(NS, np.float32); Y = np.zeros(NS, np.float32); ZD = np.zeros(NS, np.float32)
    MV = np.full(NS, -1, np.int16)
    DONE = np.zeros(NS, np.bool_)
    HI = np.zeros(MAXS); LO = np.zeros(MAXS); G0 = np.zeros(MAXS); CZ = np.zeros(3)
    ns = len(straights)
    heap = [(0.0, np.int64(0))]
    heap.pop()
    for k in range(len(SX)):
        cs = int((KN0 - SY[k]) / KB) - r0; cc = int((SX[k] - KE0) / KB) - c0
        if cs < 0 or cc < 0 or cs >= nr or cc >= nc:
            continue
        hzn = max(0.0, math.hypot(gx - SX[k], gy - SY[k]) - gR) / vmax
        for h in range(nh):
            s = (cs * nc + cc) * nh + h
            if G[s] == 0.0:
                continue
            G[s] = 0.0; X[s] = SX[k]; Y[s] = SY[k]; ZD[s] = SZ[k]
            heap.append((hzn, np.int64(s)))
    heapq.heapify(heap)
    exp = 0
    while len(heap) > 0:
        f, s = heapq.heappop(heap)
        if DONE[s]:
            continue
        DONE[s] = True; exp += 1
        x = X[s]; y = Y[s]; z = ZD[s]; th = (s % nh) * hstep
        if math.hypot(gx - x, gy - y) <= gR:
            g0 = z1m(T, 0, E0, N0, x, y)
            if g0 == g0 and z - g0 <= arrive:
                return s, exp, G, PAR, X, Y, ZD, MV
        for i in range(ns + 2 * len(AR)):
            if i < ns:
                R = 0.0; d = 0.0; L = straights[i]
            else:
                j = (i - ns) // 2; R = AR[j]; d = AD[j] * (1.0 if (i - ns) % 2 == 0 else -1.0); L = AL[j]
            m = sample_move(T, BL, E0, N0, B, x, y, th, R, d, L, HI, LO, G0)
            if m < 0:
                continue
            # end-height options: straights lowest unclipped / level / full climb; curves level
            c = CZ; nc_ = 0
            if R > 0.0:
                c[0] = z; nc_ = 1
            else:
                lo_b = z - maxg * L; hi_b = z + maxg * L; req = lo_b
                for q in range(1, m + 1):
                    fq = q / m
                    need = z + (HI[q] + clr - z) / fq
                    if need > req:
                        req = need
                if req > hi_b + 1e-9:
                    continue
                c[0] = req; nc_ = 1
                if z - req > split:
                    c[nc_] = z; nc_ += 1
                if hi_b - max(req, z) > split:
                    c[nc_] = hi_b; nc_ += 1
            x1, y1, t1 = move(x, y, th, R, d, L)
            h1 = int(round(t1 / hstep)) % nh
            rr = int((KN0 - y1) / KB) - r0; c1 = int((x1 - KE0) / KB) - c0
            if rr < 0 or c1 < 0 or rr >= nr or c1 >= nc:
                continue
            s1 = (rr * nc + c1) * nh + h1
            if DONE[s1]:
                continue
            for e in range(nc_):
                z1 = c[e]
                ok, hm = deck_eval(m, z, z1, HI, LO, G0, clr, lid)
                if not ok:
                    continue
                g = (z1 - z) / L
                t = tcost(L, g, R, vmax, alat, kpow, croll, 0.0, 1e9, 1.0) * (1.0 + max(hm, 0.0) / h0)
                g1 = G[s] + t
                if g1 < G[s1]:
                    G[s1] = g1; PAR[s1] = s; X[s1] = x1; Y[s1] = y1; ZD[s1] = z1; MV[s1] = i * 3 + e
                    heapq.heappush(heap, (g1 + max(0.0, math.hypot(gx - x1, gy - y1) - gR) / vmax, np.int64(s1)))
    return np.int64(-1), exp, G, PAR, X, Y, ZD, MV


@njit(cache=True)
def hslot(KEYS, mask, key):
    """Open addressing, linear probing: the slot holding key, or the empty slot where it goes."""
    h = ((key ^ (key >> 29)) * np.int64(-7046029254386353131)) & mask
    while KEYS[h] != -1 and KEYS[h] != key:
        h = (h + 1) & mask
    return h


@njit(cache=True)
def hgrow(KEYS, G, PAR, X, Y, ZD, MV, DONE):
    cap = 2 * len(KEYS); mask = cap - 1
    K2 = np.full(cap, -1, np.int64); G2 = np.full(cap, np.inf, np.float32); P2 = np.full(cap, -1, np.int64)
    X2 = np.zeros(cap, np.float32); Y2 = np.zeros(cap, np.float32); Z2 = np.zeros(cap, np.float32)
    M2 = np.full(cap, -1, np.int16); D2 = np.zeros(cap, np.bool_)
    for i in range(len(KEYS)):
        if KEYS[i] != -1:
            h = hslot(K2, mask, KEYS[i])
            K2[h] = KEYS[i]; G2[h] = G[i]; P2[h] = PAR[i]; X2[h] = X[i]; Y2[h] = Y[i]; Z2[h] = ZD[i]
            M2[h] = MV[i]; D2[h] = DONE[i]
    return K2, G2, P2, X2, Y2, Z2, M2, D2


@njit(cache=True)
def search_deck_h(T, BL, E0, N0, B, KB, KE0, KN0, r0, c0, nr, nc, nh, SX, SY, SZ, gx, gy, gR,
                  straights, AR, AD, AL, hstep, maxg, clr, lid, arrive, split, h0, vmax, alat, kpow, croll):
    """search_deck with the closed set in a hash table holding only touched states (the dense arrays
    cost 27 B per box state; at 5 deg ~13% of the box is touched, at 1 deg the dense box is ~10 GB).
    Keys are search_deck's state indices and the heap orders on them the same way, so results
    must be identical to search_deck: that is the regression gate. PAR holds parent keys."""
    cap = 1 << 20; mask = cap - 1; used = 0
    KEYS = np.full(cap, -1, np.int64); G = np.full(cap, np.inf, np.float32); PAR = np.full(cap, -1, np.int64)
    X = np.zeros(cap, np.float32); Y = np.zeros(cap, np.float32); ZD = np.zeros(cap, np.float32)
    MV = np.full(cap, -1, np.int16); DONE = np.zeros(cap, np.bool_)
    HI = np.zeros(MAXS); LO = np.zeros(MAXS); G0 = np.zeros(MAXS); CZ = np.zeros(3)
    ns = len(straights)
    heap = [(0.0, np.int64(0))]
    heap.pop()
    for k in range(len(SX)):
        cs = int((KN0 - SY[k]) / KB) - r0; cc = int((SX[k] - KE0) / KB) - c0
        if cs < 0 or cc < 0 or cs >= nr or cc >= nc:
            continue
        hzn = max(0.0, math.hypot(gx - SX[k], gy - SY[k]) - gR) / vmax
        for h in range(nh):
            s = np.int64((cs * nc + cc) * nh + h)
            if 2 * (used + 1) > cap:
                KEYS, G, PAR, X, Y, ZD, MV, DONE = hgrow(KEYS, G, PAR, X, Y, ZD, MV, DONE); cap *= 2; mask = cap - 1
            q = hslot(KEYS, mask, s)
            if KEYS[q] == s and G[q] == 0.0:
                continue
            if KEYS[q] == -1:
                used += 1
            KEYS[q] = s; G[q] = 0.0; X[q] = SX[k]; Y[q] = SY[k]; ZD[q] = SZ[k]
            heap.append((hzn, s))
    heapq.heapify(heap)
    exp = 0
    while len(heap) > 0:
        f, s = heapq.heappop(heap)
        qs = hslot(KEYS, mask, s)
        if DONE[qs]:
            continue
        DONE[qs] = True; exp += 1
        x = X[qs]; y = Y[qs]; z = ZD[qs]; gs = G[qs]; th = (s % nh) * hstep
        if math.hypot(gx - x, gy - y) <= gR:
            g0 = z1m(T, 0, E0, N0, x, y)
            if g0 == g0 and z - g0 <= arrive:
                return s, exp, KEYS, mask, G, PAR, X, Y, ZD, MV
        for i in range(ns + 2 * len(AR)):
            if i < ns:
                R = 0.0; d = 0.0; L = straights[i]
            else:
                j = (i - ns) // 2; R = AR[j]; d = AD[j] * (1.0 if (i - ns) % 2 == 0 else -1.0); L = AL[j]
            m = sample_move(T, BL, E0, N0, B, x, y, th, R, d, L, HI, LO, G0)
            if m < 0:
                continue
            c = CZ; nc_ = 0
            if R > 0.0:
                c[0] = z; nc_ = 1
            else:
                lo_b = z - maxg * L; hi_b = z + maxg * L; req = lo_b
                for q in range(1, m + 1):
                    fq = q / m
                    need = z + (HI[q] + clr - z) / fq
                    if need > req:
                        req = need
                if req > hi_b + 1e-9:
                    continue
                c[0] = req; nc_ = 1
                if z - req > split:
                    c[nc_] = z; nc_ += 1
                if hi_b - max(req, z) > split:
                    c[nc_] = hi_b; nc_ += 1
            x1, y1, t1 = move(x, y, th, R, d, L)
            h1 = int(round(t1 / hstep)) % nh
            rr = int((KN0 - y1) / KB) - r0; c1 = int((x1 - KE0) / KB) - c0
            if rr < 0 or c1 < 0 or rr >= nr or c1 >= nc:
                continue
            s1 = np.int64((rr * nc + c1) * nh + h1)
            q1 = hslot(KEYS, mask, s1)
            if KEYS[q1] == s1 and DONE[q1]:
                continue
            for e in range(nc_):
                z1 = c[e]
                ok, hm = deck_eval(m, z, z1, HI, LO, G0, clr, lid)
                if not ok:
                    continue
                g = (z1 - z) / L
                t = tcost(L, g, R, vmax, alat, kpow, croll, 0.0, 1e9, 1.0) * (1.0 + max(hm, 0.0) / h0)
                g1 = gs + t
                if KEYS[q1] != s1 or g1 < G[q1]:
                    if KEYS[q1] == -1:
                        if 2 * (used + 1) > cap:
                            KEYS, G, PAR, X, Y, ZD, MV, DONE = hgrow(KEYS, G, PAR, X, Y, ZD, MV, DONE)
                            cap *= 2; mask = cap - 1; q1 = hslot(KEYS, mask, s1)
                        used += 1
                    KEYS[q1] = s1; G[q1] = g1; PAR[q1] = s; X[q1] = x1; Y[q1] = y1; ZD[q1] = z1; MV[q1] = i * 3 + e
                    heapq.heappush(heap, (g1 + max(0.0, math.hypot(gx - x1, gy - y1) - gR) / vmax, s1))
    return np.int64(-1), exp, KEYS, mask, G, PAR, X, Y, ZD, MV


def zone_seeds(T, BL, E0, N0, B, KB, hub, R):
    """One seed per key cell centre within R of the hub: deck at the highest ground under the
    footprint there (no clipping), skipping blocked or no-data cells."""
    xs, ys, zs = [], [], []
    n = int(R // KB)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x = hub[0] + j * KB; y = hub[1] + i * KB
            if math.hypot(x - hub[0], y - hub[1]) > R:
                continue
            ri = int((N0 - y) // B); ci = int((x - E0) // B)
            if ri < 0 or ci < 0 or ri >= BL.shape[0] or ci >= BL.shape[1] or BL[ri, ci]:
                continue
            hi = z1m(T, 1, E0, N0, x, y)
            if hi == hi:
                xs.append(x); ys.append(y); zs.append(hi + DECK['clearance_m'])
    return np.array(xs), np.array(ys), np.array(zs)


def route_deck(T, BL, E0, N0, B, a, b):
    D = DECK
    kit = D['kit_deg']; step = math.gcd(*[int(round(k)) for k in kit]) if all(float(k).is_integer() for k in kit) else None
    if step is None:
        raise ValueError(f'kit angles must be whole degrees for a common heading step: {kit}')
    nh = 360 // step; hstep = math.radians(step)
    AR, AD, AL = kit_arcs(kit)
    m = P['box_margin_m']; KB = P['key_m']; nk = int(BL.shape[0] * B / KB) + 1
    KE0 = E0 - KB - P['key_off_m']; KN0 = N0 + KB + P['key_off_m']
    xs = [a[0], b[0]]; ys = [a[1], b[1]]
    r0 = max(0, int((KN0 - (max(ys) + m)) / KB)); r1 = min(nk, int((KN0 - (min(ys) - m)) / KB) + 1)
    c0 = max(0, int((min(xs) - m - KE0) / KB)); c1 = min(nk, int((max(xs) + m - KE0) / KB) + 1)
    SX, SY, SZ = zone_seeds(T, BL, E0, N0, B, KB, a, D['hub_zone_m'])
    t0 = time.time()
    args = (T, BL, E0, N0, float(B), float(KB), KE0, KN0, r0, c0, r1 - r0, c1 - c0, nh, SX, SY, SZ,
            float(b[0]), float(b[1]), D['hub_zone_m'], np.array(D['straights_m']), AR, AD, AL, hstep,
            P['max_grade'], D['clearance_m'], D['lid_m'], D['arrive_max_m'], D['split_min_m'], D['h0_m'],
            V_MAX, P['a_lat'], K_POWER, P['c_roll'])
    if D['hashed']:
        s, exp, KEYS, mask, G, PAR, X, Y, ZD, MV = search_deck_h(*args)
        stored = int((KEYS != -1).sum())
        slot = lambda k: hslot(KEYS, mask, np.int64(k))
    else:
        s, exp, G, PAR, X, Y, ZD, MV = search_deck(*args)
        stored = int(np.isfinite(G).sum())
        slot = lambda k: k
    secs = time.time() - t0
    if s < 0:
        return dict(found=False, expanded=int(exp), stored=stored, seeds=len(SX), secs=round(secs, 1))
    chain = []
    while s >= 0:
        chain.append(int(s)); s = PAR[slot(s)]
    chain = chain[::-1]
    sl = {k: slot(k) for k in chain}
    ns = len(D['straights_m'])
    HI = np.zeros(MAXS); LO = np.zeros(MAXS); G0 = np.zeros(MAXS)
    moves = []
    for p, q in zip(chain, chain[1:]):
        code = int(MV[sl[q]]); i = code // 3
        if i < ns:
            R = 0.0; d = 0.0; L = D['straights_m'][i]; ang = 0
        else:
            j = (i - ns) // 2; sg = 1.0 if (i - ns) % 2 == 0 else -1.0
            R = float(AR[j]); d = float(AD[j]) * sg; L = float(AL[j]); ang = round(sg * kit[j])
        th = (p % nh) * hstep; x, y = float(X[sl[p]]), float(Y[sl[p]]); z0, z1 = float(ZD[sl[p]]), float(ZD[sl[q]])
        mm = sample_move(T, BL, E0, N0, float(B), x, y, th, R, d, L, HI, LO, G0)
        ok, hm = deck_eval(mm, z0, z1, HI, LO, G0, D['clearance_m'], D['lid_m'])
        g = (z1 - z0) / L
        t = tcost(L, g, R, V_MAX, P['a_lat'], K_POWER, P['c_roll'], 0.0, 1e9, 1.0)
        hmax = max(z0 + (z1 - z0) * k / mm - LO[k] for k in range(mm + 1))
        pts = []
        for f in np.linspace(0, 1, max(2, int(math.ceil(L / 8)) + 1)):
            xi, yi, _ = move(x, y, th, R, d * f, 0.0) if R > 0 else move(x, y, th, 0.0, 0.0, L * f)
            pts.append([round(xi, 3), round(yi, 3)])
        moves.append(dict(R=round(R, 1), turn_deg=ang, L=round(L, 3), z0=round(z0, 3), z1=round(z1, 3),
                          grade=round(g, 4), h_mean=round(hm, 2), h_max=round(hmax, 2), t=round(t, 2),
                          t_priced=round(t * (1 + max(hm, 0) / D['h0_m']), 2), ok=bool(ok), pts=pts))
    km = sum(m_['L'] for m_ in moves) / 1000
    return dict(found=True, expanded=int(exp), stored=stored, seeds=len(SX), secs=round(secs, 1), moves=moves, km=round(km, 3),
                minutes=round(sum(m_['t'] for m_ in moves) / 60, 2),
                h_mean=round(sum(m_['h_mean'] * m_['L'] for m_ in moves) / max(km * 1000, 1e-9), 2),
                h_max=round(max(m_['h_max'] for m_ in moves), 2),
                km_over_8m=round(sum(m_['L'] for m_ in moves if m_['h_mean'] > 8) / 1000, 3),
                turns={str(k): sum(1 for m_ in moves if abs(m_['turn_deg']) == round(k)) for k in kit})


def main_deck(links=None, out='deck.json'):
    R = json.load(open(RS / 'slope_reach.json')); B = R['grid_m']; E0, N0 = R['east0'], R['north0']
    T = terrain_1m(); BL = np.load(RS / 'blocked.npy')
    hubs = {h['key']: (h['east_m'], h['north_m']) for h in json.load(open(RS.parent / 'hubs.json'))}
    links = links or json.load(open(HERE / 'links.json'))
    res = dict(policy=P, deck=DECK, k_power=round(K_POWER, 3), hubs=hubs, links={})
    for a, b in links:
        r = route_deck(T, BL, E0, N0, B, hubs[a], hubs[b])
        res['links'][f'{a}-{b}'] = r
        print(f'{a}-{b}: ' + (f"{r['km']} km {r['minutes']} min, mean {r['h_mean']} m up, max {r['h_max']} m, "
                              f"turns {r['turns']}" if r['found'] else 'NO ROUTE')
              + f" ({r['expanded']} states, {r['seeds']} seeds, {r['secs']} s)", flush=True)
    json.dump(res, open(OUT / out, 'w', newline='\n'))


def main(links=None, sets=None, out='lattice.json'):
    R = json.load(open(RS / 'slope_reach.json')); n = R['n']; B = R['grid_m']; E0, N0 = R['east0'], R['north0']
    Z = terrain_1m(); BL = np.load(RS / 'blocked.npy')
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
    ap.add_argument('--max-grade', type=float, help='override max grade (sensitivity runs)')
    ap.add_argument('--max-pillar-m', type=float, help='override deck height cap (sensitivity runs)')
    ap.add_argument('--foot-half-m', type=float, help='override deck footprint half-width, m (sensitivity runs; 0 = centreline only)')
    ap.add_argument('--cut-tol-m', type=float, help='override cut tolerance, m (sensitivity runs)')
    ap.add_argument('--deck', action='store_true', help='deck-height search with a curve kit and hub zones (DECK)')
    ap.add_argument('--kit', help='deck: curve angles per foundation, deg, comma list (default 5)')
    ap.add_argument('--h0-m', type=float, help='deck: height at which a stretch counts double its time, m')
    ap.add_argument('--lid-m', type=float, help='deck: hard lid on deck height over the lowest ground, m')
    ap.add_argument('--hub-zone-m', type=float, help='deck: hub zone radius, m')
    ap.add_argument('--dense', action='store_true', help='deck: dense closed-set arrays (regression reference)')
    ap.add_argument('--out', default='lattice.json')
    a = ap.parse_args()
    if a.deck:
        if a.kit:
            DECK['kit_deg'] = [float(v) for v in a.kit.split(',')]
        if a.h0_m:
            DECK['h0_m'] = a.h0_m
        if a.lid_m:
            DECK['lid_m'] = a.lid_m
        if a.hub_zone_m:
            DECK['hub_zone_m'] = a.hub_zone_m
        if a.dense:
            DECK['hashed'] = False
        if a.key_m:
            P['key_m'] = a.key_m
        if a.key_off_m:
            P['key_off_m'] = a.key_off_m
        main_deck(links=[tuple(s.split('-')) for s in a.links] or None, out=a.out)
        sys.exit(0)
    if a.key_m:
        P['key_m'] = a.key_m
    if a.margin_m:
        P['box_margin_m'] = a.margin_m
    if a.profile:
        pr = PROFILES[a.profile]
        P['straights_m'] = pr['straights_m']; P['min_arc_m'] = pr['min_arc_m']
        RADIUS_SETS.clear(); RADIUS_SETS.update(pr['sets'])
        P['profile'] = a.profile
    if a.max_grade:
        P['max_grade'] = a.max_grade
    if a.max_pillar_m:
        P['max_pillar_m'] = a.max_pillar_m
    if a.key_off_m:
        P['key_off_m'] = a.key_off_m
    if a.foot_half_m is not None:
        P['foot_half_m'] = a.foot_half_m
    if a.cut_tol_m is not None:
        P['cut_tol_m'] = a.cut_tol_m
    main(links=[tuple(s.split('-')) for s in a.links] or None, sets=a.sets.split(',') if a.sets else None, out=a.out)
