"""
tests/test_audit_regressions.py
================================
Denetimde bulunan üç hatanın geri gelmesini engelleyen testler:

1. DEPSO stagnation sayacı Gbest iyileştiğinde sıfırlanmıyordu
   (`convergence_history[-1]` kendisiyle karşılaştırılıyordu). Sonuç: Adım 13
   local search neredeyse her iterasyonda tetikleniyordu.

2. RBRS-AE `_insertion_costs` marjinal delta yerine birleşik rotanın TAMAMINI
   döndürüyordu (batch tabanı hep 0.0 kalıyordu). Sonuç: regret ataması
   kapasite alt sınırının 10 katı batch açıyordu.

3. `run_batch.generate_orders` sipariş sayısı `k`'yı almıyordu; havuz erken
   tükendiği için k=50/100/150/200 senaryoları AYNI listeyi alıp aynı deneyi
   4 kez raporluyordu.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from algorithms.base import Batch
from algorithms.depso import DEPSO
from algorithms.rbrs_ae import RBRS_AE
from config import ITEMS
from core.data_loader import DataLoader
from core.warehouse import Warehouse


@pytest.fixture(scope="module")
def wh():
    return Warehouse()


@pytest.fixture(scope="module")
def orders(wh):
    o = DataLoader().load_orders(1, 1, 20).orders[:50]
    wh.build_problem_matrix(o)
    return o


# ── 1. DEPSO stagnation ──────────────────────────────────────────────

def test_stagnation_resets_when_gbest_improves(orders, wh):
    """Gbest düştüğü iterasyonda sayaç 0 olmalı."""
    d = DEPSO(num_iterations=40, seed=42)
    d._orders, d._warehouse, d._K = orders, wh, len(orders)
    d.convergence_history = []
    d._initialize()

    saw_improvement = False
    for it in range(1, 41):
        d._current_iteration = it
        for p in range(d.num_particles):
            d._move_particle(p)
            d._evaluate_particle(p)
        d.convergence_history.append(d.gbest_distance)

        improved = d.gbest_distance < d._prev_gbest - 1e-12
        d._update_stagnation()
        if improved:
            saw_improvement = True
            assert d.s_stag_gbest == 0, (
                f"iter {it}: Gbest iyileşti ama stagnation {d.s_stag_gbest}"
            )

        d._mutate()
        d._local_search()
        d._prev_gbest = d.gbest_distance

    assert saw_improvement, "test anlamlı olsun diye en az bir iyileşme gerekli"


def test_stagnation_increments_when_gbest_flat(orders, wh):
    """Gbest değişmediğinde sayaç artmalı."""
    d = DEPSO(num_iterations=10, seed=1)
    d._orders, d._warehouse, d._K = orders, wh, len(orders)
    d.convergence_history = []
    d._initialize()

    before = d.s_stag_gbest
    d._prev_gbest = d.gbest_distance      # iyileşme yok
    d._update_stagnation()
    assert d.s_stag_gbest == before + 1


# ── 2. RBRS-AE marjinal insertion cost ───────────────────────────────

def test_insertion_cost_is_marginal_not_total(orders, wh):
    """Maliyet = rota(batch+order) - rota(batch), tamamı değil."""
    algo = RBRS_AE(seed=42)
    algo._wh, algo._route_cache = wh, {}

    batch = Batch(batch_id=0, orders=[orders[0]],
                  total_weight=orders[0].total_weight)
    base = algo._route_cost(batch.locations)[1]
    combined = algo._route_cost(batch.locations + orders[1].locations)[1]

    costs = {idx: c for c, idx in algo._insertion_costs(orders[1], [batch])}
    assert costs[0] == pytest.approx(combined - base)
    assert base > 0, "test anlamlı olsun diye batch rotası sıfırdan büyük olmalı"


def test_regret_assignment_respects_capacity_lower_bound(orders, wh):
    """
    Başlangıç ataması kapasite alt sınırına makul yakın olmalı.
    Hata varken 50 sipariş için 22 batch açılıyordu (alt sınır 2).
    """
    algo = RBRS_AE(seed=42)
    algo._wh, algo._route_cache = wh, {}

    total_weight = sum(o.total_weight for o in orders)
    lower_bound = -(-total_weight // ITEMS['picker_capacity_WU'])

    batches = algo._regret_assignment(orders, algo._priority_scores(orders))

    assert len(batches) >= lower_bound
    assert len(batches) <= lower_bound * 3, (
        f"{len(batches)} batch açıldı, alt sınır {lower_bound:.0f} — "
        "insertion cost tabanı yine bozulmuş olabilir"
    )
    # Hiçbir batch kapasiteyi aşmamalı, hiçbir sipariş kaybolmamalı
    assert all(b.total_weight <= ITEMS['picker_capacity_WU'] for b in batches)
    assert sum(len(b.orders) for b in batches) == len(orders)


# ── 3. Senaryo üretimi gerçekten k sipariş üretiyor mu ───────────────

@pytest.mark.parametrize("n_maxol,a_maxol", [(2, 6), (6, 2), (10, 10)])
def test_generate_orders_honours_target(n_maxol, a_maxol):
    from run_batch import generate_orders
    for k in (50, 200):
        inst = generate_orders(n_maxol, a_maxol, n_instances=1, target_orders=k)
        assert len(inst[0][0]) == k, (
            f"n_maxol={n_maxol} a_maxol={a_maxol} k={k}: "
            f"{len(inst[0][0])} sipariş üretildi"
        )


def test_different_k_produce_different_instances():
    """
    k=50 ve k=200 aynı deney OLMAMALI. (Hata varken havuz erken tükendiği
    için ikisi de aynı kısa listeyi alıyordu.)
    """
    from run_batch import generate_orders
    small = generate_orders(6, 2, n_instances=1, target_orders=50)[0][0]
    large = generate_orders(6, 2, n_instances=1, target_orders=200)[0][0]
    assert len(small) != len(large)
    assert sum(o.total_weight for o in large) > sum(o.total_weight for o in small)
