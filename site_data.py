"""
site_data.py
============
Web sitesinin okuduğu veri dosyasını (site/data/catalog.js) üretir.
Siteye elle sayı girilmez; deneyler koşulduktan sonra bu komut çalıştırılır.

    python site_data.py              # katalog: tüm deneyler + referans + dinamik
    python site_data.py --races      # + yarış animasyonları için örnek rotalar (yavaş)

Topladığı kaynaklar (hangisi varsa):
  results/generated/checkpoints/*.json   üretici deneyleri (run_generated.py)
  results/batch_*.json                    Kübler referans doğrulaması (run_batch.py)
  results/dynamic/*.json                  dinamik yer ataması (run_dynamic.py)

Yeni bir eksen (ör. 30 000 lokasyon, %40 doluluk, 300 sipariş) ile koşulan
deneyler otomatik olarak sitenin filtrelerinde görünür.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.generator import InstanceSpec, generate

ROOT = Path(__file__).parent
SITE_DATA = ROOT / "site" / "data"
ALGOS = ['DEPSO', 'RBRS-AE', 'ALNS']
BASELINES = ['SOP', 'FCFS']

DIMENSIONS = [
    {'key': 'locations', 'label': 'Depo boyutu', 'unit': 'lokasyon'},
    {'key': 'blocks', 'label': 'Koridor yapısı', 'unit': '',
     'names': {'1': 'Geçişsiz', '2': 'Tek geçişli', '3': 'İki geçişli'}},
    {'key': 'fill', 'label': 'Doluluk', 'unit': '%'},
    {'key': 'dynamics', 'label': 'Talep dinamikliği', 'unit': '',
     'names': {'dusuk': 'Düşük', 'orta': 'Orta', 'yuksek': 'Yüksek'}},
    {'key': 'k', 'label': 'Sipariş sayısı', 'unit': 'sipariş'},
]


def _git_commit() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return 'bilinmiyor'


def generated_records() -> list[dict]:
    out = []
    for p in sorted((ROOT / "results" / "generated" / "checkpoints").glob("*.json")):
        r = json.loads(p.read_text(encoding='utf-8'))
        spec = r['spec']
        out.append({
            'id': p.stem,
            'size': spec['size'], 'locations': r.get('total_locations', spec['size']),
            'blocks': spec['blocks'], 'fill': round(spec['fill'] * 100),
            'dynamics': spec['dynamics'], 'seed': spec['seed'],
            'k': r['k'], 'set': r['set_id'],
            'res': {a: {'td': round(r[a]['td'], 1), 'rt': round(r[a]['rt'], 2),
                        'b': r[a]['batches']} for a in ALGOS + BASELINES if a in r},
        })
    return out


def reference_records() -> list[dict]:
    """Kübler referans doğrulaması: DEPSO'nun makaledeki SOP'a göre kazancına yakınlığı."""
    out = []
    for p in sorted((ROOT / "results").glob("batch_*.json")):
        d = json.loads(p.read_text(encoding='utf-8'))
        for r in d.get('results', []):
            st = r.get('stats', {})
            if 'DEPSO' not in st:
                continue
            out.append({'scenario': r['scenario'], 'k': r['k'],
                        'paper': r.get('paper_vs_sop'),
                        'ours': {a: st[a]['vs_sop_mean'] for a in ALGOS if a in st},
                        'n': r.get('n_instances')})
    return out


def dynamic_records() -> list[dict]:
    out = []
    for p in sorted((ROOT / "results" / "dynamic").glob("*.json")):
        d = json.loads(p.read_text(encoding='utf-8'))
        if 'periods' not in d:
            continue
        out.append({'problem': d['problem'], 'algorithm': d['algorithm'],
                    'summary': d['summary'],
                    'periods': [{k: r[k] for k in ('period', 'reduction_pct', 'effort_pct',
                                                   'net_pct', 'accepted', 'tested')}
                                for r in d['periods']]})
    return out


# ── Yarış animasyonları ─────────────────────────────────────────────────

def _geometry(wh) -> dict:
    racks = []
    for aisle in range(wh.num_aisles):
        yc = wh.aisle_y[aisle]
        for blk in range(wh.num_blocks):
            x0 = wh.cross_aisle_x[blk] + (wh.cross_aisle_width if blk > 0 else 0)
            racks.append([x0, yc - 1.5, wh.block_length, 1.0])
            racks.append([x0, yc + 0.5, wh.block_length, 1.0])
    return {'w': wh.depot_x + 2, 'h': wh.num_aisles * wh.aisle_spacing,
            'depot': [wh.depot_x, wh.depot_y], 'cross': wh.cross_aisle_x,
            'crossW': wh.cross_aisle_width, 'racks': racks}


def _leg(wh, a, b):
    xa, ya = wh.coords(a)
    xb, yb = wh.coords(b)
    if a != wh.DEPOT and b != wh.DEPOT and wh._aisle_of(a) == wh._aisle_of(b):
        return [[xb, yb]]
    cands = list(wh.cross_aisle_x) + ([wh.depot_x] if wh.DEPOT in (a, b) else [])
    cx = min(cands, key=lambda c: abs(xa - c) + abs(ya - yb) + abs(xb - c))
    out = []
    for p in ([cx, ya], [cx, yb], [xb, yb]):
        if not out or out[-1] != p:
            out.append(p)
    return out


def race(spec: InstanceSpec, k: int, set_id: int, depso_iter: int = 500) -> dict:
    from run_batch import make_algorithms
    inst = generate(spec)
    wh = inst.warehouse
    orders = inst.sample_orders(k, set_id)
    seed = 1000 * set_id + k                      # run_generated.py ile aynı tohum
    algos = make_algorithms(seed, depso_iter)
    res = []
    for name in ALGOS:
        sol = algos[name].solve(orders, wh)
        batches = []
        for b in sol.batches:
            path = [list(wh.coords(wh.DEPOT))]
            stops = []
            for i in range(len(b.route) - 1):
                path += _leg(wh, b.route[i], b.route[i + 1])
                loc = b.route[i + 1]
                if loc != wh.DEPOT:
                    L = wh.get_location(loc)
                    stops.append([round(L.x, 2), round(L.y, 2), L.side])
            batches.append({'orders': len(b.orders), 'dist': round(b.travel_distance, 1),
                            'path': [[round(x, 2), round(y, 2)] for x, y in path],
                            'stops': stops})
        res.append({'name': name, 'total': round(sol.total_travel_distance, 1),
                    'runtime': round(sol.runtime_seconds, 1), 'batches': batches})
    return {'id': f"{spec.name}__k{k}__set{set_id}",
            'dims': {'locations': wh.total_locations, 'blocks': spec.blocks,
                     'fill': round(spec.fill * 100), 'dynamics': spec.dynamics, 'k': k},
            'geometry': _geometry(wh), 'algorithms': res}


RACE_EXAMPLES = [
    (InstanceSpec(5000, 1, 0.7, 'orta', 0), 50, 0),
    (InstanceSpec(5000, 3, 0.7, 'orta', 0), 50, 0),
    (InstanceSpec(10000, 2, 0.9, 'orta', 0), 100, 0),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--races', action='store_true', help='örnek yarışları yeniden hesapla')
    args = ap.parse_args()
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    races_file = SITE_DATA / "races.json"

    if args.races or not races_file.exists():
        t0 = time.perf_counter()
        races = [race(*ex) for ex in RACE_EXAMPLES]
        races_file.write_text(json.dumps(races, separators=(',', ':')), encoding='utf-8')
        print(f"  {len(races)} yarış hesaplandı ({time.perf_counter() - t0:.0f}s)")
    races = json.loads(races_file.read_text(encoding='utf-8'))

    catalog = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M'),
        'git_commit': _git_commit(),
        'algorithms': ALGOS, 'baselines': BASELINES, 'dimensions': DIMENSIONS,
        'records': generated_records(),
        'reference': reference_records(),
        'dynamic': dynamic_records(),
        'races': races,
    }
    js = "window.CATALOG = " + json.dumps(catalog, ensure_ascii=False, separators=(',', ':')) + ";\n"
    (SITE_DATA / "catalog.js").write_text(js, encoding='utf-8')
    print(f"site/data/catalog.js: {len(catalog['records'])} deney örneği, "
          f"{len(catalog['reference'])} referans senaryo, {len(catalog['dynamic'])} dinamik deney, "
          f"{len(races)} yarış ({len(js) // 1024} KB)")


if __name__ == '__main__':
    main()
