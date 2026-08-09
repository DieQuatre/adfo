"""tests/test_relocation.py — Dynamic relocation testleri.

QA bulgusu: relocation.py'a hiç test yoktu, modül 3 commit boyunca
ölü kaldı fark edilmeden. Bu testler temel işlevselliği garanti eder.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_loader import DataLoader
from core.warehouse import Warehouse
from algorithms.relocation import DynamicRelocation, ItemState


def _make_reloc():
    loader = DataLoader()
    wh = Warehouse()
    items = loader.load_items()
    item_locations = [it.initial_location for it in items]
    item_classes = [it.class_period1 for it in items]
    loc_classes = loader.load_location_classes()
    reloc = DynamicRelocation(wh, loc_classes)
    reloc.initialize(item_locations, item_classes)
    return reloc, loader, wh


def test_initialize_sets_states():
    """initialize() tüm item'lar için state oluşturmalı."""
    reloc, _, _ = _make_reloc()
    assert len(reloc.item_states) == 6000
    # Her item'ın bir lokasyonu olmalı
    for st in list(reloc.item_states.values())[:100]:
        assert st.location >= 0


def test_loc_to_item_consistent():
    """loc_to_item ve item_states tutarlı olmalı."""
    reloc, _, _ = _make_reloc()
    for item_id, st in list(reloc.item_states.items())[:100]:
        assert reloc.loc_to_item.get(st.location) == item_id


def test_class_tracking_increments():
    """Yanlış sınıfta olan item'ın sayacı artmalı."""
    reloc, _, _ = _make_reloc()
    # Yapay: bir item'ı yanlış sınıfa işaretle
    some_id = list(reloc.item_states.keys())[0]
    st = reloc.item_states[some_id]
    orig_cls = st.current_class
    wrong_cls = 'A' if orig_cls != 'A' else 'C'

    fc = {some_id: wrong_cls}
    # Diğerleri doğru kalsın
    for iid in reloc.item_states:
        if iid != some_id:
            fc[iid] = reloc.item_states[iid].current_class

    reloc._update_class_tracking(fc)
    assert reloc.item_states[some_id].periods_in_wrong_class == 1
    reloc._update_class_tracking(fc)
    assert reloc.item_states[some_id].periods_in_wrong_class == 2


def test_class_tracking_resets():
    """Doğru sınıfa dönünce sayaç sıfırlanmalı."""
    reloc, _, _ = _make_reloc()
    some_id = list(reloc.item_states.keys())[0]
    st = reloc.item_states[some_id]
    orig = st.current_class
    wrong = 'A' if orig != 'A' else 'C'

    fc_wrong = {iid: (wrong if iid == some_id else s.current_class)
                for iid, s in reloc.item_states.items()}
    reloc._update_class_tracking(fc_wrong)
    assert reloc.item_states[some_id].periods_in_wrong_class == 1

    fc_right = {iid: s.current_class for iid, s in reloc.item_states.items()}
    reloc._update_class_tracking(fc_right)
    assert reloc.item_states[some_id].periods_in_wrong_class == 0


def test_apply_undo_restores_state():
    """apply sonra undo → state tam eski haline dönmeli."""
    reloc, _, wh = _make_reloc()
    # Boş bir A lokasyonu bul
    asc = None
    for st in reloc.item_states.values():
        if st.current_class == 'C':
            asc = st
            break
    assert asc is not None

    orig_loc = asc.location
    orig_cls = asc.current_class
    orig_empty_a = len(reloc.empty_locs.get('A', []))

    asc.forecast_class = 'A'
    if reloc.empty_locs.get('A'):
        target_loc = reloc.empty_locs['A'][0]
        sug = {'type': 1, 'asc_item': asc, 'asc_new_loc': target_loc,
               'desc_item': None, 'desc_new_loc': None}
        reloc._apply_suggestion(sug)
        assert asc.location == target_loc
        reloc._undo_suggestion(sug)
        # Tam restore
        assert asc.location == orig_loc
        assert asc.current_class == orig_cls
        assert len(reloc.empty_locs.get('A', [])) == orig_empty_a


def test_run_period_produces_suggestions():
    """Sayaç dolunca run_period öneri üretmeli (relocation ölü olmamalı)."""
    from core.forecasting import ItemForecaster
    from algorithms.depso import DEPSO

    reloc, loader, wh = _make_reloc()
    demand = loader.load_scenario_demand(1)
    forecaster = ItemForecaster()
    forecaster.fit_all(demand, warmup_periods=12)
    algo = DEPSO(num_iterations=20, seed=42)

    total_tested = 0
    for period in range(1, 4):
        orders = loader.load_orders(1, period, 1).orders[:30]
        forecasts = forecaster.predict_all(tau=1)
        result = reloc.run_period(period, orders, forecasts, algo)
        forecaster.update_all(demand[:, 11 + period])
        total_tested += result.num_suggestions_tested

    # 3 periyot sonunda en az bir öneri test edilmiş olmalı
    assert total_tested > 0, "Relocation hiç öneri üretmiyor (ölü modül)"


if __name__ == "__main__":
    test_initialize_sets_states()
    test_loc_to_item_consistent()
    test_class_tracking_increments()
    test_class_tracking_resets()
    test_apply_undo_restores_state()
    test_run_period_produces_suggestions()
    print("✅ test_relocation: tüm testler geçti")
