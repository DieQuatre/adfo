"""
run_batch.py
=============
35 senaryoyu (Kübler Appendix H) koşturur: SOP, FCFS, DEPSO, RBRS-AE, ALNS.

Kullanım:
    python run_batch.py --batch 1              # senaryo 1-5
    python run_batch.py --batch all --jobs 8   # 35 senaryo, 8 paralel işlem
    python run_batch.py --summary              # kayıtlı sonuçların özeti

Yarıda kesilen koşum aynı komutla devam eder (results/checkpoints/).
--fresh her şeyi baştan koşar.

Her senaryo: data*/ havuzundan k siparişlik --n örnek; her örnekte tüm
algoritmalar AYNI siparişlerle koşar. Algoritma ayarları config.py'den gelir;
yalnızca DEPSO iterasyonu komut satırından değiştirilebilir (varsayılan: makale, 500).

Sonuç dosyası results/batch_<i>.json: ortalamalar + örnek bazında ham değerler
(istatistiksel testler ve web sitesi için) + kullanılan ayarlar ve kod sürümü.

Algoritma karşılaştırması için (docs/DENEY_PROTOKOLU.md):
    python run_batch.py --batch all --jobs 16 --seeds 5 --time-budget 60
    python compare_algorithms.py results/compare__s5__t60
--seeds N: her örnek her metasezgiselle N farklı tohumla çözülür.
--time-budget S: DEPSO, RBRS-AE ve ALNS örnek başına aynı süreyi (S sn) kullanır.
--time-per-order s: aynı, ama süre sipariş sayısıyla orantılı (k × s sn).
Varsayılan olmayan protokolün sonuçları results/compare<ek>/ klasörüne yazılır;
Kübler referans doğrulaması (results/batch_*.json) değişmez.
Commit'lenmemiş değişiklik varken koşum başlamaz (--allow-dirty ile yalnızca deneme).
"""

import sys
import json
import time
import random
import argparse
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.warehouse import Warehouse
from core.data_loader import DataLoader
from core import experiment as ex
from core.experiment import ALGORITHMS, Protocol
import config


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
    name, k, n, a, inst_id, proto = task
    seed = _instance_seed(inst_id, k)
    pool = load_pool(n, a)
    if len(pool) < k:
        raise RuntimeError(f"{DATA_DIR_MAP[(n, a)]}/ havuzu k={k} için yetersiz")
    shuffled = pool[:]
    random.Random(seed).shuffle(shuffled)
    orders = shuffled[:k]

    out = {'scenario': name, 'inst_id': inst_id, 'seed': seed}
    out.update(ex.solve_all(orders, _WH, seed, proto))
    return out


def make_algorithms(seed: int, depso_iter: int) -> dict:
    """Karşılaştırılan algoritmalar; ayarlar config.py'den (DEPSO iterasyonu hariç)."""
    return ex.make_algorithms(seed, depso_iter)


def solve_all(orders, warehouse, seed: int, depso_iter: int) -> dict:
    """Tek tohum, iterasyon sınırlı (eski arayüz)."""
    return ex.solve_all(orders, warehouse, seed, Protocol(depso_iter=depso_iter))


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
        if 'td_seeds' in inst_results[0].get(alg, {}):
            stats[alg]['td_seeds'] = [r[alg]['td_seeds'] for r in inst_results]
            stats[alg]['rt_seeds'] = [r[alg]['rt_seeds'] for r in inst_results]
    return {'scenario': name, 'k': k, 'n_maxol': n, 'a_maxol': a,
            'paper_vs_sop': paper, 'n_instances': len(inst_results),
            'seeds': [r['seed'] for r in inst_results],
            'order_source': 'data_pool', 'stats': stats}


CHECKPOINT_DIR = Path("results") / "checkpoints"


def _ckpt_path(task: tuple) -> Path:
    name, k, n, a, inst_id, proto = task
    return CHECKPOINT_DIR / f"{name}__i{inst_id}__d{proto.depso_iter}{proto.tag}.json"


def run_scenarios(scenarios: list[dict], n_instances: int, proto: Protocol,
                  jobs: int = 1, resume: bool = True) -> list[dict]:
    """
    Her (senaryo, örnek) bittiği anda results/checkpoints/ altına yazılır.
    Koşum yarıda kesilirse aynı komut tekrar çalıştırıldığında bitmiş
    örnekler atlanır (resume=True). Checkpoint, protokolü (DEPSO iterasyonu,
    tohum sayısı, süre bütçesi) adında taşır; farklı ayarla alınmış sonuç karışmaz.
    """
    tasks = [(s['name'], s['k'], s['n'], s['a'], i, proto)
             for s in scenarios for i in range(n_instances)]
    done: dict[str, list] = {s['name']: [] for s in scenarios}
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    todo = []
    for t in tasks:
        path = _ckpt_path(t)
        if resume and path.exists():
            done[t[0]].append(json.loads(path.read_text(encoding='utf-8')))
        else:
            todo.append(t)
    skipped = len(tasks) - len(todo)
    if skipped:
        print(f"  {skipped} örnek daha önce bitmiş (checkpoint), atlanıyor.")
    t0 = time.perf_counter()

    def _report(r):
        task = (r['scenario'], None, None, None, r['inst_id'], proto)
        _ckpt_path(task).write_text(json.dumps(r), encoding='utf-8')
        done[r['scenario']].append(r)
        parts = ' '.join(f"{alg}={r[alg]['td']:.0f}" for alg in ALGORITHMS)
        n_done = sum(len(v) for v in done.values())
        print(f"  [{n_done}/{len(tasks)} {time.perf_counter() - t0:6.0f}s] "
              f"{r['scenario']} #{r['inst_id'] + 1}: {parts}", flush=True)

    if jobs > 1 and todo:
        with Pool(jobs) as pool:
            for r in pool.imap_unordered(_run_instance, todo):
                _report(r)
    else:
        for t in todo:
            _report(_run_instance(t))

    return [_aggregate(s, done[s['name']]) for s in scenarios]


def _git_commit() -> str:
    return ex.git_state()['commit']


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


def load_all_results(results_dir: Path = Path("results")) -> list:
    """Tüm batch sonuçlarını birleştir."""
    all_results = []
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
    parser.add_argument("--fresh", action="store_true",
                        help="Checkpoint'leri yok say, her örneği baştan koş")
    parser.add_argument("--summary", action="store_true",
                        help="Tüm batch sonuçlarını özetler")
    parser.add_argument("--seeds", type=int, default=1,
                        help="Örnek başına metasezgisel tohum sayısı (varsayılan 1)")
    parser.add_argument("--time-budget", type=float, default=None,
                        help="DEPSO, RBRS-AE, ALNS için örnek başına eşit süre (sn)")
    parser.add_argument("--time-per-order", type=float, default=None,
                        help="Eşit süre bütçesi sipariş sayısıyla orantılı: k × bu değer (sn)")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="Commit'lenmemiş değişikliklerle koşmaya izin ver (yalnızca deneme)")
    args = parser.parse_args()
    proto = Protocol(depso_iter=args.depso_iter, n_seeds=args.seeds,
                     time_budget=args.time_budget, time_per_order=args.time_per_order)
    out_dir = Path("results") if proto.is_default else Path("results") / f"compare{proto.tag}"

    if args.only:
        wanted = [x.strip() for x in args.only.split(',') if x.strip()]
        by = {s['name']: s for s in ALL_35}
        missing = [w for w in wanted if w not in by]
        if missing:
            print(f"Bilinmeyen senaryo: {missing}")
            sys.exit(1)
        git = ex.require_clean(args.allow_dirty)
        res = run_scenarios([by[w] for w in wanted], args.n, proto, args.jobs,
                            resume=not args.fresh)
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "only.json", 'w', encoding='utf-8') as f:
            json.dump({'n_instances': args.n, 'depso_iter': args.depso_iter,
                       'protocol': proto.to_dict(), 'jobs': args.jobs,
                       'algorithms': ALGORITHMS, 'git_commit': git['commit'], 'git': git,
                       'results': res}, f, indent=2)
        print_summary(res)
        sys.exit(0)

    if args.summary or args.batch is None:
        all_res = load_all_results(out_dir)
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
    git = ex.require_clean(args.allow_dirty)
    print("=" * 60)
    print(f"BATCH {args.batch}: {len(scenarios)} senaryo × {args.n} örnek, "
          f"{proto.describe()}, {args.jobs} paralel işlem, kod {git['commit']}")
    print(f"Çıktı: {out_dir}/")
    print("=" * 60)

    t0 = time.perf_counter()
    results = run_scenarios(scenarios, args.n, proto, args.jobs,
                            resume=not args.fresh)
    by_name = {r['scenario']: r for r in results}

    meta = {
        'n_instances': args.n, 'depso_iter': args.depso_iter,
        'protocol': proto.to_dict(), 'jobs': args.jobs,
        'algorithms': ALGORITHMS, 'git_commit': git['commit'], 'git': git,
        'config': {'DEPSO': config.DEPSO, 'RBRS_AE': config.RBRS_AE,
                   'ALNS': config.ALNS},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in batch_ids:
        names = [s['name'] for s in BATCHES[i - 1]]
        out = out_dir / f"batch_{i}.json"
        with open(out, 'w', encoding='utf-8') as f:
            json.dump({'batch': i, 'scenarios': names, **meta,
                       'results': [by_name[n] for n in names]}, f, indent=2)
        print(f"  Kayıt: {out}")

    print(f"\n✓ Tamamlandı ({time.perf_counter() - t0:.0f}s)")
    print_summary(results)

    all_res = load_all_results(out_dir)
    print(f"\nToplam kayıtlı senaryo: {len(all_res)}/35")
    if not proto.is_default:
        print(f"Karşılaştırma raporu: python compare_algorithms.py {out_dir}")
