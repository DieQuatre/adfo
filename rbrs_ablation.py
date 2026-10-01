"""
rbrs_ablation.py
================
RBRS-AE iyileştirmelerinin tek tek ve birlikte katkısı (algorithms/rbrs_ae2.py).

Her varyant eşit süre bütçesiyle (sipariş başına --tpo sn) aynı örneklerde,
birkaç tohumla çözülür. Ölçü: örnek bazında ALNS'ye ve özgün RBRS-AE'ye göre
ortalama fark (%), Wilcoxon testi.

    python rbrs_ablation.py --jobs 16                 # küçük set (8 örnek)
    python rbrs_ablation.py --jobs 16 --full --seeds 5    # geniş set (85 örnek), ~30-40 dk
    python rbrs_ablation.py --jobs 16 --variants RBRS-AE,RBRS-AE2
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from algorithms.alns import ALNS
from algorithms.rbrs_ae import RBRS_AE
from algorithms.rbrs_ae2 import IMPROVED, RECOMMENDED, RBRS_AE2
from core import experiment as ex

VARIANTS = {'RBRS-AE': {}}
for k, v in IMPROVED.items():
    VARIANTS[f'+{k}'] = {k: v}
VARIANTS['hepsi'] = dict(IMPROVED)
VARIANTS['RBRS-AE2'] = dict(RECOMMENDED)
REFERENCE = 'ALNS'


def make(name: str, seed: int, budget: float):
    if name == REFERENCE:
        a = ALNS(seed=seed)
    elif name == 'RBRS-AE':
        a = RBRS_AE(seed=seed)
    else:
        a = RBRS_AE2(label=name, seed=seed, **VARIANTS[name])
    a.time_limit = budget
    return a


def instances(full: bool):
    """(ad, siparişler, depo) üreten tanımlar; işçide yeniden kurulur."""
    out = []
    sizes = [5000, 10000, 20000] if full else [10000]
    for size in sizes:
        for blocks in ([1, 2, 3] if full else [2]):
            for k in (50, 100, 200) if full else (100, 200):
                for s in range(3 if full else 2):
                    out.append(('gen', size, blocks, 0.7, k, s))
    for (n, a, k) in ((10, 10, 100), (10, 10, 200), (6, 6, 150), (2, 6, 100)):
        out.append(('kubler', n, a, None, k, 0))
    return out


_CACHE = {}


def _load(spec):
    if spec in _CACHE:
        return _CACHE[spec]
    kind = spec[0]
    if kind == 'gen':
        from core.generator import InstanceSpec, generate
        _, size, blocks, fill, k, s = spec
        inst = generate(InstanceSpec(size, blocks, fill, 'orta', 0))
        res = (f"G{size}_B{blocks}_k{k}_set{s}", inst.sample_orders(k, s), inst.warehouse)
    else:
        from core.warehouse import Warehouse
        from run_batch import load_pool
        _, n, a, _, k, s = spec
        pool = load_pool(n, a)[:]
        random.Random(1000 + k + s).shuffle(pool)
        res = (f"K{k}_{n}_{a}", pool[:k], Warehouse())
    _CACHE.clear()
    _CACHE[spec] = res
    return res


def _task(t):
    spec, name, seed, tpo = t
    label, orders, wh = _load(spec)
    sol = make(name, seed, tpo * len(orders)).solve(orders, wh)
    return label, name, seed, sol.total_travel_distance, sol.iterations_used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--seeds', type=int, default=2)
    ap.add_argument('--tpo', type=float, default=0.05)
    ap.add_argument('--full', action='store_true')
    ap.add_argument('--variants', default=None, help="virgülle ayrılmış alt küme")
    args = ap.parse_args()

    names = list(VARIANTS) + [REFERENCE]
    if args.variants:
        names = [n for n in names if n in args.variants.split(',')] + [REFERENCE]
    specs = instances(args.full)
    tasks = [(sp, n, 17 + 7919 * j, args.tpo) for sp in specs for n in names for j in range(args.seeds)]
    print(ex.speed_note())
    print(f"{len(specs)} örnek × {len(names)} algoritma × {args.seeds} tohum = {len(tasks)} çözüm, "
          f"sipariş başına {args.tpo} sn")
    t0 = time.perf_counter()
    res = {}
    if args.jobs > 1:
        with Pool(args.jobs) as p:
            it = p.imap_unordered(_task, tasks)
            for i, r in enumerate(it, 1):
                res.setdefault((r[0], r[1]), []).append(r[3])
                if i % 20 == 0:
                    print(f"  {i}/{len(tasks)} [{time.perf_counter() - t0:.0f}s]", flush=True)
    else:
        for t in tasks:
            r = _task(t)
            res.setdefault((r[0], r[1]), []).append(r[3])

    labels = sorted({k[0] for k in res})
    mean = {k: statistics.fmean(v) for k, v in res.items()}
    lines = ["# RBRS-AE iyileştirme denemesi", "",
             f"{len(labels)} örnek, {args.seeds} tohum, sipariş başına {args.tpo} sn, kod {ex.git_state()['commit']}", "",
             "| Varyant | ALNS'ye göre fark | özgün RBRS-AE'ye göre fark | özgünden iyi olduğu örnek | p |",
             "|---|---|---|---|---|"]
    for n in names:
        if n == REFERENCE:
            continue
        d_alns = statistics.fmean((mean[(l, n)] - mean[(l, REFERENCE)]) / mean[(l, REFERENCE)] * 100 for l in labels)
        d_orig = statistics.fmean((mean[(l, n)] - mean[(l, 'RBRS-AE')]) / mean[(l, 'RBRS-AE')] * 100 for l in labels)
        w = ex.wilcoxon([mean[(l, n)] for l in labels], [mean[(l, 'RBRS-AE')] for l in labels])
        lines.append(f"| {n} | %{d_alns:+.2f} | %{d_orig:+.2f} | {w['x_better']}/{len(labels)} | "
                     f"{ex.fmt_p(w['p']) if n != 'RBRS-AE' else '—'} |")
    lines += ["", "Negatif: daha kısa mesafe."]
    text = "\n".join(lines)
    print(text)
    out = Path("results") / "rbrs_ablation"
    out.mkdir(parents=True, exist_ok=True)
    tag = f"{'full' if args.full else 'small'}_s{args.seeds}_tpo{args.tpo:g}"
    (out / f"{tag}.md").write_text(text, encoding='utf-8')
    (out / f"{tag}.json").write_text(json.dumps({'git': ex.git_state(), 'args': vars(args),
        'results': {f"{l}|{n}": res[(l, n)] for (l, n) in res}}, indent=1), encoding='utf-8')
    print(f"Kayıt: {out / (tag + '.md')}")


if __name__ == '__main__':
    main()
