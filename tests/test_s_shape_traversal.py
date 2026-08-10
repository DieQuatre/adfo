"""
tests/test_s_shape_traversal.py
================================
S-Shape'in TANIMLAYICI özelliğini doğrular: pick içeren koridor baştan sona
geçilir, boş kısımlar dahil.

Eski implementasyon koridoru geçmiyor, pick'ler arasını en kısa yolla
topluyordu; sonuç neredeyse optimal bir rotaydı. Mevcut smoke testi
(`test_smoke.py::test_s_shape`) sadece `dist > 0` kontrol ettiği için bunu
yakalayamadı. Buradaki testler geometriyi elle hesaplanmış değerlerle
karşılaştırır.

Geometri (config.py + core/warehouse.py):
  cross_aisle_x = [0, 30, 62, 94]      depot = (96, 0)
  aisle_y[i]    = (i + 0.5) * 3        → aisle 0: 1.5, aisle 1: 4.5
  blok 0 rafları: x = 0.5 .. 29.5      kapıları: x = 0 (uzak), x = 30 (yakın)
  loc_id = aisle*720 + side*360 + rack*4 + within
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from algorithms.routing.s_shape import s_shape_route
from algorithms.routing.two_opt import nn_then_2opt
from core.warehouse import Warehouse

# aisle 0 / aisle 1, blok 0'ın son rafı (rack 29) → kapıya (x=30) bitişik
LOC_A0_NEAR_GATE = 116   # 0*720 + 0 + 29*4 + 0  → x = 29.5, y = 1.5
LOC_A1_NEAR_GATE = 836   # 1*720 + 0 + 29*4 + 0  → x = 29.5, y = 4.5
LOC_A0_FAR = 0           # 0*720 + 0 +  0*4 + 0  → x =  0.5, y = 1.5


@pytest.fixture(scope="module")
def wh():
    return Warehouse()


def test_geometry_assumptions_hold(wh):
    """Elle hesaplanan beklenen değerler bu geometriye dayanıyor."""
    assert wh.cross_aisle_x == [0.0, 30.0, 62.0, 94.0]
    assert (wh.depot_x, wh.depot_y) == (96.0, 0.0)
    assert wh.coords(LOC_A0_NEAR_GATE) == (29.5, 1.5)
    assert wh.coords(LOC_A1_NEAR_GATE) == (29.5, 4.5)


def test_single_pick_is_enter_and_return(wh):
    """
    Tek koridorda tek pick → gir-çık. Bu durumda S-shape en kısa yola eşittir.
      depot→kapı 66 + koridora 1.5 + gir-çık 2×29.5 + geri 1.5 + kapı→depot 66
    """
    _, dist = s_shape_route([LOC_A0_FAR], wh)
    assert dist == pytest.approx(194.0)
    assert dist == pytest.approx(2 * wh.distance(wh.DEPOT, LOC_A0_FAR))


def test_two_aisles_are_traversed_completely(wh):
    """
    İki koridorun ikisi de TAM geçilir; pick'ler kapının hemen dibinde olsa
    bile koridorun 30 LU'luk tamamı yürünür.

      66 (depot→kapı 30) + 1.5 (aisle 0'a) + 30 (tam geçiş)
         + 3 (aisle 1'e)  + 30 (tam geçiş) + 4.5 (ön koridora) + 66 = 201
    """
    route, dist = s_shape_route([LOC_A0_NEAR_GATE, LOC_A1_NEAR_GATE], wh)
    assert dist == pytest.approx(201.0)
    assert route[0] == wh.DEPOT and route[-1] == wh.DEPOT
    assert set(route[1:-1]) == {LOC_A0_NEAR_GATE, LOC_A1_NEAR_GATE}


def test_s_shape_is_worse_than_optimised_routing(wh):
    """
    Pick'ler kapı dibindeyken S-shape, NN+2opt'tan belirgin PAHALI olmalı.
    Eski implementasyonda ikisi birebir aynı çıkıyordu — sahte S-shape'in
    işareti buydu.
    """
    locs = [LOC_A0_NEAR_GATE, LOC_A1_NEAR_GATE]
    _, s_dist = s_shape_route(locs, wh)
    _, opt_dist = nn_then_2opt(locs, wh)
    assert s_dist > opt_dist * 1.2, (
        f"S-shape ({s_dist}) optimize rotaya ({opt_dist}) fazla yakın — "
        "koridorlar tam geçilmiyor olabilir"
    )


def test_never_cheaper_than_shortest_path_tour(wh):
    """S-shape kısıtlı bir sezgiseldir; optimize rotanın altına inemez."""
    import random
    rng = random.Random(7)
    for _ in range(20):
        locs = rng.sample(range(wh.total_locations), 12)
        _, s_dist = s_shape_route(locs, wh)
        _, opt_dist = nn_then_2opt(locs, wh)
        assert s_dist >= opt_dist - 1e-6


def test_empty_and_depot_only_inputs(wh):
    assert s_shape_route([], wh) == ([wh.DEPOT, wh.DEPOT], 0.0)
    assert s_shape_route([wh.DEPOT], wh) == ([wh.DEPOT, wh.DEPOT], 0.0)
