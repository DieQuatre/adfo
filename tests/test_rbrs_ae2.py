"""RBRS-AE iyileştirme sınıfı (algorithms/rbrs_ae2.py)."""

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from algorithms.rbrs_ae import RBRS_AE
from algorithms.rbrs_ae2 import IMPROVED, OPTIONS, RBRS_AE2
from core.warehouse import Warehouse
from run_batch import load_pool
from tests.test_solution_integrity import assert_consistent


@pytest.fixture(scope="module")
def inst():
    pool = load_pool(6, 6)[:]
    random.Random(4).shuffle(pool)
    return pool[:40], Warehouse()


def test_default_options_reproduce_original(inst):
    orders, wh = inst
    a = RBRS_AE(seed=3).solve(orders, wh).total_travel_distance
    b = RBRS_AE2(seed=3).solve(orders, wh).total_travel_distance
    assert a == pytest.approx(b, abs=1e-9)


@pytest.mark.parametrize("opt", list(IMPROVED))
def test_each_option_gives_valid_solution(inst, opt):
    orders, wh = inst
    sol = RBRS_AE2(seed=1, max_iterations=8, **{opt: IMPROVED[opt]}).solve(orders, wh)
    assert_consistent(sol, orders, wh)


def test_recommended_valid_and_named(inst):
    orders, wh = inst
    algo = RBRS_AE2.recommended(seed=2, max_iterations=8)
    sol = algo.solve(orders, wh)
    assert algo.name == 'RBRS-AE2' and sol.extra_info['options']['destroy'] == 'mix'
    assert_consistent(sol, orders, wh)


def test_time_budget(inst):
    orders, wh = inst
    a = RBRS_AE2.recommended(seed=1)
    a.time_limit = 1.0
    assert a.solve(orders, wh).runtime_seconds < 2.0


def test_unknown_option_rejected():
    with pytest.raises(ValueError):
        RBRS_AE2(destroy='hepsi')
    assert set(OPTIONS) == set(IMPROVED)
