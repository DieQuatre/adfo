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
