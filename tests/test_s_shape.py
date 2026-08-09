"""tests/test_s_shape.py — Gerçek S-Shape (traversal) testleri.

QA bulgusu: Eski S-shape en-kısa-yol hesaplıyordu (sahte).
Gerçek S-shape aisle'ı tam kat eder (traversal) — bu bir benchmark'tır,
optimal olmamalıdır.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.warehouse import Warehouse
from algorithms.routing.s_shape import s_shape_route
from algorithms.routing.two_opt import nn_then_2opt


def test_single_location_optimal():
    """Tek lokasyonda S-shape = optimal git-gel (traversal gereksiz)."""
    wh = Warehouse()
    loc = 100
    x, y = wh.coords(loc)
    _, dist = s_shape_route([loc], wh)
    optimal = 2 * (abs(wh.depot_x - x) + abs(wh.depot_y - y))
    assert abs(dist - optimal) < 1.0


def test_s_shape_not_shorter_than_optimal():
    """S-shape bir benchmark — NN+2opt'ten kısa OLMAMALI (çok aisle'da)."""
    wh = Warehouse()
    test_locs = [100, 1500, 3700, 5200, 6800]
    _, s_dist = s_shape_route(test_locs, wh)
    _, nn_dist = nn_then_2opt(test_locs, wh)
    assert s_dist >= nn_dist


def test_empty_returns_zero():
    wh = Warehouse()
    route, dist = s_shape_route([], wh)
    assert dist == 0.0


def test_route_starts_ends_at_depot():
    wh = Warehouse()
    route, _ = s_shape_route([100, 500, 1500], wh)
    assert route[0] == wh.DEPOT
    assert route[-1] == wh.DEPOT


def test_all_picks_visited():
    """Tüm pick'ler rotada olmalı."""
    wh = Warehouse()
    locs = [100, 1500, 3700]
    route, _ = s_shape_route(locs, wh)
    for loc in locs:
        assert loc in route


def test_traversal_covers_aisle():
    """Aynı aisle'da 2 uzak pick → traversal aisle boyunca yürümeli."""
    wh = Warehouse()
    # Aisle 0'da x=0.5 ve x=93.5 (iki uç)
    loc_left = 0      # x≈0.5
    loc_right = 359   # aisle 0, en sağ rack
    xl = wh.coords(loc_left)[0]
    xr = wh.coords(loc_right)[0]
    if abs(xr - xl) > 50:  # gerçekten uzaksa
        _, dist = s_shape_route([loc_left, loc_right], wh)
        # En az aisle uzunluğu kadar yürümeli
        assert dist >= abs(xr - xl)


if __name__ == "__main__":
    test_single_location_optimal()
    test_s_shape_not_shorter_than_optimal()
    test_empty_returns_zero()
    test_route_starts_ends_at_depot()
    test_all_picks_visited()
    test_traversal_covers_aisle()
    print("✅ test_s_shape: tüm testler geçti")
