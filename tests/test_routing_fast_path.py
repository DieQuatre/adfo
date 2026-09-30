"""
Hızlı rota yolu (alt-matris) eski dist_m tabanlı yolla BİREBİR aynı sonucu
vermeli: aynı rota sırası, aynı mesafe. Aksi hâlde hızlandırma sonuçları
değiştirmiş olur.
"""

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from algorithms.routing.nearest_neighbor import nearest_neighbor_route
from algorithms.routing.two_opt import two_opt_improve, _two_opt_slow
from core.data_loader import DataLoader
from core.warehouse import Warehouse


def _nn_reference(locations, wh):
    start = wh.DEPOT
    unique_locs = list(set(locations))
    remaining = set(unique_locs)
    route, current, total = [start], start, 0.0
    while remaining:
        nearest = min(remaining, key=lambda loc: wh.dist_m(current, loc))
        total += wh.dist_m(current, nearest)
        route.append(nearest)
        remaining.discard(nearest)
        current = nearest
    total += wh.dist_m(current, start)
    route.append(start)
    return route, total


@pytest.fixture(scope="module")
def setup():
    wh = Warehouse()
    orders = DataLoader().load_orders(1, 1, 1).orders[:400]
    wh.build_problem_matrix(orders)
    locs = sorted({l for o in orders for l in o.locations})
    return wh, locs


@pytest.mark.parametrize("size", [3, 8, 25, 60, 150])
def test_fast_path_identical_to_reference(setup, size):
    wh, locs = setup
    rng = random.Random(size)
    for _ in range(15):
        sample = rng.sample(locs, min(size, len(locs)))
        r_fast, d_fast = nearest_neighbor_route(sample, wh)
        r_ref, d_ref = _nn_reference(sample, wh)
        assert r_fast == r_ref and d_fast == d_ref

        o_fast = two_opt_improve(r_fast, wh)
        o_ref = _two_opt_slow(r_ref, wh, 30, 2)
        assert o_fast[0] == o_ref[0] and o_fast[1] == o_ref[1]


# ── Derlenmiş (numba) yol ─────────────────────────────────────────────

@pytest.fixture(scope="module")
def orders400():
    wh = Warehouse()
    orders = DataLoader().load_orders(1, 1, 1).orders[:400]
    return wh, orders


def test_compiled_route_identical_to_python(orders400):
    """fast.route, Python NN + 2-opt ile birebir aynı rota ve mesafeyi vermeli."""
    from algorithms.routing import fast
    if not fast.AVAILABLE:
        pytest.skip("numba kurulu değil")
    wh, orders = orders400
    wh.build_problem_matrix(orders)
    locs = [l.location for o in orders for l in o.orderlines]
    rng = random.Random(11)
    for _ in range(1500):
        k = rng.choice([1, 2, 3, 4, 5, 9, 20, 45, 90])
        key = frozenset(rng.sample(locs, min(k, len(locs))))
        r1, _ = nearest_neighbor_route(list(key), wh)
        r1, d1 = two_opt_improve(r1, wh)
        r2, d2 = fast.route(list(key), wh)
        assert r1 == r2 and d1 == d2


def test_algorithms_identical_with_and_without_compiled_routes(orders400, monkeypatch):
    from algorithms.routing import fast
    if not fast.AVAILABLE:
        pytest.skip("numba kurulu değil")
    from core.experiment import make_algorithms
    wh, orders = orders400[0], orders400[1][:40]
    with_fast = {n: a.solve(orders, wh).total_travel_distance
                 for n, a in make_algorithms(5, 30).items()}
    monkeypatch.setattr(fast, 'AVAILABLE', False)
    without = {n: a.solve(orders, wh).total_travel_distance
               for n, a in make_algorithms(5, 30).items()}
    assert with_fast == without


def test_route_cache_limit_does_not_change_results(orders400):
    """Önbellek sınırı yalnızca belleği etkiler: rota kümeye bağlı (sıralı liste)."""
    from algorithms.routing.route_cache import RouteCache
    from core.experiment import make_algorithms
    wh, orders = orders400[0], orders400[1][:60]
    base = {n: a.solve(orders, wh).total_travel_distance for n, a in make_algorithms(7, 40).items()}
    old = RouteCache.__init__.__defaults__
    try:
        RouteCache.__init__.__defaults__ = (50,)          # neredeyse her çağrıda boşalt
        tiny = {n: a.solve(orders, wh).total_travel_distance for n, a in make_algorithms(7, 40).items()}
    finally:
        RouteCache.__init__.__defaults__ = old
    assert tiny == base


def test_route_depends_only_on_set(orders400):
    from algorithms.routing.route_cache import RouteCache
    wh, orders = orders400
    wh.build_problem_matrix(orders)
    locs = sorted({l.location for o in orders for l in o.orderlines})[:40]
    a = RouteCache(wh).get(locs)
    b = RouteCache(wh).get(list(reversed(locs)) + locs[:5])
    assert a == b
