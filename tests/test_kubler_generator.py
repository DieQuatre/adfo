"""
Kübler (2020) §6.3 / Fig. 8 / Fig. 10 veri üretiminin yeniden kurulumu
(core/kubler_generator.py).
"""

import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.kubler_generator import KublerSpec, access_lines, generate_kubler


@pytest.fixture(scope="module")
def s1():
    return generate_kubler(KublerSpec(scenario=1))


@pytest.fixture(scope="module")
def s2():
    return generate_kubler(KublerSpec(scenario=2))


def lines_by_item(subperiods, n):
    c = Counter(l.item for sub in subperiods for o in sub for l in o.orderlines)
    v = np.zeros(n, dtype=int)
    for i, k in c.items():
        v[i] = k
    return v


def test_access_function():
    lines = access_lines(7500, 6000, 0.6)
    assert lines.sum() == 7500
    assert (np.diff(lines) <= 0).all()
    top20 = lines[:1200].sum() / 7500
    assert abs(top20 - 0.6) < 0.01                      # AF = en çok çekilen %20'nin payı


def test_period1_orders_follow_fig8(s1):
    subs = s1.period_orders(0)
    orders = [o for sub in subs for o in sub]
    assert len(orders) == 5000
    assert [len(x) for x in subs] == [250] * 20        # alt dönemlere düzgün
    for o in orders:
        assert 1 <= o.num_orderlines <= 2
        assert len(set(o.items)) == len(o.items)         # ürün siparişte en fazla bir kez
        for l in o.orderlines:
            assert 1 <= l.quantity <= 6
            assert l.weight == pytest.approx(l.quantity * s1.weights[l.item], abs=1e-3)
    assert (lines_by_item(subs, 6000) == s1.demand[:, 0]).all()


def test_later_periods_match_demand(s1):
    for p in (12, 20):
        subs = s1.period_orders(p)
        assert (lines_by_item(subs, 6000) == s1.demand[:, p]).all()
        sizes = [len(x) for x in subs]
        assert max(sizes) - min(sizes) <= 1
        for o in (o for sub in subs for o in sub):
            assert len(set(o.items)) == len(o.items) and 1 <= o.num_orderlines <= 2


def test_demand_limits(s1, s2):
    for d in (s1, s2):
        tot = d.demand.sum(axis=0)
        assert tot.max() <= 2.0 * tot.min()               # M = 2
        assert (d.demand >= 0).all()
        assert d.demand.shape == (6000, 21)


def test_initial_abc_assignment(s1):
    zone = {l: c for c, ls in s1.zones.items() for l in ls}
    cut = np.sort(s1.demand[:, 0])[::-1][299]           # 300. ürünün satır sayısı
    above = np.flatnonzero(s1.demand[:, 0] > cut)
    assert all(zone[int(s1.initial_locations[i])] == 'A' for i in above)
    assert sum(zone[int(l)] == 'A' for l in s1.initial_locations) == 300
    assert len(set(s1.initial_locations.tolist())) == 6000


def test_scenarios_share_period1_but_differ_later(s1, s2):
    assert (s1.demand[:, 0] == s2.demand[:, 0]).all()
    assert (s1.initial_locations == s2.initial_locations).all()
    assert (s1.weights == s2.weights).all()
    assert not (s1.demand[:, 12] == s2.demand[:, 12]).all()


def test_deterministic():
    a = generate_kubler(KublerSpec(scenario=1, seed=3))
    b = generate_kubler(KublerSpec(scenario=1, seed=3))
    assert (a.demand == b.demand).all()
    oa = [[l.item for l in o.orderlines] for o in a.period_orders(14)[0]]
    ob = [[l.item for l in o.orderlines] for o in b.period_orders(14)[0]]
    assert oa == ob


def test_fast_movers_turn_over(s1, s2):
    """Fig. 10'un amacı: 1. dönemin hızlı ürünlerinin bir kısmı yavaşlar,
    başka ürünler hızlanır. 1. test döneminde A sınıfının önemli bir kısmı
    başlangıçta A olmayan ürünlerden oluşmalı; yüksek dinamikte daha çok."""
    def new_in_A(d, p=12):
        top = np.argsort(-d.demand[:, p], kind='stable')[:300]
        return int((d.item_class[top] != 0).sum())
    assert new_in_A(s1) >= 90
    assert new_in_A(s2) >= 60
    assert s1.stats['bi_declining'] > 0
