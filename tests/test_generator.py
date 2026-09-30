"""
Parametrik üretici (core/generator.py) testleri.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from algorithms.rbrs_ae import RBRS_AE
from config import GENERATOR as GEN, ITEMS
from core.generator import InstanceSpec, generate, grid, layout_for, _power_law_shares
from tests.test_solution_integrity import assert_consistent


@pytest.fixture(scope="module")
def small():
    return generate(InstanceSpec(5000, 2, 0.7, 'orta', 0))


def test_same_spec_same_data():
    a = generate(InstanceSpec(5000, 1, 0.5, 'dusuk', 3))
    b = generate(InstanceSpec(5000, 1, 0.5, 'dusuk', 3))
    assert np.array_equal(a.demand, b.demand)
    assert np.array_equal(a.locations, b.locations)
    oa = a.sample_orders(40, set_id=2)
    ob = b.sample_orders(40, set_id=2)
    assert [[(l.item, l.quantity) for l in o.orderlines] for o in oa] == \
           [[(l.item, l.quantity) for l in o.orderlines] for o in ob]


def test_different_seed_different_data():
    a = generate(InstanceSpec(5000, 1, 0.5, 'orta', 0))
    b = generate(InstanceSpec(5000, 1, 0.5, 'orta', 1))
    assert not np.array_equal(a.demand, b.demand)


def test_grid_matches_meeting_design():
    g = grid()
    assert len(g) == len(GEN['grid_sizes']) * len(GEN['grid_blocks']) * len(GEN['grid_fills'])
    assert len({s.name for s in g}) == len(g)


@pytest.mark.parametrize("size", GEN['grid_sizes'])
@pytest.mark.parametrize("blocks", GEN['grid_blocks'])
def test_layout_close_to_target(size, blocks):
    from core.warehouse import Warehouse
    wh = Warehouse(layout_for(size, blocks))
    assert abs(wh.total_locations - size) / size < 0.05
    assert wh.num_blocks == blocks


@pytest.mark.parametrize("fill", [0.9, 0.7, 0.5])
def test_fill_rate(fill):
    inst = generate(InstanceSpec(5000, 3, fill, 'orta', 0))
    assert inst.num_items == round(fill * inst.warehouse.total_locations)
    assert len(set(inst.locations.tolist())) == inst.num_items, "iki ürün aynı yerde"


def test_items_placed_in_their_class_zone(small):
    zones = {c: set(z) for c, z in small.location_zones.items()}
    for i in range(small.num_items):
        assert int(small.locations[i]) in zones[small.initial_class[i]]


def test_power_law_hits_target_share():
    w = _power_law_shares(5000, 0.7)
    assert w[:1000].sum() == pytest.approx(0.7, abs=1e-3)


def test_orders_valid(small):
    subs = small.period_orders(small.first_test_period)
    orders = [o for s in subs for o in s]
    cap = ITEMS['picker_capacity_WU']
    for o in orders:
        items = [l.item for l in o.orderlines]
        assert len(items) == len(set(items)), "siparişte aynı ürün iki kez"
        assert 1 <= len(items) <= GEN['max_lines_per_order']
        assert o.total_weight <= cap
        for l in o.orderlines:
            assert l.location == int(small.locations[l.item])
            assert 1 <= l.quantity <= GEN['max_qty_per_line']
    # Satır sayısı dönemin talebine eşit
    lines = sum(o.num_orderlines for o in orders)
    assert lines == int(small.demand[:, small.first_test_period].sum())


def test_subperiods_balanced(small):
    n = [len(s) for s in small.period_orders(small.first_test_period)]
    assert len(n) == GEN['subperiods']
    assert max(n) - min(n) <= 1


def test_dynamics_levels_ordered():
    """Yapısal sınıf değişimi: düşük < orta < yüksek."""
    rates = [generate(InstanceSpec(10000, 2, 0.7, d, 0)).stats['structural_class_change_test_horizon']
             for d in ('dusuk', 'orta', 'yuksek')]
    assert rates[0] < rates[1] < rates[2]


def test_sample_orders_sets_differ(small):
    a = {o.order_id for o in small.sample_orders(50, 0)}
    b = {o.order_id for o in small.sample_orders(50, 1)}
    assert a != b and len(a) == len(b) == 50


def test_algorithm_runs_on_generated_instance(small):
    orders = small.sample_orders(30, 0)
    sol = RBRS_AE(max_iterations=5, seed=0).solve(orders, small.warehouse)
    assert_consistent(sol, orders, small.warehouse)


def test_save_writes_files(small, tmp_path):
    d = small.save(tmp_path, with_orders=True)
    for f in ('meta.json', 'items.json', 'demand.json'):
        assert (d / f).exists()
    assert list(d.glob('orders_period*.json'))


def test_invalid_spec_rejected():
    with pytest.raises(ValueError):
        generate(InstanceSpec(5000, 1, 0.5, 'cok_yuksek', 0))
    with pytest.raises(ValueError):
        generate(InstanceSpec(5000, 1, 1.5, 'orta', 0))


# ── Çok satan ↔ az satan dönüşümü ──────────────────────────────────────

def test_swap_pairs_fast_fade_slow_rise():
    inst = generate(InstanceSpec(5000, 2, 0.7, 'yuksek', 0))
    down = [i for i, p in enumerate(inst.profiles) if p == 'swap_down']
    up = [i for i, p in enumerate(inst.profiles) if p == 'swap_up']
    top = int(round(0.2 * inst.num_items))
    assert len(down) == len(up) == round(GEN['swap_share']['yuksek'] * top)
    E = inst.expected
    first = E[:, 0]
    rank = np.argsort(-first, kind='stable')
    popular = set(rank[:top].tolist())
    # sıralama beklenen talebin 1. dönemine göre (profiller biraz oynatır)
    assert np.mean([i in popular for i in down]) > 0.9     # sönenler popülerlerden
    assert np.mean([i not in popular for i in up]) > 0.9   # yükselenler az satanlardan
    last = E[:, -1]
    assert np.median(last[down] / first[down]) < 0.3  # sönmüş
    assert np.median(last[up] / first[up]) > 5        # yükselmiş


def test_swap_share_by_dynamics():
    counts = [generate(InstanceSpec(5000, 1, 0.7, d, 0)).profiles.count('swap_down')
              for d in ('dusuk', 'orta', 'yuksek')]
    assert counts[0] < counts[1] < counts[2]


def test_placement_uses_configured_period(small):
    from core.generator import _abc
    cls = _abc(small.demand[:, GEN['placement_period']], small.warehouse.class_pct)
    assert list(cls) == small.initial_class
