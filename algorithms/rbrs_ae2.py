"""
algorithms/rbrs_ae2.py
======================
RBRS-AE'nin iyileştirme denemeleri (ablation için seçenekli).

Özgün RBRS-AE (algorithms/rbrs_ae.py) DEĞİŞMEDİ; bu sınıf onu genişletir.
Her seçeneğin varsayılanı özgün davranıştır; böylece her iyileştirmenin
katkısı ayrı ayrı ölçülebilir (experiments/rbrs_ablation.py).

Seçenekler
----------
repair   'greedy' (özgün): serbest kalan siparişler sırayla en ucuz gruba.
         'regret'        : regret-2 ile yerleştirme (adındaki "regret" fikrinin
                           eleme adımına da uygulanması), öncelik ağırlıklı.
destroy  'worst' (özgün): I(b) skoru en kötü grupları yık.
         'mix'           : her iterasyonda rastgele biri: en kötü gruplar /
                           ilişkili siparişler (konumca yakın, Shaw) / rastgele
                           gruplar. Çok satırlı siparişlerde yakınlık bilgisi
                           önemli; özgün kural yalnızca grup skoruna bakıyor.
accept   'walk' (özgün) : her iterasyonun sonucu, kötü olsa da yeni başlangıç.
         'threshold'     : sonuç en iyiden %τ'dan fazla kötüyse en iyiye dön
                           (τ, %3'ten 0'a iner; record-to-record).
moves    'random' (özgün): takas için gruplar rastgele seçilir.
         'near'          : takas eşi, merkezi en yakın birkaç gruptan seçilir.
final    'full' (özgün)  : son iyileştirmede tüm sipariş çiftleri (O(n²) rota).
         'near'          : yalnızca yakın grup çiftleri, ilk iyileşme kabul.
size     'orig' (özgün) : yıkılan pay %20 → %10 (sipariş).
         'small'         : %10 → %5, en az 2, en çok 30 sipariş (ALNS ile aynı ölçek).
ls       'every' (özgün): her iterasyonda shift + swap.
         'sparse'        : shift + swap yalnızca yeni en iyi bulununca ya da 5
                           iterasyonda bir; kalan süre yıkım-onarıma gider.
"""

from __future__ import annotations

import math
import random

from algorithms.base import Batch, Solution
from algorithms.rbrs_ae import RBRS_AE, _ROUTE_STALE
from algorithms.routing.route_cache import RouteCache

OPTIONS = {
    'repair': ('greedy', 'regret'),
    'destroy': ('worst', 'mix'),
    'accept': ('walk', 'threshold'),
    'moves': ('random', 'near'),
    'final': ('full', 'near'),
    'size': ('orig', 'small'),
    'ls': ('every', 'sparse'),
}
IMPROVED = {'repair': 'regret', 'destroy': 'mix', 'accept': 'threshold',
            'moves': 'near', 'final': 'near', 'size': 'small', 'ls': 'sparse'}
# Küçük deneme setinde (docs/RBRS_AE2.md) yalnızca bu ikisi açık fark yarattı;
# diğerleri etkisiz ya da zararlı çıktı.
RECOMMENDED = {'destroy': 'mix', 'repair': 'regret'}


class RBRS_AE2(RBRS_AE):
    NEAR_K = 4            # yakın grup sayısı
    TAU0 = 0.03           # threshold kabulünde başlangıç toleransı

    @classmethod
    def recommended(cls, **kw):
        return cls(label='RBRS-AE2', **RECOMMENDED, **kw)

    def __init__(self, label: str | None = None, **kw):
        opts = {k: kw.pop(k, OPTIONS[k][0]) for k in OPTIONS}
        for k, v in opts.items():
            if v not in OPTIONS[k]:
                raise ValueError(f"{k}={v!r}; seçenekler {OPTIONS[k]}")
        super().__init__(**kw)
        self.opts = opts
        self._label = label

    @property
    def name(self) -> str:
        return self._label or "RBRS-AE2"

    # ── yardımcılar ───────────────────────────────────────────────────
    def _order_xy(self, o):
        if id(o) not in self._xy:
            pts = [self._wh.coords(l) for l in o.locations]
            self._xy[id(o)] = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        return self._xy[id(o)]

    def _batch_xy(self, b):
        pts = [self._order_xy(o) for o in b.orders]
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

    def _near_batches(self, batches, b, k):
        cx, cy = self._batch_xy(b)
        others = [(abs(cx - x) + abs(cy - y), i) for i, (x, y) in
                  ((i, self._batch_xy(o)) for i, o in enumerate(batches) if o is not b and o.orders)]
        others.sort()
        return [batches[i] for _, i in others[:k]]

    # ── ana döngü ─────────────────────────────────────────────────────
    def _solve_impl(self, orders, warehouse):
        self._wh = warehouse
        self._xy = {}
        if not orders:
            return Solution(self.name, [], 0.0)
        warehouse.build_problem_matrix(orders)
        self._routes = RouteCache(warehouse)
        priorities = self._priority_scores(orders)
        self._pri = {id(o): p for o, p in zip(orders, priorities)}

        batches = self._regret_assignment(orders, priorities)
        self._compute_routes(batches)
        best_dist = self._total_dist(batches)
        best_batches = self._clone(batches)
        self.convergence_history = [best_dist]

        no_imp = 0
        it = 0
        budget = self.time_limit is not None
        for it in range(1, self._iter_limit(self.max_iterations) + 1):
            if budget:
                if it > 1 and self._time_up(self.FINAL_SHARE_SPLIT):
                    it -= 1
                    break
            elif no_imp >= self.max_no_improvement:
                break
            prog = self._progress(it, self.max_iterations)

            if self.opts['ls'] == 'every' or it % 5 == 1 or no_imp == 0:
                batches, c1 = self._shift(batches)
                batches, c2 = (self._swap_near(batches) if self.opts['moves'] == 'near'
                               else self._swap(batches))
                if c1 or c2:
                    self._compute_routes(batches)

            elim_pct = (0.10 - 0.05 * prog) if self.opts['size'] == 'small' else (0.20 - 0.10 * prog)
            batches = self._destroy_repair(batches, orders, priorities, elim_pct)
            self._compute_routes(batches)

            dist = self._total_dist(batches)
            self.convergence_history.append(dist)
            if dist < best_dist - 1e-9:
                best_dist = dist
                best_batches = self._clone(batches)
                no_imp = 0
            else:
                no_imp += 1
                if self.opts['accept'] == 'threshold':
                    tau = self.TAU0 * (1.0 - prog)
                    if dist > best_dist * (1.0 + tau):
                        batches = self._clone(best_batches)

        final = self._clone(best_batches)
        for _ in range(15):
            if self._time_up():
                break
            if self.opts['final'] == 'near':
                final, c = self._final_near(final)
                if not c:
                    break
            else:
                final, c1 = self._final_shift(final)
                final, c2 = self._final_swap(final)
                if not c1 and not c2:
                    break
        self._compute_routes(final)
        fd = self._total_dist(final)
        if fd < best_dist - 1e-9:
            best_dist, best_batches = fd, final
        return Solution(algorithm_name=self.name, batches=best_batches,
                        total_travel_distance=best_dist, iterations_used=it,
                        convergence_history=self.convergence_history,
                        extra_info={'options': dict(self.opts)})

    # ── yıkım + onarım ────────────────────────────────────────────────
    def _destroy_repair(self, batches, orders, priorities, elim_pct):
        if self.opts['destroy'] == 'worst' and self.opts['repair'] == 'greedy':
            return self._eliminate(batches, orders, priorities, elim_pct)
        if len(batches) <= 2:
            return batches
        n_orders = sum(len(b.orders) for b in batches)
        q = max(2, int(round(elim_pct * n_orders)))
        if self.opts['size'] == 'small':
            q = min(q, 30)
        mode = 'worst' if self.opts['destroy'] == 'worst' else self._rng.choice(('worst', 'related', 'random'))

        if mode == 'worst':
            scored = sorted(batches, key=lambda b: (0.7 * b.travel_distance / max(len(b.orders), 1) +
                                                    0.3 * (1.0 - b.total_weight / self.capacity)),
                            reverse=True)
            n_b = max(1, int(len(scored) * elim_pct))
            drop = {id(b) for b in scored[:n_b]}
            freed = [o for b in batches if id(b) in drop for o in b.orders]
            kept = [b for b in batches if id(b) not in drop]
        else:
            all_o = [(o, b) for b in batches for o in b.orders]
            if mode == 'related':
                seed = self._rng.choice(all_o)[0]
                sx, sy = self._order_xy(seed)
                all_o.sort(key=lambda ob: abs(self._order_xy(ob[0])[0] - sx) +
                                          abs(self._order_xy(ob[0])[1] - sy))
                chosen = all_o[:q]
            else:
                chosen = self._rng.sample(all_o, min(q, len(all_o)))
            out = {id(o) for o, _ in chosen}
            freed = [o for o, _ in chosen]
            kept = []
            for b in batches:
                rest = [o for o in b.orders if id(o) not in out]
                if len(rest) == len(b.orders):
                    kept.append(b)
                elif rest:
                    nb = Batch(batch_id=b.batch_id, orders=rest,
                               total_weight=sum(o.total_weight for o in rest))
                    nb.travel_distance = self._route_cost(nb.locations)[1]
                    kept.append(nb)
        if not freed:
            return batches

        if self.opts['repair'] == 'regret':
            new = self._regret_insert(kept, freed)
        else:
            new = kept[:]
            for o in sorted(freed, key=lambda o: -self._pri.get(id(o), 0.5)):
                costs = self._insertion_costs(o, new)
                _, target = costs[0]
                if target == -1:
                    new.append(Batch(batch_id=len(new), orders=[o], total_weight=o.total_weight))
                else:
                    new[target].orders.append(o)
                    new[target].total_weight += o.total_weight
                    new[target].travel_distance = _ROUTE_STALE
        self._renumber(new)
        return new

    def _regret_insert(self, kept, freed):
        """Regret-2, öncelik ağırlıklı: score = (2. en iyi − en iyi) × (1 + öncelik)."""
        batches = kept[:]
        todo = list(freed)
        while todo:
            best = None
            for o in todo:
                costs = self._insertion_costs(o, batches)
                regret = costs[1][0] - costs[0][0] if len(costs) >= 2 else math.inf
                score = regret * (1.0 + self._pri.get(id(o), 0.5))
                if best is None or score > best[0]:
                    best = (score, o, costs[0][1])
            _, o, target = best
            todo.remove(o)
            if target == -1:
                b = Batch(batch_id=len(batches), orders=[o], total_weight=o.total_weight)
                b.travel_distance = self._route_cost(b.locations)[1]
                batches.append(b)
            else:
                b = batches[target]
                b.orders.append(o)
                b.total_weight += o.total_weight
                b.travel_distance = self._route_cost(b.locations)[1]
        return batches

    # ── yakın gruplarla takas ─────────────────────────────────────────
    def _swap_near(self, batches):
        if len(batches) < 2:
            return batches, False
        changed = False
        for _ in range(self.swap_attempts):
            b1 = self._rng.choice(batches)
            if not b1.orders:
                continue
            near = self._near_batches(batches, b1, self.NEAR_K)
            if not near:
                continue
            b2 = self._rng.choice(near)
            o1 = self._rng.choice(b1.orders)
            o2 = self._rng.choice(b2.orders)
            w1 = b1.total_weight - o1.total_weight + o2.total_weight
            w2 = b2.total_weight - o2.total_weight + o1.total_weight
            if w1 > self.capacity or w2 > self.capacity:
                continue
            l1 = [l for x in b1.orders if x is not o1 for l in x.locations] + o2.locations
            l2 = [l for x in b2.orders if x is not o2 for l in x.locations] + o1.locations
            d1 = self._route_cost(l1)[1]
            d2 = self._route_cost(l2)[1]
            if d1 + d2 < b1.travel_distance + b2.travel_distance - 1e-9:
                b1.orders.remove(o1); b1.orders.append(o2); b1.total_weight = w1; b1.travel_distance = d1
                b2.orders.remove(o2); b2.orders.append(o1); b2.total_weight = w2; b2.travel_distance = d2
                changed = True
        return batches, changed

    # ── son iyileştirme: yakın gruplar, ilk iyileşme ──────────────────
    def _final_near(self, batches):
        changed = False
        order = list(range(len(batches)))
        self._rng.shuffle(order)
        for i in order:
            if self._time_up():
                break
            b1 = batches[i]
            if not b1.orders:
                continue
            for b2 in self._near_batches(batches, b1, self.NEAR_K):
                done = False
                for o1 in list(b1.orders):
                    rest1 = [l for x in b1.orders if x is not o1 for l in x.locations]
                    d1_out = self._route_cost(rest1)[1] if rest1 else 0.0
                    # taşıma (shift)
                    if b2.total_weight + o1.total_weight <= self.capacity:
                        d2_in = self._route_cost(b2.locations + o1.locations)[1]
                        if d1_out + d2_in < b1.travel_distance + b2.travel_distance - 1e-9:
                            b1.orders.remove(o1); b1.total_weight -= o1.total_weight; b1.travel_distance = d1_out
                            b2.orders.append(o1); b2.total_weight += o1.total_weight; b2.travel_distance = d2_in
                            changed = done = True
                            break
                    # takas (swap)
                    for o2 in list(b2.orders):
                        w1 = b1.total_weight - o1.total_weight + o2.total_weight
                        w2 = b2.total_weight - o2.total_weight + o1.total_weight
                        if w1 > self.capacity or w2 > self.capacity:
                            continue
                        d1 = self._route_cost(rest1 + o2.locations)[1]
                        l2 = [l for x in b2.orders if x is not o2 for l in x.locations] + o1.locations
                        d2 = self._route_cost(l2)[1]
                        if d1 + d2 < b1.travel_distance + b2.travel_distance - 1e-9:
                            b1.orders.remove(o1); b1.orders.append(o2); b1.total_weight = w1; b1.travel_distance = d1
                            b2.orders.remove(o2); b2.orders.append(o1); b2.total_weight = w2; b2.travel_distance = d2
                            changed = done = True
                            break
                    if done:
                        break
                if done or not b1.orders:
                    break
        batches = [b for b in batches if b.orders]
        self._renumber(batches)
        return batches, changed
