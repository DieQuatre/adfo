"""
tests/test_solution_integrity.py
================================
Her algoritmanın döndürdüğü çözüm kendi içinde tutarlı olmalı:

- her sipariş tam bir kez gruplanmış,
- hiçbir grup kapasiteyi aşmıyor,
- her grubun rotası depodan başlayıp depoda bitiyor ve grubun TÜM
  lokasyonlarını (ve yalnızca onları) ziyaret ediyor,
- rotanın mesafesi yeniden hesaplanınca grubun travel_distance değerine eşit,
- grup mesafelerinin toplamı total_travel_distance'a eşit.

2026-09-28 denetiminde RBRS-AE'nin final yerel aramasından sonra rotaların
eski kaldığı (K3) ve DEPSO yerel aramasının farklı bir ölçü kullandığı (O2)
bulundu; bu testler ikisini de yakalar.
"""

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from algorithms.base import compute_route_distance
from algorithms.depso import DEPSO
from algorithms.rbrs_ae import RBRS_AE
from algorithms.routing.route_cache import RouteCache
from config import ITEMS, RBRS_AE as RBRS_CFG
from core.data_loader import DataLoader
from core.warehouse import Warehouse


@pytest.fixture(scope="module")
def wh():
    return Warehouse()


@pytest.fixture(scope="module")
def pool():
    loader = DataLoader()
    orders = []
    for sub in range(1, 21):
        orders.extend(loader.load_orders(1, 1, sub).orders)
    return orders


def _sample(pool, k, seed):
    orders = pool[:]
    random.Random(seed).shuffle(orders)
    return orders[:k]


def assert_consistent(sol, orders, wh):
    ids = sorted(id(o) for b in sol.batches for o in b.orders)
    assert ids == sorted(id(o) for o in orders), "sipariş eksik ya da tekrar"

    cap = ITEMS['picker_capacity_WU']
    for b in sol.batches:
        assert b.total_weight <= cap + 1e-9, f"kapasite aşıldı: {b.total_weight}"
        assert b.route[0] == wh.DEPOT and b.route[-1] == wh.DEPOT
        visited = set(b.route) - {wh.DEPOT}
        assert visited == set(b.locations), "rota grubun lokasyonlarıyla uyuşmuyor"
        assert compute_route_distance(b.route, wh) == pytest.approx(
            b.travel_distance, abs=1e-6), "rota mesafesi travel_distance'a eşit değil"

    assert sum(b.travel_distance for b in sol.batches) == pytest.approx(
        sol.total_travel_distance, abs=1e-6)


@pytest.mark.parametrize("seed", [2, 4])
def test_rbrs_ae_routes_fresh_after_final_local_search(wh, pool, seed):
    """Bu tohumlarla, eski kodda final yerel arama sonrası rotalar eski kalıyordu."""
    orders = _sample(pool, 60, seed)
    sol = RBRS_AE(max_iterations=1, max_no_improvement=1,
                  shift_attempts=1, swap_attempts=1, seed=seed).solve(orders, wh)
    assert_consistent(sol, orders, wh)


def test_rbrs_ae_default_run_consistent(wh, pool):
    orders = _sample(pool, 50, 11)
    sol = RBRS_AE(max_iterations=10, seed=11).solve(orders, wh)
    assert_consistent(sol, orders, wh)


@pytest.mark.parametrize("seed", [1, 7])
def test_depso_consistent_including_local_search(wh, pool, seed):
    """max_stagnation_bound=0 → yerel arama neredeyse her iterasyonda çalışır."""
    orders = _sample(pool, 40, seed)
    sol = DEPSO(num_iterations=30, max_stagnation_bound=0, seed=seed).solve(orders, wh)
    assert_consistent(sol, orders, wh)
    # Her grup, ana döngüyle aynı ölçüyle (NN + 2-opt) değerlendirilmiş olmalı.
    ref = RouteCache(wh)
    for b in sol.batches:
        assert b.travel_distance == pytest.approx(ref.distance(b.locations), abs=1e-6)


def test_route_cache_returns_independent_copies(wh):
    cache = RouteCache(wh)
    r1, d1 = cache.get([100, 1500, 3700])
    r1.append(999)
    r2, d2 = cache.get([3700, 100, 1500, 100])   # sıra ve tekrar önemsiz
    assert 999 not in r2 and d1 == d2
    assert cache.hits == 1 and cache.misses == 1


def test_rbrs_ae_defaults_come_from_config():
    algo = RBRS_AE()
    assert algo.max_iterations == RBRS_CFG['max_iterations'] == 100
    assert algo.max_no_improvement == RBRS_CFG['max_no_improvement'] == 15
    assert algo.shift_attempts == RBRS_CFG['shift_attempts']
    assert algo.swap_attempts == RBRS_CFG['swap_attempts']


def test_zero_is_a_valid_override():
    """`x or config` kalıbı 0 değerini yutuyordu."""
    assert RBRS_AE(swap_attempts=0).swap_attempts == 0
    assert DEPSO(max_stagnation_bound=0).max_stag == 0


def test_run_batch_does_not_override_rbrs_settings():
    src = (Path(__file__).parent.parent / "core" / "experiment.py").read_text(encoding="utf-8")
    call = src[src.index("RBRS_AE("):src.index(")", src.index("RBRS_AE("))]
    for key in ("max_iterations", "max_no_improvement", "shift_attempts", "swap_attempts"):
        assert key not in call, f"core/experiment.py RBRS-AE ayarını ({key}) eziyor"


# ── ALNS ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", [3, 8])
def test_alns_consistent(wh, pool, seed):
    from algorithms.alns import ALNS
    orders = _sample(pool, 40, seed)
    sol = ALNS(max_iterations=60, seed=seed).solve(orders, wh)
    assert_consistent(sol, orders, wh)
    ref = RouteCache(wh)
    for b in sol.batches:
        assert b.travel_distance == pytest.approx(ref.distance(b.locations), abs=1e-6)
