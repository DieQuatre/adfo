"""
run_batch.py
=============
35 senaryoyu (Kübler Appendix H) koşturur: SOP, FCFS, DEPSO, RBRS-AE, ALNS.

Kullanım:
    python run_batch.py --batch 1              # senaryo 1-5
    python run_batch.py --batch all --jobs 8   # 35 senaryo, 8 paralel işlem
    python run_batch.py --summary              # kayıtlı sonuçların özeti

Her senaryo: data*/ havuzundan k siparişlik --n örnek; her örnekte tüm
algoritmalar AYNI siparişlerle koşar. Algoritma ayarları config.py'den gelir;
yalnızca DEPSO iterasyonu komut satırından değiştirilebilir (varsayılan: makale, 500).

Sonuç dosyası results/batch_<i>.json: ortalamalar + örnek bazında ham değerler
(istatistiksel testler ve web sitesi için) + kullanılan ayarlar ve kod sürümü.
"""

import sys
import json
import time
import random
import argparse
import subprocess
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.warehouse import Warehouse
from core.data_loader import DataLoader
from benchmarks.sop import SOP
from benchmarks.fcfs import FCFS
from algorithms.depso import DEPSO
from algorithms.rbrs_ae import RBRS_AE
from algorithms.alns import ALNS
import config

ALGORITHMS = ['SOP', 'FCFS', 'DEPSO', 'RBRS-AE', 'ALNS']


# ════════════════════════════════════════════════════════════════════════════
# 35 SENARYO LİSTESİ
# ════════════════════════════════════════════════════════════════════════════

ALL_35 = []
for k in [50, 100, 150, 200]:
    for n_maxol in [2, 6, 10]:
        for a_maxol in [2, 6, 10]:
            if k == 50 and n_maxol == 2 and a_maxol == 2:
                continue
            ALL_35.append({'k': k, 'n': n_maxol, 'a': a_maxol,
                           'name': f'{k}_{n_maxol}_{a_maxol}'})

# 7 batch × 5 senaryo = 35
BATCHES = [ALL_35[i:i+5] for i in range(0, 35, 5)]

# Paper referans değerleri (Appendix H)
PAPER = {
    '50_2_6':   -88.52, '50_2_10':  -87.13, '50_6_2':   -87.36,
    '50_6_6':   -81.54, '50_6_10':  -77.49, '50_10_2':  -84.83,
    '50_10_6':  -76.61, '50_10_10': -70.60,
    '100_2_2':  -92.74, '100_2_6':  -90.79, '100_2_10': -88.63,
    '100_6_2':  -89.20, '100_6_6':  -82.77, '100_6_10': -78.51,
    '100_10_2': -86.23, '100_10_6': -77.36, '100_10_10':-71.25,
    '150_2_2':  -94.22, '150_2_6':  -91.23, '150_2_10': -89.25,
    '150_6_2':  -89.34, '150_6_6':  -82.89, '150_6_10': -78.45,
    '150_10_2': -86.22, '150_10_6': -77.32, '150_10_10':-71.41,
    '200_2_2':  -94.26, '200_2_6':  -91.54, '200_2_10': -89.26,
    '200_6_2':  -89.61, '200_6_6':  -82.58, '200_6_10': -78.35,
    '200_10_2': -86.11, '200_10_6': -77.21, '200_10_10':-71.57,
}


# ════════════════════════════════════════════════════════════════════════════
# SİPARİŞ KAYNAĞI
# ════════════════════════════════════════════════════════════════════════════
#
# Tek kaynak: Kübler parametreleriyle üretilmiş data*/ dizinleri.
# Dizin yoksa ya da havuz k siparişi karşılamıyorsa koşum AÇIK HATA verir.
# (Eskiden sessizce sentetik bir üreticiye düşülüyordu; o üretici talebi
# A-sınıfına yığdığı için SOP tabanını yapay düşürüp kazancı şişiriyordu.)

DATA_DIR_MAP = {
    (2,  2): 'data_2_2',   (2,  6): 'data',      (2, 10): 'data_2_10',
    (6,  2): 'data_6_2',   (6,  6): 'data_6_6',  (6, 10): 'data_6_10',
    (10, 2): 'data_10_2',  (10, 6): 'data_10_6', (10, 10): 'data_10_10',
}

_POOL_CACHE: dict = {}


def load_pool(n_maxol: int, a_maxol: int) -> list:
    """(n_maxol, a_maxol) kombinasyonunun tüm alt-periyot siparişlerini topla."""
    key = (n_maxol, a_maxol)
    if key in _POOL_CACHE:
        return _POOL_CACHE[key]

    ddir = Path(__file__).parent / DATA_DIR_MAP[key]
    if not ddir.exists():
        _POOL_CACHE[key] = []
        return []

    loader = DataLoader(ddir)
    pool = []
    for sub in range(1, 21):
        try:
            pool.extend(loader.load_orders(1, 1, sub).orders)
        except FileNotFoundError:
            pass
    _POOL_CACHE[key] = pool
    return pool


def sample_instances(n_maxol: int, a_maxol: int, k: int,
                     n_instances: int) -> list:
    """
    Havuzdan k siparişlik n_instances örnek çek.

    Tohum formülü: inst_id*7 + 42 + k. Tohumun k'ya bağlı olması, farklı k
    değerlerinin farklı alt küme almasını garantiler.
    """
    pool = load_pool(n_maxol, a_maxol)
    if len(pool) < k:
        raise RuntimeError(
            f"{DATA_DIR_MAP[(n_maxol, a_maxol)]}/ havuzunda {len(pool)} sipariş var, "
            f"k={k} isteniyor. Veri dizini eksik ya da yetersiz."
        )

    out = []
    for inst_id in range(n_instances):
        seed = inst_id * 7 + 42 + k
        shuffled = pool[:]
        random.Random(seed).shuffle(shuffled)
        out.append((shuffled[:k], seed))
    return out


# ════════════════════════════════════════════════════════════════════════════
# TEK SENARYO KOŞUMU
# ════════════════════════════════════════════════════════════════════════════

def _mean(v): return sum(v)/len(v) if v else 0.0

def _instance_seed(inst_id: int, k: int) -> int:
    return inst_id * 7 + 42 + k      # sample_instances ile aynı formül


_WH = None


def _run_instance(task: tuple) -> dict:
    """Tek bir (senaryo, örnek) için tüm algoritmalar. Paralel işçide çalışır."""
    global _WH
    if _WH is None:
        _WH = Warehouse()
    name, k, n, a, inst_id, depso_iter = task
    seed = _instance_seed(inst_id, k)
    pool = load_pool(n, a)
    if len(pool) < k:
        raise RuntimeError(f"{DATA_DIR_MAP[(n, a)]}/ havuzu k={k} için yetersiz")
    shuffled = pool[:]
    random.Random(seed).shuffle(shuffled)
    orders = shuffled[:k]

    algos = {
        'SOP':     SOP(),
        'FCFS':    FCFS(),
        'DEPSO':   DEPSO(num_iterations=depso_iter, seed=seed),
        'RBRS-AE': RBRS_AE(seed=seed),     # ayarlar config.RBRS_AE
        'ALNS':    ALNS(seed=seed),        # ayarlar config.ALNS
    }
    out = {'scenario': name, 'inst_id': inst_id, 'seed': seed}
    for alg in ALGORITHMS:
        sol = algos[alg].solve(orders, _WH)
        out[alg] = {'td': sol.total_travel_distance,
                    'rt': sol.runtime_seconds,
                    'batches': sol.num_batches}
    return out


def _aggregate(scenario: dict, inst_results: list[dict]) -> dict:
    name, k, n, a = scenario['name'], scenario['k'], scenario['n'], scenario['a']
    paper = PAPER.get(name, '?')
    inst_results = sorted(inst_results, key=lambda r: r['inst_id'])
    sop = [r['SOP']['td'] for r in inst_results]
    fcfs = [r['FCFS']['td'] for r in inst_results]
    stats = {}
    for alg in ALGORITHMS:
        tds = [r[alg]['td'] for r in inst_results]
        rts = [r[alg]['rt'] for r in inst_results]
        vs_sop = [(t - s) / s * 100 for t, s in zip(tds, sop) if s > 0]
        vs_fcfs = [(t - f) / f * 100 for t, f in zip(tds, fcfs) if f > 0]
        stats[alg] = {
            'mean_td':      round(_mean(tds), 1),
            'mean_rt':      round(_mean(rts), 2),
            'vs_sop_mean':  round(_mean(vs_sop), 2),
            'vs_fcfs_mean': round(_mean(vs_fcfs), 2),
            'td':           [round(t, 3) for t in tds],
            'rt':           [round(t, 3) for t in rts],
            'batches':      [r[alg]['batches'] for r in inst_results],
        }
    return {'scenario': name, 'k': k, 'n_maxol': n, 'a_maxol': a,
            'paper_vs_sop': paper, 'n_instances': len(inst_results),
            'seeds': [r['seed'] for r in inst_results],
            'order_source': 'data_pool', 'stats': stats}


def run_scenarios(scenarios: list[dict], n_instances: int, depso_iter: int,
                  jobs: int = 1) -> list[dict]:
    tasks = [(s['name'], s['k'], s['n'], s['a'], i, depso_iter)
             for s in scenarios for i in range(n_instances)]
    done: dict[str, list] = {s['name']: [] for s in scenarios}
    t0 = time.perf_counter()

    def _report(r):
        done[r['scenario']].append(r)
        parts = ' '.join(f"{alg}={r[alg]['td']:.0f}" for alg in ALGORITHMS)
        n_done = sum(len(v) for v in done.values())
        print(f"  [{n_done}/{len(tasks)} {time.perf_counter() - t0:6.0f}s] "
              f"{r['scenario']} #{r['inst_id'] + 1}: {parts}", flush=True)

    if jobs > 1:
        with Pool(jobs) as pool:
            for r in pool.imap_unordered(_run_instance, tasks):
                _report(r)
    else:
        for t in tasks:
            _report(_run_instance(t))

    return [_aggregate(s, done[s['name']]) for s in scenarios]


def _git_commit() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'],
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return 'bilinmiyor'


# ════════════════════════════════════════════════════════════════════════════
# RAPOR
# ════════════════════════════════════════════════════════════════════════════

def print_summary(results: list):
    print("\n" + "="*72)
    print("ÖZET TABLO — Paper Appendix H vs Bizim Sonuçlarımız")
    print("="*72)
    print(f"{'Senaryo':<12} {'DEPSO/SOP':>10} {'Paper':>10} {'Fark':>8} "
          f"{'RBRS/SOP':>10} {'ALNS/SOP':>10} {'Durum':>6}")
    print("-"*72)

    for r in results:
        if 'stats' not in r or 'DEPSO' not in r.get('stats', {}):
            print(f"{r['scenario']:<12} {'HATA':>10}")
            continue
        depso = r['stats']['DEPSO']['vs_sop_mean']
        rbrs  = r['stats']['RBRS-AE']['vs_sop_mean']
        alns  = r['stats'].get('ALNS', {}).get('vs_sop_mean', float('nan'))
        paper = r['paper_vs_sop']
        diff  = round(depso - paper, 2) if isinstance(paper, float) else 0
        ok    = "✅" if abs(diff) < 8 else "⚠️"
        print(f"{r['scenario']:<12} {depso:>10.2f}% {paper:>10.2f}% "
              f"{diff:>+8.2f}% {rbrs:>10.2f}% {alns:>10.2f}%  {ok}")

    print("="*72)


def load_all_results() -> list:
    """Tüm batch sonuçlarını birleştir."""
    all_results = []
    results_dir = Path("results")
    for i in range(1, 8):
        path = results_dir / f"batch_{i}.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            all_results.extend(data.get('results', []))
    return all_results


# ════════════════════════════════════════════════════════════════════════════
# ANA
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=str, required=False,
                        help="1-7 ya da 'all'. Belirtilmezse özet gösterir.")
    parser.add_argument("--n", type=int, default=5,
                        help="Senaryo başına örnek sayısı (varsayılan 5)")
    parser.add_argument("--depso-iter", type=int,
                        default=config.DEPSO['num_iterations'],
                        help="DEPSO iterasyon (varsayılan config: 500, makale)")
    parser.add_argument("--jobs", type=int, default=1,
                        help="Paralel işlem sayısı (örn. çekirdek sayısı - 2)")
    parser.add_argument("--only", type=str, default=None,
                        help="Yalnızca bu senaryolar, örn. 50_2_6,100_6_6 "
                             "(sonuç results/only.json'a yazılır, batch dosyaları değişmez)")
    parser.add_argument("--summary", action="store_true",
                        help="Tüm batch sonuçlarını özetler")
    args = parser.parse_args()

    if args.only:
        wanted = [x.strip() for x in args.only.split(',') if x.strip()]
        by = {s['name']: s for s in ALL_35}
        missing = [w for w in wanted if w not in by]
        if missing:
            print(f"Bilinmeyen senaryo: {missing}")
            sys.exit(1)
        res = run_scenarios([by[w] for w in wanted], args.n, args.depso_iter, args.jobs)
        Path("results").mkdir(exist_ok=True)
        with open(Path("results") / "only.json", 'w', encoding='utf-8') as f:
            json.dump({'n_instances': args.n, 'depso_iter': args.depso_iter,
                       'algorithms': ALGORITHMS, 'git_commit': _git_commit(),
                       'results': res}, f, indent=2)
        print_summary(res)
        sys.exit(0)

    if args.summary or args.batch is None:
        all_res = load_all_results()
        if all_res:
            print_summary(all_res)
        else:
            print("Henüz sonuç yok. Önce batch'leri çalıştırın:")
            for i, batch in enumerate(BATCHES, 1):
                names = [s['name'] for s in batch]
                print(f"  python run_batch.py --batch {i}  "
                      f"# {', '.join(names)}")
        sys.exit(0)

    if args.batch == 'all':
        batch_ids = list(range(1, 8))
    elif args.batch.isdigit() and 1 <= int(args.batch) <= 7:
        batch_ids = [int(args.batch)]
    else:
        print("--batch 1-7 arasında ya da 'all' olmalı!")
        sys.exit(1)

    scenarios = [s for i in batch_ids for s in BATCHES[i - 1]]
    print("=" * 60)
    print(f"BATCH {args.batch}: {len(scenarios)} senaryo × {args.n} örnek, "
          f"DEPSO {args.depso_iter} iter, {args.jobs} paralel işlem")
    print("=" * 60)

    t0 = time.perf_counter()
    results = run_scenarios(scenarios, args.n, args.depso_iter, args.jobs)
    by_name = {r['scenario']: r for r in results}

    meta = {
        'n_instances': args.n, 'depso_iter': args.depso_iter,
        'algorithms': ALGORITHMS, 'git_commit': _git_commit(),
        'config': {'DEPSO': config.DEPSO, 'RBRS_AE': config.RBRS_AE,
                   'ALNS': config.ALNS},
    }
    Path("results").mkdir(exist_ok=True)
    for i in batch_ids:
        names = [s['name'] for s in BATCHES[i - 1]]
        out = Path("results") / f"batch_{i}.json"
        with open(out, 'w', encoding='utf-8') as f:
            json.dump({'batch': i, 'scenarios': names, **meta,
                       'results': [by_name[n] for n in names]}, f, indent=2)
        print(f"  Kayıt: {out}")

    print(f"\n✓ Tamamlandı ({time.perf_counter() - t0:.0f}s)")
    print_summary(results)

    all_res = load_all_results()
    print(f"\nToplam kayıtlı senaryo: {len(all_res)}/35")
