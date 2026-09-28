"""
run_batch.py
=============
5'er 5'er senaryo üret ve koştur.

Kullanım:
    python run_batch.py --batch 1   # senaryo 1-5
    python run_batch.py --batch 2   # senaryo 6-10
    ...
    python run_batch.py --batch 7   # senaryo 31-35

Her batch: data*/ havuzundan örnekleme + 5 instance × 4 algoritma koşumu
Süre tahmini: ~3-5 dakika/batch (bu ortamda), ~30-60 dk (kendi makinende 40 inst)
"""

import sys
import json
import time
import random
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.warehouse import Warehouse
from core.data_loader import DataLoader
from benchmarks.sop import SOP
from benchmarks.fcfs import FCFS
from algorithms.depso import DEPSO
from algorithms.rbrs_ae import RBRS_AE


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

def run_one_scenario(scenario: dict, n_instances: int,
                     depso_iter: int, wh: Warehouse) -> dict:
    k      = scenario['k']
    n      = scenario['n']
    a      = scenario['a']
    name   = scenario['name']
    paper  = PAPER.get(name, '?')

    print(f"\n  [{name}]  K={k}, N_maxol={n}, A_maxol={a}  "
          f"(paper DEPSO vs SOP: {paper}%)")

    # Sipariş kaynağı: yalnızca Kübler veri seti (yedek yol yok).
    instances = sample_instances(n, a, k, n_instances)
    source = 'data_pool'

    print(f"    kaynak: {source}, {len(instances)} instance")

    results = {alg: {'td': [], 'rt': []}
               for alg in ['SOP', 'FCFS', 'DEPSO', 'RBRS-AE']}

    for inst_id, (all_orders, inst_seed) in enumerate(instances):
        orders = all_orders[:k]
        if len(orders) < 5:
            continue

        algos = [
            ('SOP',     SOP()),
            ('FCFS',    FCFS()),
            ('DEPSO',   DEPSO(num_iterations=depso_iter,
                              num_particles=5, seed=inst_seed)),
            ('RBRS-AE', RBRS_AE(seed=inst_seed)),   # ayarlar config.RBRS_AE
        ]

        line_parts = []
        for alg_name, algo in algos:
            sol = algo.solve(orders, wh)
            results[alg_name]['td'].append(sol.total_travel_distance)
            results[alg_name]['rt'].append(sol.runtime_seconds)
            line_parts.append(f"{alg_name}={sol.total_travel_distance:.0f}")

        print(f"    inst {inst_id+1}: {' '.join(line_parts)}")

    # İstatistik
    sop_tds  = results['SOP']['td']
    fcfs_tds = results['FCFS']['td']
    stats = {}
    for alg in ['SOP', 'FCFS', 'DEPSO', 'RBRS-AE']:
        tds = results[alg]['td']
        rts = results[alg]['rt']
        if not tds:
            continue
        vs_sop  = [((t-s)/s*100) for t,s in zip(tds, sop_tds) if s > 0]
        vs_fcfs = [((t-f)/f*100) for t,f in zip(tds, fcfs_tds) if f > 0]
        stats[alg] = {
            'mean_td':      round(_mean(tds), 1),
            'mean_rt':      round(_mean(rts), 2),
            'vs_sop_mean':  round(_mean(vs_sop), 2),
            'vs_fcfs_mean': round(_mean(vs_fcfs), 2),
        }

    depso_vs_sop  = stats.get('DEPSO', {}).get('vs_sop_mean', 0)
    rbrs_vs_sop   = stats.get('RBRS-AE', {}).get('vs_sop_mean', 0)
    diff          = round(depso_vs_sop - paper, 2) if isinstance(paper, float) else '?'
    ok            = "✅" if isinstance(diff, float) and abs(diff) < 5 else "⚠️"

    print(f"    → DEPSO vs SOP: {depso_vs_sop:.2f}%  "
          f"(paper: {paper}%  fark: {diff}%  {ok})")
    print(f"    → RBRS-AE vs SOP: {rbrs_vs_sop:.2f}%")

    return {'scenario': name, 'k': k, 'n_maxol': n, 'a_maxol': a,
            'paper_vs_sop': paper, 'n_instances': len(instances),
            'order_source': source, 'stats': stats}


# ════════════════════════════════════════════════════════════════════════════
# RAPOR
# ════════════════════════════════════════════════════════════════════════════

def print_summary(results: list):
    print("\n" + "="*72)
    print("ÖZET TABLO — Paper Appendix H vs Bizim Sonuçlarımız")
    print("="*72)
    print(f"{'Senaryo':<12} {'DEPSO/SOP':>10} {'Paper':>10} {'Fark':>8} "
          f"{'RBRS/SOP':>10} {'Durum':>6}")
    print("-"*72)

    for r in results:
        if 'stats' not in r or 'DEPSO' not in r.get('stats', {}):
            print(f"{r['scenario']:<12} {'HATA':>10}")
            continue
        depso = r['stats']['DEPSO']['vs_sop_mean']
        rbrs  = r['stats']['RBRS-AE']['vs_sop_mean']
        paper = r['paper_vs_sop']
        diff  = round(depso - paper, 2) if isinstance(paper, float) else 0
        ok    = "✅" if abs(diff) < 8 else "⚠️"
        print(f"{r['scenario']:<12} {depso:>10.2f}% {paper:>10.2f}% "
              f"{diff:>+8.2f}% {rbrs:>10.2f}%  {ok}")

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
    parser.add_argument("--batch", type=int, required=False,
                        help="Hangi batch? (1-7). Belirtilmezse özet gösterir.")
    parser.add_argument("--n", type=int, default=5,
                        help="Instance sayısı (default: 5)")
    parser.add_argument("--depso-iter", type=int, default=100,
                        help="DEPSO iterasyon (default: 100)")
    parser.add_argument("--summary", action="store_true",
                        help="Tüm batch sonuçlarını özetler")
    args = parser.parse_args()

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

    batch_idx = args.batch
    if batch_idx < 1 or batch_idx > 7:
        print("Batch 1-7 arasında olmalı!")
        sys.exit(1)

    batch = BATCHES[batch_idx - 1]
    names = [s['name'] for s in batch]

    print(f"{'='*60}")
    print(f"BATCH {batch_idx}/7: {', '.join(names)}")
    print(f"Instance: {args.n}, DEPSO iter: {args.depso_iter}")
    print(f"{'='*60}")

    wh = Warehouse()
    t0 = time.perf_counter()

    batch_results = []
    for scenario in batch:
        result = run_one_scenario(scenario, args.n, args.depso_iter, wh)
        batch_results.append(result)

    # Kaydet
    Path("results").mkdir(exist_ok=True)
    out = Path("results") / f"batch_{batch_idx}.json"
    with open(out, 'w') as f:
        json.dump({'batch': batch_idx, 'scenarios': names,
                   'n_instances': args.n, 'depso_iter': args.depso_iter,
                   'results': batch_results}, f, indent=2)

    elapsed = time.perf_counter() - t0
    print(f"\n✓ Batch {batch_idx} tamamlandı ({elapsed:.0f}s)")
    print(f"  Kayıt: {out}")

    # Özet
    print_summary(batch_results)

    # Tüm batch'ler bitti mi?
    all_res = load_all_results()
    print(f"\nToplam tamamlanan senaryo: {len(all_res)}/35")
    if len(all_res) == 35:
        print("\n🎉 35 senaryo TAMAMLANDI! Tam özet:")
        print_summary(all_res)
