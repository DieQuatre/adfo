"""
generate_instances.py
=====================
Parametrik üreticiyle deney ızgarasındaki depoları üretir ve özetler.

    python generate_instances.py                   # ızgara, tohum 0, 'orta' dinamiklik
    python generate_instances.py --save            # instances/ altına meta, ürün, talep
    python generate_instances.py --save --orders   # + ilk test döneminin siparişleri
    python generate_instances.py --dynamics yuksek --seed 1

Örnekler (spec + tohum) her zaman aynı veriyi üretir; instances/ klasörü
git'e eklenmez, istenince yeniden üretilir. Özet: instances/index.csv.
"""

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import GENERATOR as GEN
from core.generator import generate, grid

COLUMNS = ['name', 'size', 'blocks', 'fill', 'dynamics', 'seed', 'total_locations',
           'num_items', 'orders_first_test_period', 'top20_share_expected',
           'structural_class_change_test_horizon', 'observed_class_change_per_period']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--dynamics', default=GEN['default_dynamics'],
                    choices=sorted(GEN['dynamics']))
    ap.add_argument('--save', action='store_true')
    ap.add_argument('--orders', action='store_true')
    ap.add_argument('--out', default='instances')
    args = ap.parse_args()

    specs = grid(args.seed, args.dynamics)
    out = Path(args.out)
    rows = []
    t0 = time.perf_counter()
    for spec in specs:
        inst = generate(spec)
        n_orders = sum(len(s) for s in inst.period_orders(inst.first_test_period))
        st = inst.stats
        rows.append({'name': spec.name, 'size': spec.size, 'blocks': spec.blocks,
                     'fill': spec.fill, 'dynamics': spec.dynamics, 'seed': spec.seed,
                     'total_locations': st['total_locations'], 'num_items': st['num_items'],
                     'orders_first_test_period': n_orders,
                     'top20_share_expected': st['top20_share_expected'],
                     'structural_class_change_test_horizon': st['structural_class_change_test_horizon'],
                     'observed_class_change_per_period': st['observed_class_change_per_period']})
        if args.save:
            inst.save(out, with_orders=args.orders)
        print(f"  {spec.name:28s} lok={st['total_locations']:6d} ürün={st['num_items']:6d} "
              f"sipariş={n_orders:6d} yapısal değişim={st['structural_class_change_test_horizon']:.3f}")

    out.mkdir(exist_ok=True)
    with open(out / 'index.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"\n{len(rows)} depo, {time.perf_counter() - t0:.1f}s. Özet: {out / 'index.csv'}")


if __name__ == '__main__':
    main()
