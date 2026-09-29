"""
run_dynamic.py
==============
Dinamik yer ataması deneyi (Kübler §6.4'ün karşılığı).

Her test döneminde aynı siparişler iki kez çözülür:
  statik:  ürünler başlangıçtaki yerlerinde kalır
  dinamik: önceki dönem sonlarında kabul edilen taşımalar uygulanmış
Dönem sonunda relocation (algorithms/relocation.py) dinamik çözümün
gruplarını kullanarak taşıma önerilerini dener.

Raporlanan (makaledeki gibi, statik mesafeye oranla):
  mesafe azalması %  = (statik − dinamik) / statik
  relocation eforu % = efor / statik
  net %              = azalma − efor

Kullanım:
  python run_dynamic.py --source kubler --scenario 1 --algo DEPSO --jobs 16
  python run_dynamic.py --source kubler-fig10 --scenario 1 --algo DEPSO --jobs 16
  python run_dynamic.py --source generated --size 5000 --blocks 2 --fill 0.7 \\
      --dynamics yuksek --algo RBRS-AE --jobs 16
  python run_dynamic.py --source kubler --scenario 1 --algo FIRSTFIT --subperiods 4   # hızlı deneme

Kaynaklar: kubler = data/ klasöründeki eski veri seti; kubler-fig10 = makalenin
§6.3 / Fig. 10 yöntemiyle yeniden üretilen veri (core/kubler_generator.py);
generated = kendi parametrik üreticimiz.

--subperiods N: her dönemin yalnızca ilk N alt dönemi çözülür (hızlı deneme).
Bu durumda relocation kazancı N/20 oranında eksik ölçülmesin diye Tdr ölçeklenir.
Sonuç: results/dynamic/<kaynak>_<algoritma>.json ve .md
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config
from algorithms.alns import ALNS
from algorithms.batching.first_fit import first_fit_batching
from algorithms.depso import DEPSO
from algorithms.rbrs_ae import RBRS_AE
from algorithms.relocation import DynamicRelocation
from algorithms.routing.route_cache import RouteCache
from core.dynamic_data import from_generated, from_kubler, from_kubler_fig10

OUT = Path("results") / "dynamic"
ALGOS = ('DEPSO', 'RBRS-AE', 'ALNS', 'FIRSTFIT')


def solve(algo: str, orders, wh, seed: int, depso_iter: int):
    """(toplam mesafe, gruplar). FIRSTFIT: hızlı deneme için first-fit + NN/2-opt."""
    if not orders:
        return 0.0, []
    if algo == 'FIRSTFIT':
        wh.build_problem_matrix(orders)
        rc = RouteCache(wh)
        groups = [b.orders for b in first_fit_batching(orders)]
        return sum(rc.distance(b_locs(g)) for g in groups), groups
    solver = {'DEPSO': lambda: DEPSO(num_iterations=depso_iter, seed=seed),
              'RBRS-AE': lambda: RBRS_AE(seed=seed),
              'ALNS': lambda: ALNS(seed=seed)}[algo]()
    sol = solver.solve(orders, wh)
    return sol.total_travel_distance, [b.orders for b in sol.batches]


def b_locs(group):
    return [l.location for o in group for l in o.orderlines]


_CTX = {}


def _init(problem_args):
    _CTX['problem'] = build_problem(problem_args)


def _solve_task(task):
    algo, orders, seed, depso_iter = task
    return solve(algo, orders, _CTX['problem'].warehouse, seed, depso_iter)


def build_problem(a: dict):
    if a['source'] == 'kubler':
        return from_kubler(a['scenario'])
    if a['source'] == 'kubler-fig10':
        return from_kubler_fig10(a['scenario'], a['seed'])
    from core.generator import InstanceSpec, generate
    return from_generated(generate(InstanceSpec(a['size'], a['blocks'], a['fill'],
                                                a['dynamics'], a['seed'])))


def run_experiment(problem, algo: str, depso_iter: int, used: int | None = None,
                   n_periods: int | None = None, jobs: int = 1, pargs: dict | None = None,
                   progress=None, tdr_eval: str = 'firstfit', eval_subs: int = 4,
                   eval_iter: int = 100) -> tuple[list[dict], dict]:
    """
    Dinamik deneyi koşar; (dönem satırları, özet) döndürür.
    progress(row) her dönem sonunda çağrılır (arayüz / terminal).
    jobs > 1 için pargs (build_problem argümanları) gerekir.
    tdr_eval: relocation kazancı (Tdr) hangi gruplarla ölçülür.
      'firstfit' (varsayılan): dönemin siparişleri lokasyona bakmayan first-fit
          ile gruplanır; taşımanın rota etkisi algoritmadan bağımsız ölçülür ve
          aynı veri için tüm algoritmalar aynı taşıma kararlarını alır.
      'algo': seçilen algoritmanın kendi grupları sabit tutulur (önceki
          davranış). Konuma göre gruplayan algoritmalarda (DEPSO, RBRS-AE,
          ALNS) kazancı olduğundan çok küçük ölçer; bkz. docs/RELOCATION.md.
      'full': makaledeki gibi her öneri için siparişler algoritmayla yeniden
          çözülür. Süre yüzünden dönemin ilk `eval_subs` alt dönemiyle ve
          DEPSO için `eval_iter` iterasyonla; her alt dönemde aynı tohum.
    """
    wh = problem.warehouse
    periods = problem.test_periods[:n_periods] if n_periods else problem.test_periods
    S = problem.subperiods
    used = min(used or S, S)
    reloc = DynamicRelocation(wh, problem.zones, problem.initial_locations,
                              problem.demand, problem.warmup)
    static_loc = problem.initial_locations.copy()

    pool = Pool(jobs, initializer=_init, initargs=(pargs,)) if jobs > 1 else None
    if pool is None:
        _CTX['problem'] = problem

    def solve_many(order_sets, seed0):
        tasks = [(algo, o, seed0 + k, depso_iter) for k, o in enumerate(order_sets)]
        return pool.map(_solve_task, tasks) if pool else [_solve_task(t) for t in tasks]

    rows = []
    try:
        for p in periods:
            subs = problem.orders_fn(p)[:used]
            static = solve_many([[_with_locs(o, static_loc) for o in sub] for sub in subs], 1000 * p)
            dynamic = solve_many([reloc.remap(sub) for sub in subs], 1000 * p)
            td_static = sum(d for d, _ in static)
            td_dynamic = sum(d for d, _ in dynamic)
            # dönem sonu relocation: dinamik çözümün grupları kullanılır
            if tdr_eval == 'full':
                ev = problem.orders_fn(p)[:eval_subs]

                def td_fn(moves, ev=ev, p=p):
                    loc = reloc.loc.copy()
                    for item, dst in moves.items():
                        loc[item] = dst
                    tasks = [(algo, [_with_locs(o, loc) for o in sub], 5000 * p + k, eval_iter)
                             for k, sub in enumerate(ev)]
                    out = pool.map(_solve_task, tasks) if pool else [_solve_task(t) for t in tasks]
                    return sum(d for d, _ in out)
                res = reloc.run_period(p, subs, tdr_scale=S / len(ev), td_fn=td_fn)
            else:
                if tdr_eval == 'algo':
                    eval_batches = [g for _, g in dynamic]
                else:
                    eval_batches = [solve('FIRSTFIT', reloc.remap(sub), wh, 0, 0)[1] for sub in subs]
                res = reloc.run_period(p, subs, batches=eval_batches, tdr_scale=S / used)
            effort = res.effort_LU * used / S
            row = {
                'period': p - problem.warmup + 1,
                'td_static': round(td_static, 1), 'td_dynamic': round(td_dynamic, 1),
                'reduction_pct': round(100 * (td_static - td_dynamic) / td_static, 3) if td_static else 0,
                'effort_LU': round(effort, 1),
                'effort_pct': round(100 * effort / td_static, 3) if td_static else 0,
                'candidates': res.candidates, 'tested': res.tested, 'accepted': res.accepted,
                'relocated_items': res.relocated_items,
                'moves': [[mv.item, mv.src, mv.dst, mv.src_class, mv.dst_class]
                          for s in res.suggestions if s.accepted for mv in s.moves],
                'scenarios': [s.scenario for s in res.suggestions if s.accepted],
            }
            row['net_pct'] = round(row['reduction_pct'] - row['effort_pct'], 3)
            rows.append(row)
            if progress:
                progress(row)
    finally:
        if pool:
            pool.close()

    tot_s = sum(r['td_static'] for r in rows)
    tot_d = sum(r['td_dynamic'] for r in rows)
    tot_e = sum(r['effort_LU'] for r in rows)
    summary = {'reduction_pct': round(100 * (tot_s - tot_d) / tot_s, 2) if tot_s else 0,
               'effort_pct': round(100 * tot_e / tot_s, 2) if tot_s else 0,
               'subperiods_used': used}
    summary['net_pct'] = round(summary['reduction_pct'] - summary['effort_pct'], 2)
    return rows, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', choices=['kubler', 'kubler-fig10', 'generated'], default='kubler')
    ap.add_argument('--scenario', type=int, default=1)
    ap.add_argument('--size', type=int, default=5000)
    ap.add_argument('--blocks', type=int, default=2)
    ap.add_argument('--fill', type=float, default=0.7)
    ap.add_argument('--dynamics', default=config.GENERATOR['default_dynamics'])
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--algo', choices=ALGOS, default='DEPSO')
    ap.add_argument('--depso-iter', type=int, default=config.DEPSO['num_iterations'])
    ap.add_argument('--subperiods', type=int, default=None)
    ap.add_argument('--periods', type=int, default=None, help="yalnızca ilk N test dönemi")
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--tdr-eval', choices=['firstfit', 'algo', 'full'], default='firstfit',
                    help="relocation kazancının nasıl ölçüleceği (bkz. run_experiment)")
    ap.add_argument('--eval-subperiods', type=int, default=4,
                    help="--tdr-eval full: öneri başına yeniden çözülen alt dönem sayısı")
    ap.add_argument('--eval-iter', type=int, default=100,
                    help="--tdr-eval full: yeniden çözümde DEPSO iterasyonu")
    args = ap.parse_args()

    pargs = {k: getattr(args, k) for k in ('source', 'scenario', 'size', 'blocks', 'fill',
                                           'dynamics', 'seed')}
    problem = build_problem(pargs)
    S = problem.subperiods
    used = min(args.subperiods or S, S)
    tag = (f"{problem.name}_{args.algo}" + (f"_sub{used}" if used < S else "")
           + {'firstfit': '', 'algo': '_tdralgo', 'full': '_tdrfull'}[args.tdr_eval])
    n_per = len(problem.test_periods[:args.periods] if args.periods else problem.test_periods)
    print(f"{problem.name}: {n_per} dönem × {used}/{S} alt dönem, algoritma {args.algo}, "
          f"{args.jobs} paralel işlem")
    t0 = time.perf_counter()

    def show(row):
        print(f"  dönem {row['period']}: statik {row['td_static']:9.0f}  dinamik {row['td_dynamic']:9.0f}  "
              f"azalma {row['reduction_pct']:6.2f}%  efor {row['effort_pct']:5.2f}%  "
              f"aday {row['candidates']:4d}  kabul {row['accepted']:3d}/{row['tested']:3d}  "
              f"[{time.perf_counter() - t0:5.0f}s]", flush=True)

    rows, summary = run_experiment(problem, args.algo, args.depso_iter, used, args.periods,
                                   args.jobs, pargs, progress=show, tdr_eval=args.tdr_eval,
                                   eval_subs=args.eval_subperiods, eval_iter=args.eval_iter)
    summary['tdr_eval'] = args.tdr_eval
    print(f"\nToplam: azalma {summary['reduction_pct']}%, efor {summary['effort_pct']}%, "
          f"net {summary['net_pct']}%")
    if args.source in ('kubler', 'kubler-fig10'):
        t = config.VALIDATION_TARGETS
        s = args.scenario
        print(f"Makale (senaryo {s}, DEPSO): azalma {t[f'scenario{s}_travel_distance_reduction_pct']}%, "
              f"efor {t[f'scenario{s}_relocation_effort_pct']}%, "
              f"net {t[f'scenario{s}_net_improvement_pct']}%")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{tag}.json").write_text(json.dumps({
        'problem': problem.name, 'algorithm': args.algo, 'subperiods_used': used,
        'depso_iter': args.depso_iter, 'config': config.DYNAMIC_STORAGE,
        'tdr_eval': args.tdr_eval,
        'eval': ({'subperiods': args.eval_subperiods, 'depso_iter': args.eval_iter}
                 if args.tdr_eval == 'full' else None),
        'summary': summary, 'periods': rows}, indent=1), encoding='utf-8')
    lines = [f"# Dinamik yer ataması — {problem.name}, {args.algo}", "",
             f"{len(rows)} dönem, dönem başına {used}/{S} alt dönem. "
             f"Taşıma kazancının ölçümü: {args.tdr_eval}"
             + (f" ({args.eval_subperiods} alt dönem, {args.eval_iter} iterasyon)"
                if args.tdr_eval == 'full' else "") + ".", "",
             "| dönem | statik LU | dinamik LU | azalma % | efor % | net % | kabul / test |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['period']} | {r['td_static']:.0f} | {r['td_dynamic']:.0f} | "
                     f"{r['reduction_pct']:.2f} | {r['effort_pct']:.2f} | {r['net_pct']:.2f} | "
                     f"{r['accepted']} / {r['tested']} |")
    lines += ["", f"**Toplam:** azalma {summary['reduction_pct']}%, efor {summary['effort_pct']}%, "
                  f"net {summary['net_pct']}%"]
    (OUT / f"{tag}.md").write_text("\n".join(lines), encoding='utf-8')
    print(f"Kayıt: {OUT / (tag + '.md')}")


def _with_locs(order, loc):
    from core.data_loader import Order, OrderLine
    return Order(order_id=order.order_id, num_orderlines=order.num_orderlines,
                 total_weight=order.total_weight,
                 orderlines=[OrderLine(item=l.item, quantity=l.quantity,
                                       location=int(loc[l.item]), weight=l.weight)
                             for l in order.orderlines])


if __name__ == '__main__':
    main()
