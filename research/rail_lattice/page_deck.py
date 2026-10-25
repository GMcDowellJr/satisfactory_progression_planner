"""Rebuild the 'Rail Curve Sweep' page with the deck-height search runs added (research prototype).

Inputs
  research/rail_lattice/out/rail-curve-sweep-v4.html   the published v4 page (page.py output, or
                                                        the artifact saved there): its embedded
                                                        data is the base, so the ground-following
                                                        sweeps need not be rerun
  research/rail_lattice/out/<run>.json                  lattice.py --deck outputs, one file per run
                                                        or one per link (RUNS below)
Output: research/rail_lattice/out/rail-curve-sweep.html (gitignored).

Deck runs join the page as extra entries beside the curve limits. Their minutes are the speed-
profile travel time (profile_minutes), zone edge to zone edge; the ground-following columns are
hub point to hub point without braking, so the two are not comparable. A link whose output file
is missing shows as still running.
"""
import json, math, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'out'
sys.path.insert(0, str(HERE))
from page import thin, speed  # noqa: E402
import lattice  # noqa: E402  (profile_minutes; needs numba, as lattice.py does)

LINKS = ['S2-C2', 'C1-C2', 'C1-C3', 'C3-W3', 'C1-S1', 'W2-W1', 'W1-S1']
# key -> (button name, button note, title, group, H0, file pattern: '{link}' = one file per link)
RUNS = {
    'D5':   ('Deck · 5°', 'H₀ 8 · lid 32', 'Deck search, 5° per foundation', 'kit', 8, 'gate_hash2.json'),
    'DALL': ('Deck · 1–10°', 'H₀ 8 · lid 32', 'Deck search, kit 1–10° per foundation', 'kit', 8, 'kitall_{link}.json'),
    'K8':   ('Kit 1·2·4·10', 'H₀ 8 m', 'Deck search, kit 1·2·4·10°, H₀ 8 m', 'h0', 8, 'k1-2-4-10_h8_l32_{link}.json'),
    'K4':   ('Kit 1·2·4·10', 'H₀ 4 m', 'Deck search, kit 1·2·4·10°, H₀ 4 m', 'h0', 4, 'k1-2-4-10_h4_l32_{link}.json'),
    'K16':  ('Kit 1·2·4·10', 'H₀ 16 m', 'Deck search, kit 1·2·4·10°, H₀ 16 m', 'h0', 16, 'k1-2-4-10_h16_l32_{link}.json'),
    'KINF': ('Kit 1·2·4·10', 'height free', 'Deck search, kit 1·2·4·10°, height unpriced', 'h0', None, 'k1-2-4-10_h1e9_l32_{link}.json'),
    # ceiling sweep at the adopted H0 (Greg, 2026-10-25: H0 8 m, kit 1-2-4-10); K8 is its lid-32 point
    'L64':  ('Kit 1·2·4·10', 'H₀ 8 · lid 64', 'Deck search, kit 1·2·4·10°, H₀ 8 m, lid 64 m', 'lid', 8, 'k1-2-4-10_h8_l64_{link}.json'),
    'L128': ('Kit 1·2·4·10', 'H₀ 8 · lid 128', 'Deck search, kit 1·2·4·10°, H₀ 8 m, lid 128 m', 'lid', 8, 'k1-2-4-10_h8_l128_{link}.json'),
}


def load_run(pattern):
    out = {}
    for link in LINKS:
        f = OUT / pattern.format(link=link)
        if f.exists():
            d = json.loads(f.read_text(encoding='utf-8'))
            if link in d['links']:
                out[link] = (d['links'][link], d)
    return out


def main():
    base = (OUT / 'rail-curve-sweep-v4.html').read_text(encoding='utf-8')
    D = json.loads(re.search(r'const D=(\{.*?\});\n', base, re.S).group(1))
    P = D['policy']; v_max = P['v_max_kmh'] / 3.6; k_pow = D['k_power']
    deck = {}; zone = None
    for key, (name, sub, title, group, h0, pattern) in RUNS.items():
        got = load_run(pattern)
        if not got:
            continue
        meta = next(iter(got.values()))[1]['deck']; zone = meta['hub_zone_m']
        deck[key] = dict(name=name, sub=sub, title=title, group=group, h0=h0, kit=meta['kit_deg'], lid=meta['lid_m'],
                         acc=meta['acc_mps2'], done=len(got))
        D['sets'][key] = 0
        for l in D['links']:
            lk = f"{l['a']}-{l['b']}"
            if lk not in got:
                l['runs'][key] = dict(found=False, pending=True); continue
            r = got[lk][0]
            if not r['found']:
                l['runs'][key] = dict(found=False); continue
            mv = []
            for m in r['moves']:
                vc, vu = speed(m, P, v_max, k_pow)
                mv.append(dict(R=m['R'], L=m['L'], g=m['grade'], pil=m['h_max'], h=m['h_mean'], vc=vc, vu=vu,
                               pts=thin(m['pts'])))
            # outputs written before d264e6b carry no profile time: compute it from their moves
            prof = r['minutes_profile'] if 'minutes_profile' in r else lattice.profile_minutes(r['moves'], meta['acc_mps2'])
            l['runs'][key] = dict(
                found=True, km=r['km'], minutes=prof, search_minutes=r['minutes'],
                speed_change=r.get('min_speed_change'), h_mean=r['h_mean'], h_max=r['h_max'], km_over_8m=r['km_over_8m'],
                steep_m=round(sum(m['L'] for m in r['moves'] if abs(m['grade']) > 0.125)),
                viaduct_m=round(sum(m['L'] for m in r['moves'] if m['h_mean'] > 4)),
                moves=mv, unstable=False, alt_minutes=[],
                curves={str(round(rad)): sum(1 for m in r['moves'] if m['R'] == rad)
                        for rad in sorted({m['R'] for m in r['moves'] if m['R'] > 0}, reverse=True)})
    if deck:
        # deck entries first after the radius limits, so the page opens on the newest work
        D['deck'] = deck; D['zone_m'] = zone
    html = (HERE / 'page_template.html').read_text(encoding='utf-8').replace('/*DATA*/null', json.dumps(D, separators=(',', ':')))
    (OUT / 'rail-curve-sweep.html').write_text(html, encoding='utf-8', newline='\n')
    print('wrote', OUT / 'rail-curve-sweep.html', len(html) // 1024, 'KB;', {k: v['done'] for k, v in deck.items()})


if __name__ == '__main__':
    main()
