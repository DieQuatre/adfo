"""
tests/test_relocation.py
=========================
Dynamic storage relocation regresyon testleri.

Bu modül denetim öncesi HİÇ test edilmiyordu. `_update_class_tracking` iki
sayacı birbirini sıfırlayacak şekilde güncellediği için `_build_priority_list`
içindeki `o AND u` koşulu asla sağlanamıyor, dolayısıyla hiçbir periyotta tek
bir relocation önerisi bile üretilmiyordu. Aşağıdaki testler o hatanın geri
gelmesini engeller.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from algorithms.relocation import DynamicRelocation
from core.data_loader import DataLoader
from core.warehouse import Warehouse


@pytest.fixture(scope="module")
def wh():
    return Warehouse()


@pytest.fixture(scope="module")
def loader():
    return DataLoader()


@pytest.fixture(scope="module")
def reloc(wh, loader):
    """6000 item ile başlatılmış relocation motoru."""
    items = loader.load_items()
    r = DynamicRelocation(wh, loader.load_location_classes())
    r.initialize([it.initial_location for it in items],
                 [it.class_period1 for it in items])
    return r


# ── Sayaç mantığı ────────────────────────────────────────────────────

def test_counters_are_independent(reloc):
    """
    o ve u sayaçları farklı şeyleri ölçer ve AYNI ANDA pozitif olabilmelidir.
    Aksi halde `o AND u` koşulu matematiksel olarak sağlanamaz.
    """
    item_id = next(iter(reloc.item_states))
    state = reloc.item_states[item_id]
    other = 'A' if state.current_class != 'A' else 'C'

    # Aynı yanlış tahmini üst üste 3 periyot ver
    for _ in range(3):
        reloc._update_class_tracking({item_id: other})

    assert state.periods_in_wrong_class >= 2, "o sayacı artmalı"
    assert state.periods_in_target_class >= 1, "u sayacı aynı anda pozitif olmalı"


def test_unstable_forecast_resets_u_counter(reloc):
    """Hedef sınıf tahmini değişirse u sayacı sıfırlanmalı (istikrar ölçüsü)."""
    item_id = next(iter(reloc.item_states))
    state = reloc.item_states[item_id]

    reloc._update_class_tracking({item_id: 'A'})
    reloc._update_class_tracking({item_id: 'A'})
    stable = state.periods_in_target_class

    reloc._update_class_tracking({item_id: 'C'})   # tahmin değişti
    assert state.periods_in_target_class == 1
    assert state.periods_in_target_class < stable


# ── Aday üretimi ─────────────────────────────────────────────────────

def test_priority_list_is_not_permanently_empty(reloc, loader):
    """
    Gerçek Holt-Winters tahminleriyle, o eşiği aşıldıktan sonra aday listesi
    boş OLMAMALI. (Hata varken 9 periyot boyunca hep 0 aday üretiliyordu.)
    """
    from core.forecasting import ItemForecaster

    demand = loader.load_scenario_demand(1)
    fc = ItemForecaster()
    fc.fit_all(demand, warmup_periods=12)

    counts = []
    for p in range(1, 5):
        classes = reloc._classify_by_forecast(fc.predict_all(tau=1))
        reloc._update_class_tracking(classes)
        counts.append(len(reloc._build_priority_list()))
        fc.update_all(demand[:, 11 + p])

    assert max(counts) > 0, f"hiçbir periyotta aday üretilmedi: {counts}"


def test_priority_list_only_contains_ascending_items(reloc):
    """Aday listesi yalnızca daha ÜST sınıfa taşınması gereken itemler içerir."""
    order = {'A': 0, 'B': 1, 'C': 2}
    for state in reloc._build_priority_list():
        assert order[state.current_class] > order[state.forecast_class]


# ── Uçtan uca ────────────────────────────────────────────────────────

def test_run_period_produces_measurable_result(wh, loader):
    """
    run_period gerçek siparişlerle çalıştığında travel distance ölçmeli.
    Hata varken td_before/td_after 0.0 kalıyordu.
    """
    from core.forecasting import ItemForecaster
    from algorithms.depso import DEPSO

    items = loader.load_items()
    r = DynamicRelocation(wh, loader.load_location_classes())
    r.initialize([it.initial_location for it in items],
                 [it.class_period1 for it in items])

    demand = loader.load_scenario_demand(1)
    fc = ItemForecaster()
    fc.fit_all(demand, warmup_periods=12)
    algo = DEPSO(num_iterations=5, seed=42)

    saw_measurement = False
    for period in range(1, 4):
        orders = loader.load_orders(1, period, 1).orders[:20]
        res = r.run_period(period, orders, fc.predict_all(tau=1), algo)
        fc.update_all(demand[:, 11 + period])
        if res.travel_distance_before > 0:
            saw_measurement = True
            assert res.travel_distance_after > 0
            assert res.num_accepted + res.num_rejected > 0

    assert saw_measurement, "hiçbir periyotta relocation değerlendirmesi yapılmadı"
