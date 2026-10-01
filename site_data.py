"""
site_data.py
============
Web sitesinin okuduğu veri dosyasını (site/data/catalog.js) üretir.
Siteye elle sayı girilmez; deneyler koşulduktan sonra bu komut çalıştırılır.

    python site_data.py              # katalog: tüm deneyler + referans + dinamik
    python site_data.py --races      # + yarış animasyonları için örnek rotalar (yavaş)

Topladığı kaynaklar (hangisi varsa):
  results/generated/checkpoints/*.json   üretici deneyleri (run_generated.py); birden çok
                                          protokol varsa en çok örneği olan (--protocol ile seçilir)
  results/batch_*.json                    Kübler referans doğrulaması (run_batch.py)
  results/compare*/                       eşit süreli, çok tohumlu karşılaştırma (run_batch.py)
  results/generated/results__*.json       aynısı, kendi ızgaramızda (run_generated.py)
  results/dynamic/*.json                  dinamik yer ataması (run_dynamic.py)

Yeni bir eksen (ör. 30 000 lokasyon, %40 doluluk, 300 sipariş) ile koşulan
deneyler otomatik olarak sitenin filtrelerinde görünür.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.generator import InstanceSpec, generate

ROOT = Path(__file__).parent
SITE_DATA = ROOT / "site" / "data"
ALGOS = ['DEPSO', 'RBRS-AE', 'RBRS-AE2', 'ALNS']
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


def _protocol_tag(name: str) -> str:
    """'S5000_..__k50__set0__d500__s5__tpo0.05.json' → '__s5__tpo0.05' ('' eski tek tohumlu)."""
    stem = name[:-5] if name.endswith('.json') else name
    rest = stem.split('__d', 1)[1] if '__d' in stem else ''
    return rest[rest.index('__'):] if '__' in rest else ''


def generated_records(protocol: str | None = None) -> tuple[list[dict], str]:
    """Tek bir protokolün örnekleri (protokoller aynı tabloya karışmaz)."""
    files = sorted((ROOT / "results" / "generated" / "checkpoints").glob("*.json"))
    if not files:
        return [], ''
    tags = Counter(_protocol_tag(p.name) for p in files)
    tag = protocol if protocol is not None else max(tags, key=lambda t: (tags[t], t != ''))
    out = []
    for p in files:
        if _protocol_tag(p.name) != tag:
            continue
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
    return out, tag


def comparison_records() -> list[dict]:
    """Eşit süreli, çok tohumlu karşılaştırmaların özeti (compare_algorithms.summarize)."""
    from compare_algorithms import load, summarize
    sources = [(p, 'kubler') for p in sorted((ROOT / "results").glob("compare*")) if p.is_dir()]
    sources += [(p, 'grid') for p in sorted((ROOT / "results" / "generated").glob("results__*.json"))]
    out = []
    for path, kind in sources:
        try:
            inst, meta = load(path)
        except SystemExit:
            continue
        if not inst:
            continue
        s = summarize(inst, meta)
        s.update({'id': path.name, 'kind': kind})
        out.append(s)
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


def _paper_dynamic(problem: str):
    """Kübler senaryolarında makalenin sonucu (config.VALIDATION_TARGETS)."""
    import re
    import config
    m = re.match(r'kubler(?:_fig10)?_s(\d)', problem)
    if not m:
        return None
    t, s = config.VALIDATION_TARGETS, m.group(1)
    return {'reduction_pct': t[f'scenario{s}_travel_distance_reduction_pct'],
            'effort_pct': t[f'scenario{s}_relocation_effort_pct'],
            'net_pct': t[f'scenario{s}_net_improvement_pct']}


def dynamic_records() -> list[dict]:
    """
    Dinamik deneyler. Grupları sabit tutan eski ölçüm (_tdralgo) sitede
    gösterilmez: DEPSO gibi konuma göre gruplayan algoritmalarda kazancı
    olduğundan çok küçük ölçer (docs/RELOCATION.md). Sıra: kendi depolarımız
    (boyuta göre), sonra Kübler koşumları (makaledeki ölçümle yapılanlar önce).
    """
    out = []

    def order(p):
        n = p.stem
        import re
        m = re.match(r'S(\d+)_B(\d)_F(\d+)_(\w+?)_s(\d+)_(.+)$', n)
        if m:                                   # önce kendi depolarımız: boyut, algoritma sırası
            alg = {'DEPSO': 0, 'RBRS-AE': 1, 'ALNS': 2}.get(m.group(6), 3)
            return (0, int(m.group(1)), int(m.group(2)), int(m.group(3)), alg, n)
        return (1, not n.endswith('_tdrfull'), not n.startswith('kubler_fig10'), 0, 0, n.lower())

    for p in sorted((ROOT / "results" / "dynamic").glob("*.json"), key=order):
        if p.stem.endswith('_tdralgo'):
            continue
        d = json.loads(p.read_text(encoding='utf-8'))
        if 'periods' not in d:
            continue
        summary = dict(d['summary'])
        summary['td_static'] = round(sum(r['td_static'] for r in d['periods']), 1)
        summary['td_dynamic'] = round(sum(r['td_dynamic'] for r in d['periods']), 1)
        summary.setdefault('tdr_eval', d.get('tdr_eval') or
                           ('full' if p.stem.endswith('_tdrfull') else 'firstfit'))
        out.append({'problem': d['problem'], 'algorithm': d['algorithm'],
                    'summary': summary, 'paper': _paper_dynamic(d['problem']),
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
    ap.add_argument('--protocol', default=None,
                    help="üretici deneylerinden hangi protokol (ör. __s5__tpo0.05); varsayılan: en çok örneği olan")
    args = ap.parse_args()
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    races_file = SITE_DATA / "races.json"

    if args.races or not races_file.exists():
        t0 = time.perf_counter()
        races = [race(*ex) for ex in RACE_EXAMPLES]
        races_file.write_text(json.dumps(races, separators=(',', ':')), encoding='utf-8')
        print(f"  {len(races)} yarış hesaplandı ({time.perf_counter() - t0:.0f}s)")
    races = json.loads(races_file.read_text(encoding='utf-8'))

    records, tag = generated_records(args.protocol)
    catalog = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M'),
        'git_commit': _git_commit(),
        'algorithms': [a for a in ALGOS if not records or any(a in r['res'] for r in records)],
        'baselines': BASELINES, 'dimensions': DIMENSIONS,
        'records': records,
        'records_protocol': tag,
        'comparisons': comparison_records(),
        'reference': reference_records(),
        'dynamic': dynamic_records(),
        'races': races,
    }
    js = "window.CATALOG = " + json.dumps(catalog, ensure_ascii=False, separators=(',', ':')) + ";\n"
    (SITE_DATA / "catalog.js").write_text(js, encoding='utf-8')
    print(f"site/data/catalog.js: {len(catalog['records'])} deney örneği (protokol '{tag or 'tek tohum'}'), "
          f"{len(catalog['comparisons'])} karşılaştırma, "
          f"{len(catalog['reference'])} referans senaryo, {len(catalog['dynamic'])} dinamik deney, "
          f"{len(races)} yarış ({len(js) // 1024} KB)")


if __name__ == '__main__':
    main()
