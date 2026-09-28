"""
Relocation (algorithms/relocation.py) testleri — Kübler §5.3.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from algorithms.relocation import (DynamicRelocation, abc_with_limits, relevant_limit,
                                   validate_approximation)
from core.dynamic_data import from_generated
from core.generator import InstanceSpec, generate
from core.warehouse import Warehouse
from run_dynamic import run_experiment, solve


# ── 5.3.1 sınıflandırma ────────────────────────────────────────────────

def test_abc_with_limits():
    vals = np.array([10, 50, 3, 7, 30, 1, 0, 2, 5, 4, 8, 9, 6, 11, 12, 13, 14, 15, 16, 17], float)
    cls, lim = abc_with_limits(vals, {'A': 0.05, 'B': 0.15})
    assert cls[1] == 0 and (cls == 0).sum() == 1          # %5 → 1 ürün A
    assert (cls == 1).sum() == 3                            # %15 → 3 ürün B
    assert lim['A'] == 50 and lim['B'] == 16                # son A ve son B ürününün değeri


def test_relevant_limit():
    assert relevant_limit(2, 0) == 'A'      # C → A: hedefin (A) alt sınırı
    assert relevant_limit(1, 0) == 'A'      # B → A
    assert relevant_limit(2, 1) == 'B'      # C → B
    assert relevant_limit(0, 2) == 'A'      # A → C: mevcut sınıfın (A) alt sınırı
    assert relevant_limit(1, 2) == 'B'      # B → C


# ── 5.3.4 takas senaryoları, küçük elle kurulmuş depo ─────────────────

def tiny(occupied_A=True, empty_B=0):
    """20 lokasyonluk depo: 1 A, 3 B, 16 C lokasyonu."""
    wh = Warehouse({'num_aisles': 2, 'num_blocks': 1, 'racks_per_side_per_block': 5,
                    'locs_per_rack': 1})
    zones = wh.assign_locations_to_classes()
    A, B, C = zones['A'], zones['B'], zones['C']
    locs = []
    if occupied_A:
        locs.append(A[0])
    locs += B[:3 - empty_B]
    locs += C[:10]
    n = len(locs)
    R = DynamicRelocation(wh, zones, np.array(locs), np.zeros((n, 13)), 12)
    return R, zones


def cand(R, item, target, pv=1.0):
    return {'item': item, 'cur': R.current_class(item), 'target': target, 'pv': pv,
            'u_tar': 1, 'key': relevant_limit(R.current_class(item), target)}


def test_scenario_1_empty_target():
    R, zones = tiny(occupied_A=False)
    c_item = 3                                        # bir C ürünü
    sug = R._build_suggestion(cand(R, c_item, 0), [])
    assert sug.scenario == 1 and sug.moves[0].dst == zones['A'][0]


def test_scenario_2_direct_exchange():
    R, zones = tiny()
    a_item, c_item = 0, 5
    sug = R._build_suggestion(cand(R, c_item, 0), [cand(R, a_item, 2)])
    assert sug.scenario == 2
    moves = {m.item: (m.src, m.dst) for m in sug.moves}
    assert moves[c_item][1] == moves[a_item][0] and moves[a_item][1] == moves[c_item][0]


def test_scenario_3_indirect_via_empty_third_class():
    R, zones = tiny(empty_B=1)
    a_item, c_item = 0, 5
    sug = R._build_suggestion(cand(R, c_item, 0), [cand(R, a_item, 1)])
    assert sug.scenario == 3
    moves = {m.item: m for m in sug.moves}
    assert moves[c_item].dst == zones['A'][0]
    assert moves[a_item].dst in zones['B'] and moves[a_item].dst_class == 'B'


def test_scenario_4_three_item_cycle():
    R, zones = tiny()
    a_item, b_item, c_item = 0, 1, 5
    sug = R._build_suggestion(cand(R, c_item, 0), [cand(R, a_item, 1), cand(R, b_item, 2)])
    assert sug.scenario == 4
    m = {x.item: x for x in sug.moves}
    assert m[c_item].dst == m[a_item].src
    assert m[a_item].dst == m[b_item].src
    assert m[b_item].dst == m[c_item].src


def test_no_suggestion_without_partner():
    R, _ = tiny()
    assert R._build_suggestion(cand(R, 5, 0), []) is None


def test_apply_keeps_bookkeeping_consistent():
    R, zones = tiny(empty_B=1)
    sug = R._build_suggestion(cand(R, 5, 0), [cand(R, 0, 1)])
    R._apply(sug)
    locs = R.loc.tolist()
    assert len(set(locs)) == len(locs)
    for c, r in (('A', 0), ('B', 1), ('C', 2)):
        occupied = {l for l in zones[c] if l in R.item_at}
        assert occupied.isdisjoint(R.empty[r])
        assert len(occupied) + len(R.empty[r]) == len(zones[c])
    assert R.current_class(5) == 0 and R.current_class(0) == 1


# ── 5.3.3 yer kontrolü ─────────────────────────────────────────────────

def test_feasibility_drops_lowest_priority_entering_items():
    R, _ = tiny()                           # A dolu, boş A yok
    cands = [cand(R, 5, 0, pv=9.0), cand(R, 6, 0, pv=1.0)]   # iki ürün A'ya girmek istiyor
    kept = R._feasible(cands)
    assert [c['item'] for c in kept] == []  # A'dan çıkan yok, boş yok → ikisi de düşer
    cands.append(cand(R, 0, 2, pv=5.0))     # A'daki ürün C'ye inecek → bir yer açılır
    kept = R._feasible(cands)
    assert {c['item'] for c in kept} == {5, 0}


# ── Uçtan uca: üretilmiş dinamik depo ─────────────────────────────────

@pytest.fixture(scope="module")
def dyn():
    inst = generate(InstanceSpec(5000, 2, 0.6, 'yuksek', 0))
    return from_generated(inst)


def test_run_period_invariants(dyn):
    R = DynamicRelocation(dyn.warehouse, dyn.zones, dyn.initial_locations, dyn.demand, dyn.warmup)
    zone_size = {0: len(dyn.zones['A']), 1: len(dyn.zones['B']), 2: len(dyn.zones['C'])}
    accepted_total = 0
    for p in dyn.test_periods[:4]:
        subs = dyn.orders_fn(p)[:3]
        res = R.run_period(p, subs, batch_fn=lambda o, w: solve('FIRSTFIT', o, w, 0, 0)[1],
                           tdr_scale=dyn.subperiods / 3)
        assert res.tested <= R.max_suggestions
        for s in res.suggestions:
            if s.accepted:
                assert s.tdr > 0 and s.future_gain > s.effort
            elif s.moves and s.reason == 'bu dönemde kazanç yok':
                assert s.tdr <= 0
        accepted_total += res.accepted
        locs = R.loc.tolist()
        assert len(set(locs)) == len(locs), "iki ürün aynı yerde"
        for r in range(3):
            occ = sum(1 for l in locs if R.zone_of[l] == r)
            assert occ + len(R.empty[r]) == zone_size[r]
    assert accepted_total > 0, "yüksek dinamiklikte en az bir taşıma beklenir"


def test_first_period_has_no_candidates_because_of_o(dyn):
    R = DynamicRelocation(dyn.warehouse, dyn.zones, dyn.initial_locations, dyn.demand, dyn.warmup)
    p = dyn.test_periods[0]
    res = R.run_period(p, dyn.orders_fn(p)[:1], batch_fn=lambda o, w: solve('FIRSTFIT', o, w, 0, 0)[1])
    assert res.candidates == 0              # o = 2: yanlış sınıfta en az 2 dönem


def test_run_experiment_reports(dyn):
    rows, summary = run_experiment(dyn, 'FIRSTFIT', 0, used=2, n_periods=3)
    assert len(rows) == 3
    assert rows[0]['td_static'] == rows[0]['td_dynamic']      # ilk dönem henüz taşıma yok
    for r in rows:
        assert r['td_static'] > 0 and r['effort_pct'] >= 0
    assert set(summary) >= {'reduction_pct', 'effort_pct', 'net_pct'}


def test_approximation_exact_for_location_blind_batching(dyn):
    """First-fit gruplaması lokasyona bakmaz; yaklaşık ve tam Tdr birebir aynı olmalı."""
    R = DynamicRelocation(dyn.warehouse, dyn.zones, dyn.initial_locations, dyn.demand, dyn.warmup)
    fn = lambda o, w: solve('FIRSTFIT', o, w, 0, 0)
    for p in dyn.test_periods[:3]:
        subs = dyn.orders_fn(p)[:2]
        snap = (R.loc.copy(), {k: set(v) for k, v in R.empty.items()}, dict(R.item_at),
                R.wrong_count.copy())
        res = R.run_period(p, subs, batch_fn=lambda o, w: fn(o, w)[1])
    R.loc, R.empty, R.item_at, R.wrong_count = snap
    rows = validate_approximation(R, subs, fn, [s for s in res.suggestions if s.moves][:5])
    assert rows
    for r in rows:
        assert r['tdr_approx'] == pytest.approx(r['tdr_full'], abs=1e-6)
