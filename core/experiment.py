"""
core/experiment.py
==================
Deney koşucularının (run_batch.py, run_generated.py) ortak parçaları:

- Kod sürümü: sonuç hangi commit'ten geldi, commit'lenmemiş değişiklik var mı.
  Temiz olmayan kodla koşum varsayılan olarak reddedilir (--allow-dirty).
- Deney protokolü: DEPSO iterasyonu, tohum sayısı, eşit süre bütçesi.
- Tüm algoritmaları aynı siparişlerle çözme (birden çok tohumla).
- Eşleştirilmiş karşılaştırma için Wilcoxon işaretli sıralar testi.
"""

from __future__ import annotations

import statistics
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BASELINES = ['SOP', 'FCFS']
METAHEURISTICS = ['DEPSO', 'RBRS-AE', 'ALNS']
ALGORITHMS = BASELINES + METAHEURISTICS

# Kod durumu kontrolünde sayılmayan yollar: koşumların kendi çıktıları
_IGNORED = [':(exclude)results', ':(exclude)site/data']


# ── Kod sürümü ─────────────────────────────────────────────────────────

def git_state() -> dict:
    """{'commit': kısa hash, 'dirty': bool, 'files': değişmiş izlenen dosyalar}."""
    def run(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL)
    try:
        commit = run('rev-parse', '--short', 'HEAD').strip()
        status = run('status', '--porcelain', '--untracked-files=no', '--', '.', *_IGNORED)
    except Exception:
        return {'commit': 'bilinmiyor', 'dirty': None, 'files': []}
    files = [line[3:] for line in status.splitlines() if line.strip()]
    return {'commit': commit, 'dirty': bool(files), 'files': files}


def require_clean(allow_dirty: bool) -> dict:
    """Kod commit'lenmemiş değişiklik içeriyorsa koşumu durdur (izin verilmedikçe)."""
    state = git_state()
    if state['dirty'] and not allow_dirty:
        print("HATA: commit'lenmemiş değişiklikler var; sonuç hangi kodla alındığı "
              "bilinmeyen bir sürüme ait olur:")
        for f in state['files']:
            print(f"    {f}")
        print("Önce commit'le ya da geri al (git status). Yalnızca deneme için: --allow-dirty")
        sys.exit(2)
    if state['dirty']:
        print(f"UYARI: commit'lenmemiş değişikliklerle koşuluyor ({len(state['files'])} dosya); "
              f"sonuç dosyasına 'dirty' olarak yazılacak.")
    return state


# ── Protokol ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Protocol:
    depso_iter: int = 500
    n_seeds: int = 1                  # örnek başına optimizer tohumu
    time_budget: float | None = None     # sn; verilirse üç algoritma da bu süre kadar çalışır
    time_per_order: float | None = None  # sn/sipariş; bütçe = bu × k (büyük örneğe daha çok süre)

    def __post_init__(self):
        if self.time_budget is not None and self.time_per_order is not None:
            raise ValueError("time_budget ve time_per_order birlikte verilemez")

    def budget_for(self, k: int) -> float | None:
        if self.time_per_order is not None:
            return self.time_per_order * k
        return self.time_budget

    @property
    def budgeted(self) -> bool:
        return self.time_budget is not None or self.time_per_order is not None

    @property
    def tag(self) -> str:
        """Checkpoint/çıktı adı eki; varsayılan protokolde boş (eski dosyalarla uyumlu)."""
        t = f"__s{self.n_seeds}" if self.n_seeds != 1 else ""
        if self.time_budget is not None:
            t += f"__t{self.time_budget:g}"
        if self.time_per_order is not None:
            t += f"__tpo{self.time_per_order:g}"
        return t

    @property
    def is_default(self) -> bool:
        return self.n_seeds == 1 and not self.budgeted

    def describe(self) -> str:
        if self.time_per_order is not None:
            b = f"sipariş başına {self.time_per_order:g} sn eşit süre bütçesi"
        elif self.time_budget is not None:
            b = f"örnek başına {self.time_budget:g} sn eşit süre bütçesi"
        else:
            b = f"iterasyon sınırlı (DEPSO {self.depso_iter})"
        return f"{b}, {self.n_seeds} tohum"

    def to_dict(self) -> dict:
        return asdict(self)


def seed_for(base: int, j: int) -> int:
    """j. tekrarın tohumu; j = 0 eski tek tohumlu koşumlarla aynı."""
    return base + 7919 * j


def make_algorithms(seed: int, depso_iter: int, time_budget: float | None = None) -> dict:
    from algorithms.alns import ALNS
    from algorithms.depso import DEPSO
    from algorithms.rbrs_ae import RBRS_AE
    from benchmarks.fcfs import FCFS
    from benchmarks.sop import SOP
    algos = {
        'SOP':     SOP(),
        'FCFS':    FCFS(),
        'DEPSO':   DEPSO(num_iterations=depso_iter, seed=seed),
        'RBRS-AE': RBRS_AE(seed=seed),
        'ALNS':    ALNS(seed=seed),
    }
    if time_budget is not None:
        for a in METAHEURISTICS:
            algos[a].time_limit = time_budget
    return algos


def solve_all(orders, warehouse, seed: int, proto: Protocol) -> dict:
    """
    SOP ve FCFS deterministik: bir kez. Metasezgiseller proto.n_seeds tohumla;
    'td' ve 'rt' tohumların ortalaması, ham değerler 'td_seeds' / 'rt_seeds'.
    """
    out = {}
    budget = proto.budget_for(len(orders))
    base = make_algorithms(seed, proto.depso_iter, budget)
    for alg in BASELINES:
        sol = base[alg].solve(orders, warehouse)
        out[alg] = {'td': sol.total_travel_distance, 'rt': sol.runtime_seconds,
                    'batches': sol.num_batches}
    runs = {a: [] for a in METAHEURISTICS}
    for j in range(proto.n_seeds):
        algos = base if j == 0 else make_algorithms(seed_for(seed, j), proto.depso_iter, budget)
        for alg in METAHEURISTICS:
            sol = algos[alg].solve(orders, warehouse)
            runs[alg].append((sol.total_travel_distance, sol.runtime_seconds,
                              sol.num_batches, sol.iterations_used))
    for alg, rs in runs.items():
        out[alg] = {'td': statistics.fmean(r[0] for r in rs),
                    'rt': statistics.fmean(r[1] for r in rs),
                    'batches': rs[0][2],
                    'td_seeds': [round(r[0], 3) for r in rs],
                    'rt_seeds': [round(r[1], 3) for r in rs],
                    'iters': [r[3] for r in rs]}
    return out


# ── İstatistik ─────────────────────────────────────────────────────────

def wilcoxon(x: list[float], y: list[float]) -> dict:
    """
    Eşleştirilmiş örneklerde Wilcoxon işaretli sıralar testi (iki yönlü).
    x[i] ve y[i] aynı örneğin iki algoritmadaki mesafesi.
    """
    from scipy.stats import wilcoxon as _w
    diffs = [a - b for a, b in zip(x, y)]
    nz = [d for d in diffs if abs(d) > 1e-9]
    res = {'n': len(diffs), 'x_better': sum(d < 0 for d in nz), 'y_better': sum(d > 0 for d in nz),
           'ties': len(diffs) - len(nz), 'p': None}
    if len(nz) >= 6:
        res['p'] = float(_w(x, y, zero_method='wilcox', alternative='two-sided').pvalue)
    return res


def fmt_p(p) -> str:
    if p is None:
        return "—"
    return "< 0,001" if p < 0.001 else f"{p:.3f}".replace('.', ',')
