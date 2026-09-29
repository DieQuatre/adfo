"""
Deney protokolü (core/experiment.py, compare_algorithms.py):
kod sürümü kontrolü, eşit süre bütçesi, çoklu tohum, istatistik.
"""

import random
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from algorithms.alns import ALNS
from algorithms.depso import DEPSO
from algorithms.rbrs_ae import RBRS_AE
from core import experiment as ex
from core.experiment import Protocol
from core.warehouse import Warehouse
from run_batch import load_pool


@pytest.fixture(scope="module")
def small():
    pool = load_pool(2, 6)
    orders = pool[:]
    random.Random(3).shuffle(orders)
    return orders[:40], Warehouse()


# ── Protokol ───────────────────────────────────────────────────────────

def test_default_protocol_keeps_old_file_names():
    assert Protocol().tag == "" and Protocol().is_default
    assert Protocol(n_seeds=5, time_budget=60).tag == "__s5__t60"
    assert Protocol(time_per_order=0.5).tag == "__tpo0.5"
    assert Protocol(time_per_order=0.5).budget_for(200) == 100
    with pytest.raises(ValueError):
        Protocol(time_budget=10, time_per_order=0.1)


def test_seed_zero_matches_single_seed_run(small):
    orders, wh = small
    one = ex.solve_all(orders, wh, 42, Protocol(depso_iter=20))
    three = ex.solve_all(orders, wh, 42, Protocol(depso_iter=20, n_seeds=3))
    for a in ex.METAHEURISTICS:
        assert three[a]['td_seeds'][0] == pytest.approx(one[a]['td'], abs=1e-3)
        assert len(three[a]['td_seeds']) == 3
        assert three[a]['td'] == pytest.approx(sum(three[a]['td_seeds']) / 3, abs=1e-3)
    assert three['SOP']['td'] == one['SOP']['td']
    assert DEPSO(num_iterations=20, seed=42).solve(orders, wh).total_travel_distance == \
        pytest.approx(one['DEPSO']['td'], abs=1e-3)


# ── Eşit süre bütçesi ──────────────────────────────────────────────────

@pytest.mark.parametrize("cls", [DEPSO, RBRS_AE, ALNS])
def test_time_budget_is_respected(cls, small):
    orders, wh = small
    algo = cls(seed=1)
    algo.time_limit = 1.5
    sol = algo.solve(orders, wh)
    assert sol.runtime_seconds < 1.5 + 1.0          # bir iterasyonluk taşma payı
    assert sol.total_travel_distance > 0
    covered = sorted(o.order_id for b in sol.batches for o in b.orders)
    assert covered == sorted(o.order_id for o in orders)


def test_budget_runs_longer_than_iteration_limit_allows(small):
    """Bütçe modunda iterasyon sınırı değil süre durdurur."""
    orders, wh = small
    a = ALNS(seed=1, max_iterations=5)
    a.time_limit = 1.0
    assert a.solve(orders, wh).iterations_used > 5


def test_no_budget_behaviour_unchanged(small):
    orders, wh = small
    assert DEPSO(num_iterations=15, seed=1).solve(orders, wh).iterations_used == 15
    assert ALNS(seed=1, max_iterations=30).solve(orders, wh).iterations_used == 30


# ── Kod sürümü ─────────────────────────────────────────────────────────

def test_git_state_detects_tracked_changes(tmp_path, monkeypatch):
    def git(*a):
        subprocess.run(['git', *a], cwd=tmp_path, check=True, capture_output=True)
    git('init', '-q')
    (tmp_path / 'a.py').write_text('x = 1\n')
    (tmp_path / 'results').mkdir()
    (tmp_path / 'results' / 'r.json').write_text('{}')
    git('add', '.')
    git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'i')
    monkeypatch.setattr(ex, 'ROOT', tmp_path)
    assert ex.git_state()['dirty'] is False
    (tmp_path / 'results' / 'r.json').write_text('{"x": 1}')   # koşum çıktısı sayılmaz
    (tmp_path / 'new.txt').write_text('izlenmeyen')             # izlenmeyen dosya sayılmaz
    assert ex.git_state()['dirty'] is False
    (tmp_path / 'a.py').write_text('x = 2\n')
    st = ex.git_state()
    assert st['dirty'] is True and st['files'] == ['a.py']
    with pytest.raises(SystemExit):
        ex.require_clean(allow_dirty=False)
    assert ex.require_clean(allow_dirty=True)['dirty'] is True


# ── İstatistik ─────────────────────────────────────────────────────────

def test_wilcoxon_and_holm():
    from compare_algorithms import holm
    x = [100 - i for i in range(20)]
    y = [101 - i for i in range(20)]
    t = ex.wilcoxon(x, y)
    assert t['x_better'] == 20 and t['p'] < 0.001
    assert ex.wilcoxon(x, x)['p'] is None               # fark yok
    assert holm([0.01, 0.04, None, 0.03]) == pytest.approx([0.03, 0.06, None, 0.06])


def test_compare_report_on_generated_like_results(tmp_path):
    import json
    from compare_algorithms import load, report
    rows = []
    for i in range(8):
        r = {'name': f"S5000_B1_F70_orta_s0", 'k': 50, 'spec': {'size': 5000, 'blocks': 1}}
        for j, a in enumerate(ex.METAHEURISTICS):
            seeds = [1000 + 10 * j + i + s for s in range(3)]
            r[a] = {'td': sum(seeds) / 3, 'rt': 1.0, 'td_seeds': seeds}
        rows.append(r)
    f = tmp_path / "results__s3__t1.json"
    f.write_text(json.dumps({'git': {'commit': 'abc', 'dirty': False}, 'jobs': 1,
                             'protocol': {'depso_iter': 500, 'n_seeds': 3, 'time_budget': 1,
                                          'time_per_order': None},
                             'results': rows}))
    inst, meta = load(f)
    text = report(inst, meta, f)
    assert "| Örnek | 8/8 | 0/8 | 0/8 | 0/8 |" in text      # DEPSO hep en kısa
    assert "Tohumlar arası değişkenlik" in text
    assert "Uyarılar" not in text                          # temiz, bütçeli, çok tohum, tek işlem
