"""
algorithms/alns.py
==================
ALNS: Adaptive Large Neighborhood Search (Ropke ve Pisinger, 2006).

Formülasyon: docs/ALNS_formulasyon.md. Denklem numaraları o belgeye aittir.

- Çözüm: siparişlerin ayrık gruplara bölünmesi (1), kapasite Q (2).
- Amaç: f(S) = Σ TD(B_k), TD = NN + 2-opt (ortak RouteCache) (3).
- Yıkma: random (4), worst (5)-(6), related / Shaw (7).
- Kurma: greedy (9), regret-2 (10). Ekleme maliyeti Δ (8).
- Adaptif ağırlıklar: rulet seçimi (11), puanlar σ1/σ2/σ3 (12),
  segment sonu güncelleme (13).
- Kabul: simulated annealing (14)-(16).

DEPSO ve RBRS-AE ile aynı temel sınıf, aynı kapasite ve aynı rota servisi
kullanılır; üç algoritma arasındaki tek fark arama stratejisidir.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_loader import Order
from algorithms.base import BatchingRoutingAlgorithm, Batch, Solution
from algorithms.routing.route_cache import RouteCache
from config import ALNS as ALNS_CONFIG, ITEMS

DESTROY_OPS = ('random', 'worst', 'related')
REPAIR_OPS = ('greedy', 'regret2')


class _State:
    """
    Hafif çözüm gösterimi: gruplar sipariş indekslerinin listesi.
    TD değerleri ortak rota servisinden okunur.
    """
    __slots__ = ('batches', 'weights', 'tds')

    def __init__(self, batches, weights, tds):
        self.batches: list[list[int]] = batches
        self.weights: list[float] = weights
        self.tds: list[float] = tds

    @property
    def cost(self) -> float:
        return sum(self.tds)

    def copy(self) -> '_State':
        return _State([b[:] for b in self.batches], self.weights[:], self.tds[:])


class ALNS(BatchingRoutingAlgorithm):

    def __init__(self, max_iterations=None, seed=None, verbose=False, **overrides):
        cfg = dict(ALNS_CONFIG)
        unknown = set(overrides) - set(cfg)
        if unknown:
            raise TypeError(f"Bilinmeyen ALNS parametresi: {sorted(unknown)}")
        cfg.update(overrides)
        if max_iterations is not None:
            cfg['max_iterations'] = max_iterations
        self.cfg = cfg
        self.max_iterations = cfg['max_iterations']
        self.capacity = ITEMS['picker_capacity_WU']
        self.verbose = verbose
        self._rng = random.Random(seed)

        # Çözüm sırasında doldurulur
        self._orders: list[Order] = []
        self._locs: list[list[int]] = []
        self._w: list[float] = []
        self._routes: RouteCache | None = None
        self.convergence_history: list[float] = []
        self.operator_log: dict = {}

    @property
    def name(self) -> str:
        return "ALNS"

    # ══════════════════════════════════════════════════════════════
    # ANA DÖNGÜ (Sözde kod, satır 1-27)
    # ══════════════════════════════════════════════════════════════

    def _solve_impl(self, orders: list[Order], warehouse) -> Solution:
        if not orders:
            return Solution(self.name, [], 0.0)

        warehouse.build_problem_matrix(orders)
        self._wh = warehouse
        self._routes = RouteCache(warehouse)
        self._orders = orders
        self._locs = [list(o.locations) for o in orders]
        self._w = [o.total_weight for o in orders]
        n = len(orders)

        cfg = self.cfg
        q_min = max(2, math.ceil(cfg['q_min_frac'] * n))
        q_max = min(cfg['q_max_abs'], max(q_min, math.ceil(cfg['q_max_frac'] * n)))
        q_min = min(q_min, n)
        q_max = min(q_max, n)
        # büyük örnekte (n > 600) %5 alt sınırı 30'luk üst sınırı aşar: üst sınır geçerli
        q_min = min(q_min, q_max)

        # 1-3: başlangıç çözümü (regret-2 ile boş çözümden), sıcaklık (16)
        cur = self._repair_regret2(_State([], [], []), list(range(n)))
        best = cur.copy()
        T = -(cfg['init_worse_pct'] * cur.cost) / math.log(0.5) if cur.cost > 0 else 1.0

        # 4-5: ağırlıklar, puanlar, kullanım sayıları
        w_d = {op: 1.0 for op in DESTROY_OPS}
        w_r = {op: 1.0 for op in REPAIR_OPS}
        pi_d = dict.fromkeys(DESTROY_OPS, 0.0); n_d = dict.fromkeys(DESTROY_OPS, 0)
        pi_r = dict.fromkeys(REPAIR_OPS, 0.0);  n_r = dict.fromkeys(REPAIR_OPS, 0)
        self.operator_log = {
            'weights_history': [{**w_d, **w_r}],
            'uses': dict.fromkeys(DESTROY_OPS + REPAIR_OPS, 0),
            'new_best': dict.fromkeys(DESTROY_OPS + REPAIR_OPS, 0),
        }
        self.convergence_history = [best.cost]

        it = 0
        for it in range(1, self._iter_limit(self.max_iterations) + 1):
            if it > 1 and self._time_up():
                it -= 1
                break
            d_op = self._roulette(w_d)                      # 7
            r_op = self._roulette(w_r)                      # 8
            q = self._rng.randint(q_min, q_max)             # 9

            partial, removed = self._destroy(d_op, cur.copy(), q)
            cand = self._repair(r_op, partial, removed)     # 10
            delta = cand.cost - cur.cost                    # 11

            if cand.cost < best.cost - 1e-9:                # 12-13
                best = cand.copy(); cur = cand; score = cfg['sigma1']
                self.operator_log['new_best'][d_op] += 1
                self.operator_log['new_best'][r_op] += 1
            elif cand.cost < cur.cost - 1e-9:               # 14-15
                cur = cand; score = cfg['sigma2']
            elif T > 0 and self._rng.random() < math.exp(-delta / T):   # 16-17
                cur = cand; score = cfg['sigma3']
            else:                                           # 18-19
                score = 0.0

            pi_d[d_op] += score; n_d[d_op] += 1             # 20-21
            pi_r[r_op] += score; n_r[r_op] += 1
            self.operator_log['uses'][d_op] += 1
            self.operator_log['uses'][r_op] += 1
            T *= cfg['cooling']                             # 22
            self.convergence_history.append(best.cost)

            if it % cfg['segment_length'] == 0:             # 23-26
                self._update_weights(w_d, pi_d, n_d)
                self._update_weights(w_r, pi_r, n_r)
                pi_d = dict.fromkeys(DESTROY_OPS, 0.0); n_d = dict.fromkeys(DESTROY_OPS, 0)
                pi_r = dict.fromkeys(REPAIR_OPS, 0.0);  n_r = dict.fromkeys(REPAIR_OPS, 0)
                self.operator_log['weights_history'].append({**w_d, **w_r})

            if self.verbose and it % 50 == 0:
                print(f"  [ALNS] iter {it:4d}: best={best.cost:.1f} cur={cur.cost:.1f} T={T:.2f}")

        return self._to_solution(best, it)                  # 27

    # ══════════════════════════════════════════════════════════════
    # MALİYET YARDIMCILARI
    # ══════════════════════════════════════════════════════════════

    def _batch_locs(self, batch: list[int]) -> list[int]:
        out = []
        for i in batch:
            out.extend(self._locs[i])
        return out

    def _td(self, batch: list[int]) -> float:
        return self._routes.distance(self._batch_locs(batch)) if batch else 0.0

    def _insertion_options(self, state: _State, i: int) -> list[tuple[float, int]]:
        """(8): Δ(o, B_k) her uygun grup için, Δ(o, ∅) yeni grup için (-1). Artan sıralı."""
        opts = []
        wi = self._w[i]
        for k, b in enumerate(state.batches):
            if state.weights[k] + wi <= self.capacity:
                opts.append((self._routes.distance(self._batch_locs(b) + self._locs[i])
                             - state.tds[k], k))
        opts.append((self._routes.distance(self._locs[i]), -1))
        opts.sort(key=lambda x: x[0])
        return opts

    def _insert(self, state: _State, i: int, k: int) -> None:
        if k == -1:
            state.batches.append([i])
            state.weights.append(self._w[i])
            state.tds.append(self._td([i]))
        else:
            state.batches[k].append(i)
            state.weights[k] += self._w[i]
            state.tds[k] = self._td(state.batches[k])

    def _remove(self, state: _State, pairs: list[tuple[int, int]]) -> list[int]:
        """pairs: (grup_indeksi, sipariş_indeksi). Boşalan gruplar silinir."""
        by_batch: dict[int, set[int]] = {}
        for k, i in pairs:
            by_batch.setdefault(k, set()).add(i)
        removed = []
        for k, ids in by_batch.items():
            state.batches[k] = [i for i in state.batches[k] if i not in ids]
            state.weights[k] = sum(self._w[i] for i in state.batches[k])
            state.tds[k] = self._td(state.batches[k])
            removed.extend(ids)
        keep = [k for k, b in enumerate(state.batches) if b]
        state.batches = [state.batches[k] for k in keep]
        state.weights = [state.weights[k] for k in keep]
        state.tds = [state.tds[k] for k in keep]
        return removed

    def _biased_index(self, size: int, p: float) -> int:
        """(6): ⌊y^p · |liste|⌋, y ~ U(0,1)."""
        return min(size - 1, int((self._rng.random() ** p) * size))

    # ══════════════════════════════════════════════════════════════
    # YIKMA OPERATÖRLERİ
    # ══════════════════════════════════════════════════════════════

    def _destroy(self, op: str, state: _State, q: int) -> tuple[_State, list[int]]:
        pairs = [(k, i) for k, b in enumerate(state.batches) for i in b]
        q = min(q, len(pairs))
        if op == 'random':
            chosen = self._rng.sample(pairs, q)                            # (4)
        elif op == 'worst':
            chosen = self._worst_pairs(state, pairs, q)
        else:
            chosen = self._related_pairs(state, pairs, q)
        removed = self._remove(state, chosen)
        return state, removed

    def _worst_pairs(self, state: _State, pairs, q):
        """
        (5): g(o, B_k) = TD(B_k) − TD(B_k \\ {o}); azalan sırada (6) ile seçim.
        Kazançlar bir kez hesaplanır, seçim tekrar yerine konmadan yapılır.
        """
        scored = []
        for k, i in pairs:
            rest = [j for j in state.batches[k] if j != i]
            scored.append((state.tds[k] - self._td(rest), (k, i)))
        scored.sort(key=lambda x: -x[0])
        cand = [pair for _, pair in scored]
        chosen = []
        for _ in range(q):
            chosen.append(cand.pop(self._biased_index(len(cand), self.cfg['p_worst'])))
        return chosen

    def _related_pairs(self, state: _State, pairs, q):
        """
        (7): rel(o, R) = (1/|L(o)|) Σ_{l∈L(o)} min_{r∈R} d(l, r).
        Tohum rastgele; sonra en yakın adaylar (6) ile eklenir.
        """
        dist = self._wh.dist_m
        cand = pairs[:]
        seed = cand.pop(self._rng.randrange(len(cand)))
        chosen = [seed]
        # Her aday lokasyon için R'ye en yakın mesafe, R büyüdükçe güncellenir
        mins = {}
        for k, i in cand:
            for l in self._locs[i]:
                if l not in mins:
                    mins[l] = min(dist(l, r) for r in self._locs[seed[1]])
        new_r = []
        while len(chosen) < q and cand:
            if new_r:
                for l in mins:
                    m = mins[l]
                    for r in new_r:
                        d = dist(l, r)
                        if d < m:
                            m = d
                    mins[l] = m
            ranked = sorted(cand, key=lambda ki: sum(mins[l] for l in self._locs[ki[1]])
                            / len(self._locs[ki[1]]))
            pick = ranked[self._biased_index(len(ranked), self.cfg['p_shaw'])]
            cand.remove(pick)
            chosen.append(pick)
            new_r = self._locs[pick[1]]
        return chosen

    # ══════════════════════════════════════════════════════════════
    # KURMA OPERATÖRLERİ
    # ══════════════════════════════════════════════════════════════

    def _repair(self, op: str, state: _State, removed: list[int]) -> _State:
        if op == 'greedy':
            return self._repair_greedy(state, removed)
        return self._repair_regret2(state, removed)

    def _repair_greedy(self, state: _State, unassigned: list[int]) -> _State:
        """(9): her adımda global en düşük Δ'lı (sipariş, hedef) çifti."""
        todo = list(unassigned)
        while todo:
            best = None
            for i in todo:
                c, k = self._insertion_options(state, i)[0]
                if best is None or c < best[0]:
                    best = (c, i, k)
            _, i, k = best
            self._insert(state, i, k)
            todo.remove(i)
        return state

    def _repair_regret2(self, state: _State, unassigned: list[int]) -> _State:
        """
        (10): regret = Δ(2) − Δ(1); en yüksek regret'li sipariş kendi en iyi
        hedefine. Tek seçeneği olan sipariş (yalnızca yeni grup) sonsuz regret
        alır, yani önce yerleştirilir. Eşitlikte düşük Δ(1) kazanır.
        """
        todo = list(unassigned)
        while todo:
            best = None
            for i in todo:
                opts = self._insertion_options(state, i)
                regret = opts[1][0] - opts[0][0] if len(opts) >= 2 else math.inf
                key = (regret, -opts[0][0])
                if best is None or key > best[0]:
                    best = (key, i, opts[0][1])
            _, i, k = best
            self._insert(state, i, k)
            todo.remove(i)
        return state

    # ══════════════════════════════════════════════════════════════
    # ADAPTİF AĞIRLIKLAR
    # ══════════════════════════════════════════════════════════════

    def _roulette(self, weights: dict[str, float]) -> str:
        """(11): p(φ) = w_φ / Σ w."""
        total = sum(weights.values())
        x = self._rng.random() * total
        acc = 0.0
        for op, w in weights.items():
            acc += w
            if x < acc:
                return op
        return op

    def _update_weights(self, w: dict, pi: dict, n: dict) -> None:
        """(13): w ← (1 − r)·w + r·(π/n), yalnızca kullanılan operatörler."""
        r = self.cfg['reaction']
        for op in w:
            if n[op] > 0:
                w[op] = (1 - r) * w[op] + r * (pi[op] / n[op])

    # ══════════════════════════════════════════════════════════════
    # ÇIKTI
    # ══════════════════════════════════════════════════════════════

    def _to_solution(self, state: _State, iterations: int | None = None) -> Solution:
        batches = []
        for k, idx in enumerate(state.batches):
            b = Batch(batch_id=k, orders=[self._orders[i] for i in idx],
                      total_weight=state.weights[k])
            b.route, b.travel_distance = self._routes.get(b.locations)
            batches.append(b)
        return Solution(
            algorithm_name=self.name,
            batches=batches,
            total_travel_distance=sum(b.travel_distance for b in batches),
            iterations_used=self.max_iterations if iterations is None else iterations,
            convergence_history=self.convergence_history,
            extra_info={
                'route_cache_size': len(self._routes),
                'operator_uses': dict(self.operator_log['uses']),
                'operator_new_best': dict(self.operator_log['new_best']),
                'final_weights': self.operator_log['weights_history'][-1],
            },
        )


if __name__ == "__main__":
    from core.data_loader import DataLoader
    from core.warehouse import Warehouse
    from algorithms.depso import DEPSO
    from algorithms.rbrs_ae import RBRS_AE

    loader = DataLoader()
    wh = Warehouse()
    orders = loader.load_orders(1, 1, 20).orders[:50]
    for algo in (ALNS(seed=42, verbose=True), RBRS_AE(seed=42), DEPSO(seed=42)):
        sol = algo.solve(orders, wh)
        print(f"{sol.algorithm_name:8s} {sol.total_travel_distance:8.1f} LU  "
              f"{sol.num_batches} grup  {sol.runtime_seconds:.1f}s")
