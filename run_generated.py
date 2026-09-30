"""
run_generated.py
================
Parametrik üreticinin depolarında algoritma karşılaştırması
("büyüklü küçüklü" deney). 35 senaryo koşucusunun (run_batch.py) karşılığı.

    python run_generated.py --jobs 8                       # tüm ızgara
    python run_generated.py --sizes 5000 --sets 2 --k 50   # küçük deneme
    python run_generated.py --summary                      # kayıtlı sonuç özeti

Her depo × sipariş seti için SOP, FCFS, DEPSO, RBRS-AE, ALNS aynı siparişlerle
koşar. --seeds ve --time-budget run_batch.py ile aynı (docs/DENEY_PROTOKOLU.md);
commit'lenmemiş değişiklik varken koşum başlamaz (--allow-dirty). Sonuçlar örnek bittikçe results/generated/checkpoints/ altına yazılır;
kesilen koşum aynı komutla devam eder. Özet: results/generated/summary.md.
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config
from config import GENERATOR as GEN
from core.generator import InstanceSpec, generate
from core import experiment as ex
from core.experiment import ALGORITHMS, Protocol

OUT = Path("results") / "generated"
CKPT = OUT / "checkpoints"
_CACHE: dict = {}


def _instance(spec: InstanceSpec):
    if spec not in _CACHE:
        _CACHE.clear()          # işçi başına tek depo bellekte
        _CACHE[spec] = generate(spec)
    return _CACHE[spec]


def _ckpt(spec: InstanceSpec, set_id: int, k: int, proto: Protocol) -> Path:
    return CKPT / f"{spec.name}__k{k}__set{set_id}__d{proto.depso_iter}{proto.tag}.json"


def _run(task):
    spec, set_id, k, proto = task
    inst = _instance(spec)
    orders = inst.sample_orders(k, set_id)
    seed = 1000 * set_id + k
    res = {'name': spec.name, 'spec': spec.__dict__, 'set_id': set_id, 'k': k, 'seed': seed,
           'total_locations': inst.warehouse.total_locations}
    res.update(ex.solve_all(orders, inst.warehouse, seed, proto))
    return res


def summarise(rows: list[dict], proto: Protocol | None = None) -> str:
    lines = ["# Parametrik ızgara — algoritma karşılaştırması", "",
             f"Kod sürümü: `{ex.git_state()['commit']}`, {len(rows)} örnek"
             + (f", protokol {proto.to_dict()}" if proto else "") + ".", ""]
    algs = [a for a in ('DEPSO', 'RBRS-AE', 'ALNS')]

    def table(key_fn, title):
        groups = defaultdict(list)
        for r in rows:
            groups[key_fn(r)].append(r)
        out = [f"## {title}", "",
               "| grup | n | " + " | ".join(f"{a} LU" for a in algs) + " | " +
               " | ".join(f"{a} s" for a in algs) + " | en iyi (adet) |",
               "|---|---|" + "---|" * (2 * len(algs) + 1)]
        for key in sorted(groups):
            g = groups[key]
            wins = defaultdict(int)
            for r in g:
                best = min(r[a]['td'] for a in algs)
                winners = [a for a in algs if r[a]['td'] <= best + 1e-6]
                wins[winners[0] if len(winners) == 1 else 'berabere'] += 1
            td = [sum(r[a]['td'] for r in g) / len(g) for a in algs]
            rt = [sum(r[a]['rt'] for r in g) / len(g) for a in algs]
            out.append(f"| {key} | {len(g)} | " + " | ".join(f"{x:.0f}" for x in td) + " | " +
                       " | ".join(f"{x:.1f}" for x in rt) + " | " +
                       ", ".join(f"{a} {wins[a]}" for a in algs + ['berabere']) + " |")
        return out + [""]

    lines += table(lambda r: r['spec']['size'], "Depo boyutuna göre")
    lines += table(lambda r: r['spec']['blocks'], "Koridor yapısına göre (blok sayısı)")
    lines += table(lambda r: r['spec']['fill'], "Doluluğa göre")
    lines += table(lambda r: r['k'], "Sipariş sayısına göre")
    return "\n".join(lines)


def load_all(proto: Protocol) -> list[dict]:
    """Yalnızca bu protokolle alınmış checkpoint'ler (protokoller karışmaz)."""
    suffix = f"__d{proto.depso_iter}{proto.tag}.json"
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(CKPT.glob("*.json"))
            if p.name.endswith(suffix)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sizes', type=int, nargs='*', default=GEN['grid_sizes'])
    ap.add_argument('--blocks', type=int, nargs='*', default=GEN['grid_blocks'])
    ap.add_argument('--fills', type=float, nargs='*', default=GEN['grid_fills'])
    ap.add_argument('--sets', type=int, default=GEN['order_sets_per_warehouse'])
    ap.add_argument('--k', type=int, nargs='*', default=[GEN['order_set_size']])
    ap.add_argument('--dynamics', default=GEN['default_dynamics'])
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--depso-iter', type=int, default=config.DEPSO['num_iterations'])
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--summary', action='store_true')
    ap.add_argument('--seeds', type=int, default=1)
    ap.add_argument('--time-budget', type=float, default=None)
    ap.add_argument('--time-per-order', type=float, default=None)
    ap.add_argument('--allow-dirty', action='store_true')
    args = ap.parse_args()
    proto = Protocol(depso_iter=args.depso_iter, n_seeds=args.seeds, time_budget=args.time_budget,
                     time_per_order=args.time_per_order)
    tag = proto.tag

    OUT.mkdir(parents=True, exist_ok=True)
    CKPT.mkdir(parents=True, exist_ok=True)
    if args.summary:
        rows = load_all(proto)
        print(summarise(rows) if rows else "Henüz sonuç yok.")
        return

    # Izgara yalnızca varsayılan; komut satırında verilen her değer koşulur
    # (ör. --sizes 30000 ya da --fills 0.4, config'teki ızgarada olmasa bile).
    specs = [InstanceSpec(size, b, f, args.dynamics, args.seed)
             for size in args.sizes for b in args.blocks for f in args.fills]
    # Aynı depoyu kullanan işler art arda gelsin (işçi önbelleği için)
    git = ex.require_clean(args.allow_dirty)
    tasks = [(s, i, k, proto) for s in specs for k in args.k for i in range(args.sets)]
    todo = [t for t in tasks if not _ckpt(*t).exists()]
    print(f"{len(specs)} depo × {args.sets} set × k={args.k} → {len(tasks)} örnek "
          f"({len(tasks) - len(todo)} zaten bitmiş), {args.jobs} paralel işlem")

    t0 = time.perf_counter()
    done = len(tasks) - len(todo)

    def report(r):
        nonlocal done
        done += 1
        spec = InstanceSpec(**r['spec'])
        _ckpt(spec, r['set_id'], r['k'], proto).write_text(json.dumps(r), encoding='utf-8')
        parts = ' '.join(f"{a}={r[a]['td']:.0f}" for a in ALGORITHMS)
        print(f"  [{done}/{len(tasks)} {time.perf_counter() - t0:6.0f}s] {r['name']} k={r['k']} "
              f"set{r['set_id']}: {parts}", flush=True)

    if args.jobs > 1 and todo:
        with Pool(args.jobs) as pool:
            for r in pool.imap_unordered(_run, todo, chunksize=1):
                report(r)
    else:
        for t in todo:
            report(_run(t))

    rows = load_all(proto)
    (OUT / f"summary{tag}.md").write_text(summarise(rows, proto), encoding='utf-8')
    (OUT / f"results{tag}.json").write_text(json.dumps({
        'git_commit': git['commit'], 'git': git, 'depso_iter': args.depso_iter,
        'protocol': proto.to_dict(), 'jobs': args.jobs,
        'config': {'DEPSO': config.DEPSO, 'RBRS_AE': config.RBRS_AE, 'ALNS': config.ALNS,
                   'GENERATOR': GEN},
        'results': rows}, indent=1), encoding='utf-8')
    print(f"\n✓ {len(rows)} örnek. Özet: {OUT / f'summary{tag}.md'}")
    if tag:
        print(f"Karşılaştırma raporu: python compare_algorithms.py {OUT / f'results{tag}.json'}")


if __name__ == '__main__':
    main()
