"""
Parametrik depo düzeni (Warehouse(layout)).

- Varsayılan düzen Kübler düzeniyle aynı kalmalı (ayrıca bkz. test_distance).
- 1, 2 ve 3 bloklu (geçişsiz, tek geçişli, iki geçişli) depolarda mesafe
  geometrisi doğru olmalı.
- Tüm algoritmalar ve S-shape, Kübler dışı düzenlerde tutarlı çözüm üretmeli.
"""

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from algorithms.alns import ALNS
from algorithms.depso import DEPSO
from algorithms.rbrs_ae import RBRS_AE
from algorithms.routing.s_shape import s_shape_route
from benchmarks.fcfs import FCFS
from benchmarks.sop import SOP
from core.data_loader import Order, OrderLine
from core.warehouse import Warehouse
from tests.test_solution_integrity import assert_consistent


def layout(blocks, aisles=12, racks_total=60):
    return {'num_aisles': aisles, 'num_blocks': blocks,
            'racks_per_side_per_block': racks_total // blocks}


def random_orders(wh, n, seed):
    rng = random.Random(seed)
    orders = []
    for oid in range(n):
        lines = []
        for _ in range(rng.randint(1, 3)):
            w = round(rng.uniform(0.1, 1.0) * rng.randint(1, 6), 3)
            lines.append(OrderLine(item=rng.randrange(10**6), quantity=1,
                                   location=rng.randrange(wh.total_locations), weight=w))
        orders.append(Order(order_id=oid, num_orderlines=len(lines),
                            total_weight=round(sum(l.weight for l in lines), 3),
                            orderlines=lines))
    return orders


def test_default_is_kubler():
    wh = Warehouse()
    assert wh.total_locations == 7200
    assert wh.num_blocks == 3 and wh.cross_aisle_x == [0.0, 30.0, 62.0, 94.0]


@pytest.mark.parametrize("blocks", [1, 2, 3])
def test_location_count_and_cross_aisles(blocks):
    wh = Warehouse(layout(blocks))
    assert wh.total_locations == 12 * 2 * 60 * 4
    assert len(wh.cross_aisle_x) == blocks + 1
    assert wh.num_cross_aisles_inner == blocks - 1


def test_single_block_distance_uses_only_front_or_back():
    """Geçişsiz depoda farklı koridorlar arası yol yalnızca uçlardan geçer."""
    wh = Warehouse(layout(1))
    front, back = wh.cross_aisle_x
    rng = random.Random(1)
    for _ in range(500):
        a, b = rng.randrange(wh.total_locations), rng.randrange(wh.total_locations)
        (xa, ya), (xb, yb) = wh.coords(a), wh.coords(b)
        if wh._aisle_of(a) == wh._aisle_of(b):
            expected = abs(xa - xb)
        else:
            expected = min(abs(xa - front) + abs(xb - front),
                           abs(xa - back) + abs(xb - back)) + abs(ya - yb)
        assert wh.distance(a, b) == pytest.approx(expected)


@pytest.mark.parametrize("blocks", [2, 3])
def test_inner_cross_aisles_used(blocks):
    """Ara koridorlu depoda yol, yalnızca uçları kullanan yoldan uzun olamaz
    ve bazı çiftler için ara koridor sayesinde kesinlikle kısadır."""
    wh = Warehouse(layout(blocks))
    front, back = wh.cross_aisle_x[0], wh.cross_aisle_x[-1]
    rng = random.Random(blocks)
    shorter = 0
    for _ in range(500):
        a, b = rng.randrange(wh.total_locations), rng.randrange(wh.total_locations)
        if wh._aisle_of(a) == wh._aisle_of(b):
            continue
        (xa, ya), (xb, yb) = wh.coords(a), wh.coords(b)
        ends_only = min(abs(xa - front) + abs(xb - front),
                        abs(xa - back) + abs(xb - back)) + abs(ya - yb)
        d = wh.distance(a, b)
        assert d <= ends_only + 1e-9
        shorter += d < ends_only - 1e-9
    assert shorter > 0


def test_invalid_layouts_rejected():
    with pytest.raises(ValueError):
        Warehouse({'num_blocks': 0})
    with pytest.raises(ValueError):
        Warehouse({'num_aisle': 5})
    with pytest.raises(ValueError):
        Warehouse({'num_aisles': 5, 'total_locations': 7200})


@pytest.mark.parametrize("blocks", [1, 2])
def test_s_shape_runs_on_any_layout(blocks):
    wh = Warehouse(layout(blocks))
    rng = random.Random(blocks)
    for _ in range(50):
        locs = rng.sample(range(wh.total_locations), rng.randint(1, 30))
        route, dist = s_shape_route(locs, wh)
        assert set(route) - {wh.DEPOT} == set(locs)
        assert dist > 0


@pytest.mark.parametrize("blocks", [1, 2])
def test_algorithms_consistent_on_non_kubler_layout(blocks):
    wh = Warehouse(layout(blocks))
    orders = random_orders(wh, 30, seed=blocks)
    for algo in (DEPSO(num_iterations=20, seed=1), RBRS_AE(max_iterations=5, seed=1),
                 ALNS(max_iterations=30, seed=1)):
        assert_consistent(algo.solve(orders, wh), orders, wh)
    for base in (SOP(), FCFS()):
        sol = base.solve(orders, wh)
        assert sorted(id(o) for b in sol.batches for o in b.orders) == sorted(map(id, orders))
