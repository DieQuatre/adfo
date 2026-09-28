"""
validate_relocation.py
======================
Relocation'daki yaklaşımın (gruplar sabit, yalnızca etkilenen rotalar yeniden)
makaledeki tam yöntemden (her öneri için dönemi baştan çözmek) ne kadar
saptığını ölçer. Sonuç: results/dynamic/validation_<algo>.md

    python validate_relocation.py --algo RBRS-AE --subs 2 --orders 80 --n 15
"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from algorithms.relocation import DynamicRelocation, validate_approximation
from core.dynamic_data import from_kubler
from run_dynamic import solve


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--algo', default='RBRS-AE')
    ap.add_argument('--scenario', type=int, default=1)
    ap.add_argument('--subs', type=int, default=2, help='kullanılan alt dönem sayısı')
    ap.add_argument('--orders', type=int, default=80, help='alt dönem başına sipariş')
    ap.add_argument('--n', type=int, default=15, help='denenecek öneri sayısı')
    ap.add_argument('--depso-iter', type=int, default=200)
    args = ap.parse_args()

    P = from_kubler(args.scenario)
    wh = P.warehouse
    R = DynamicRelocation(wh, P.zones, P.initial_locations, P.demand, P.warmup,
                          cfg={'max_relocation_suggestions': args.n})
    fn = lambda orders, w: solve(args.algo, orders, w, 7, args.depso_iter)

    # Aday listesinin oluşması için iki dönem ilerle (o = 2); üçüncü dönemde
    # öneriler tüm dönemin siparişleriyle üretilir (hızlı gruplama ile).
    rows = []
    for p in P.test_periods[:3]:
        full = P.orders_fn(p)
        snapshot = (R.loc.copy(), {k: set(v) for k, v in R.empty.items()},
                    dict(R.item_at), R.wrong_count.copy())
        res = R.run_period(p, full, batch_fn=lambda o, w: solve('FIRSTFIT', o, w, 0, 0)[1])
        if p != P.test_periods[2]:
            continue
        R.loc, R.empty, R.item_at, R.wrong_count = snapshot
        sugs = [s for s in res.suggestions if s.moves]
        moved = {mv.item for s in sugs for mv in s.moves}
        # Karşılaştırma siparişleri: taşınan ürünleri içeren siparişler + rastgele dolgu
        pool = [o for sub in full for o in sub]
        hit = [o for o in pool if moved & set(o.items)]
        rest = [o for o in pool if not (moved & set(o.items))]
        rng = np.random.default_rng(0)
        need = max(0, args.subs * args.orders - len(hit))
        fill = [rest[i] for i in rng.choice(len(rest), size=min(need, len(rest)), replace=False)]
        chosen = hit + fill
        rng.shuffle(chosen)
        subs = [chosen[k::args.subs] for k in range(args.subs)]
        rows = validate_approximation(R, subs, fn, sugs)

    if not rows:
        print("Karşılaştırılacak öneri çıkmadı.")
        return

    a = np.array([r['tdr_approx'] for r in rows])
    f = np.array([r['tdr_full'] for r in rows])
    same_sign = np.mean(np.sign(a) == np.sign(f))
    lines = [f"# Relocation yaklaşımının doğrulanması — {args.algo}", "",
             f"Kübler senaryo {args.scenario}, test dönemi 3. Öneriler tüm dönemle üretildi; karşılaştırma, "
             f"taşınan ürünleri içeren siparişler + rastgele dolgu ile {args.subs} alt dönem × ~{args.orders} "
             f"sipariş üzerinde yapıldı. {len(rows)} öneri.", "",
             "| öneri | senaryo | Tdr yaklaşık | Tdr tam | fark |", "|---|---|---|---|---|"]
    for k, r in enumerate(rows, 1):
        lines.append(f"| {k} | {r['scenario']} | {r['tdr_approx']:.1f} | {r['tdr_full']:.1f} | "
                     f"{r['tdr_full'] - r['tdr_approx']:+.1f} |")
    lines += ["", f"- Ortalama mutlak fark: {np.mean(np.abs(f - a)):.1f} LU",
              f"- Aynı işaret (ikisi de kazanç ya da ikisi de kayıp): %{100 * same_sign:.0f}",
              f"- Ortalama Tdr: yaklaşık {a.mean():.1f}, tam {f.mean():.1f}", "",
              "Tam yöntemde algoritma her öneri için dönemi baştan çözdüğü için, taşımanın etkisine "
              "algoritmanın farklı bir gruplama bulmasından gelen dalgalanma da karışır."]
    out = Path("results") / "dynamic"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"validation_{args.algo}.md").write_text("\n".join(lines), encoding='utf-8')
    print("\n".join(lines))


if __name__ == '__main__':
    main()
