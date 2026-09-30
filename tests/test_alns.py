"""
ALNS birim testleri — docs/ALNS_formulasyon.md denklemleriyle eşleşme.
"""

import math
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from algorithms.alns import ALNS, DESTROY_OPS, REPAIR_OPS, _State
from algorithms.routing.route_cache import RouteCache
from config import ALNS as CFG
from core.data_loader import DataLoader
from core.warehouse import Warehouse


@pytest.fixture(scope="module")
def ctx():
    wh = Warehouse()
    orders = DataLoader().load_orders(1, 1, 20).orders[:30]
    wh.build_problem_matrix(orders)
    a = ALNS(seed=1)
    a._wh, a._routes, a._orders = wh, RouteCache(wh), orders
    a._locs = [list(o.locations) for o in orders]
    a._w = [o.total_weight for o in orders]
    return a, orders


def test_weight_update_formula():
    """(13): w ← (1 − r)·w + r·(π/n); kullanılmayan operatör değişmez."""
    a = ALNS(seed=0)
    w = {'x': 2.0, 'y': 1.0}
    a._update_weights(w, {'x': 66.0, 'y': 0.0}, {'x': 3, 'y': 0})
    r = CFG['reaction']
    assert w['x'] == pytest.approx((1 - r) * 2.0 + r * 22.0)
    assert w['y'] == 1.0


def test_roulette_proportional():
    """(11): seçim olasılığı ağırlıkla orantılı."""
    a = ALNS(seed=0)
    w = {'a': 3.0, 'b': 1.0}
    picks = [a._roulette(w) for _ in range(8000)]
    assert picks.count('a') / len(picks) == pytest.approx(0.75, abs=0.03)


def test_biased_index_range_and_bias():
    """(6): indeks her zaman geçerli; p büyüdükçe baş tarafa yığılır."""
    a = ALNS(seed=0)
    idx = [a._biased_index(10, 6.0) for _ in range(2000)]
    assert min(idx) >= 0 and max(idx) <= 9
    assert sum(i == 0 for i in idx) > 0.5 * len(idx)


def test_initial_temperature_formula(ctx):
    """(16): T0 ile w0 kadar kötü bir çözüm %50 olasılıkla kabul edilir."""
    f0 = 1000.0
    T0 = -(CFG['init_worse_pct'] * f0) / math.log(0.5)
    assert math.exp(-(CFG['init_worse_pct'] * f0) / T0) == pytest.approx(0.5)


def test_insertion_cost_is_marginal(ctx):
    """(8): Δ(o, B) = TD(B ∪ {o}) − TD(B); Δ(o, ∅) = TD({o})."""
    a, orders = ctx
    st = a._repair_regret2(_State([], [], []), [0, 1, 2])
    opts = dict((k, c) for c, k in a._insertion_options(st, 5))
    assert opts[-1] == pytest.approx(a._td([5]))
    for k, b in enumerate(st.batches):
        if k in opts:
            assert opts[k] == pytest.approx(a._td(b + [5]) - a._td(b))


@pytest.mark.parametrize("op", DESTROY_OPS)
def test_destroy_removes_exactly_q(ctx, op):
    a, orders = ctx
    st = a._repair_regret2(_State([], [], []), list(range(len(orders))))
    part, removed = a._destroy(op, st.copy(), 7)
    assert len(removed) == len(set(removed)) == 7
    left = [i for b in part.batches for i in b]
    assert sorted(left + removed) == list(range(len(orders)))
    assert all(b for b in part.batches), "boş grup kalmamalı"


@pytest.mark.parametrize("op", REPAIR_OPS)
def test_repair_respects_capacity(ctx, op):
    a, orders = ctx
    st = a._repair(op, _State([], [], []), list(range(len(orders))))
    assert sorted(i for b in st.batches for i in b) == list(range(len(orders)))
    assert all(w <= a.capacity + 1e-9 for w in st.weights)


def test_related_removal_prefers_nearby_orders(ctx):
    """(7): Shaw kaldırma, rastgele kaldırmaya göre birbirine yakın siparişler seçmeli."""
    a, orders = ctx
    st = a._repair_regret2(_State([], [], []), list(range(len(orders))))
    dist = a._wh.dist_m

    def spread(ids):
        locs = [l for i in ids for l in a._locs[i]]
        return sum(dist(x, y) for x in locs for y in locs) / (len(locs) ** 2)

    rel, rnd = [], []
    for s in range(20):
        a._rng = random.Random(s)
        rel.append(spread(a._destroy('related', st.copy(), 5)[1]))
        rnd.append(spread(a._destroy('random', st.copy(), 5)[1]))
    assert sum(rel) < sum(rnd)


def test_deterministic_with_seed():
    wh = Warehouse()
    orders = DataLoader().load_orders(1, 1, 20).orders[:25]
    s1 = ALNS(max_iterations=40, seed=5).solve(orders, wh)
    s2 = ALNS(max_iterations=40, seed=5).solve(orders, wh)
    assert s1.total_travel_distance == s2.total_travel_distance
    assert s1.convergence_history == s2.convergence_history


def test_best_never_worsens():
    wh = Warehouse()
    orders = DataLoader().load_orders(1, 1, 20).orders[:25]
    sol = ALNS(max_iterations=80, seed=2).solve(orders, wh)
    h = sol.convergence_history
    assert all(h[i + 1] <= h[i] + 1e-9 for i in range(len(h) - 1))
    assert sol.total_travel_distance == pytest.approx(h[-1])


def test_unknown_override_rejected():
    with pytest.raises(TypeError):
        ALNS(sigma9=1)


def test_large_instance_destroy_size_bounds():
    """n > 600'de %5 alt sınırı 30'luk üst sınırı aşıyordu (randint hatası)."""
    from core.generator import InstanceSpec, generate
    inst = generate(InstanceSpec(20000, 2, 0.7, 'orta', 0))
    orders = [o for sub in inst.period_orders(12) for o in sub][:650]
    sol = ALNS(seed=1, max_iterations=3).solve(orders, inst.warehouse)
    assert sorted(o.order_id for b in sol.batches for o in b.orders) == sorted(o.order_id for o in orders)
