"""
algorithms/relocation.py
========================
Dinamik yer ataması (relocation) — Kübler, Glock ve Bauernhansl (2020), Bölüm 5.3.

Her dönemin sonunda:

5.3.1 Sınıflandırma
    Gerçekleşen (t-1) ve tahmin edilen (t, ..., t+U_for-1) satır sayılarına
    göre ABC sınıfları ve sınıf sınırları (A/B sınırı = son A ürününün satır
    sayısı, B/C sınırı = son B ürününün). Ürün yanlış sınıftaysa sayaç artar.
    Aday: en az `o` dönemdir yanlış sınıfta VE tahmine göre hedef sınıfta en
    az `u` dönem kalacak (U_tar ≥ u).

5.3.2 Öncelik
    d_{m,relCL,r} = |satır_m,r − sınır_relCL,r|; PV_m = Σ_{r=t}^{t+U_tar−1} d.
    relCL: ürünün mevcut sınıfı ile hedef sınıfı arasındaki sınır (yükselen
    ürün için hedef sınıfın alt sınırı, düşen ürün için mevcut sınıfın alt
    sınırı). Liste PV'ye göre azalan.

5.3.3 Yer kontrolü
    FV_cl = boş + boşalabilecek − dolabilecek. Negatifse o sınıfa girecek en
    düşük PV'li ürünler listeden çıkarılır.

5.3.4 Taşıma kuralı
    Listedeki ilk yükselen ürün. Senaryo 1: hedef sınıfta boş yer. Senaryo 2:
    doğrudan takas (hedef sınıftan, mevcut sınıfa inecek ürünle). Senaryo 3:
    dolaylı takas (hedef sınıftan bir ürün üçüncü sınıfın boş yerine).
    Senaryo 4: üç ürünlü döngü. Öncelik 1 > {2, 3 rastgele} > 4. Düşen ürün:
    ilgili sınıfta en yüksek PV'li, eşitlikte kapıya en yakın.

5.3.5 Verimlilik
    Efor: her taşınan ürün için (mevcut → hedef mesafe) + t_phy·v + t_adm·v.
    Tdr_{t-1} = Td_com − Td_rel. Tdr ≤ 0 ise ret. Değilse
    λ = Tdr / d_rel_{t-1}, gelecek kazanç Σ_r λ·d_rel_r (yalnızca yükselen
    ürünün serisi); kazanç > efor ise kabul, Td_com ← Td_rel.

MAKALEDEN BİLİNÇLİ SAPMA (docs/RELOCATION.md)
    Makale Td_rel'i her öneri için dönemin tüm siparişlerini DEPSO ile yeniden
    çözerek hesaplar. Burada dönemin siparişleri seçilen algoritmayla BİR KEZ
    gruplanır; öneri denenirken gruplar sabit tutulur ve yalnızca taşınan
    ürünün geçtiği grupların rotası (NN + 2-opt) yeniden hesaplanır. Bu,
    9 dönemlik deneyi günlerden dakikalara indirir. Sapmanın büyüklüğü
    `validate_approximation` ile ölçülür.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from config import DYNAMIC_STORAGE, ITEMS
from core.data_loader import Order, OrderLine
from core.forecasting import ItemForecaster
from algorithms.routing.route_cache import RouteCache

CLASS_RANK = {'A': 0, 'B': 1, 'C': 2}
RANK_CLASS = 'ABC'

# batch_fn(orders, warehouse) -> list[list[Order]]  (algoritmanın gruplaması)
BatchFn = Callable[[list[Order], object], list[list[Order]]]


# ════════════════════════════════════════════════════════════════════════════
# SINIFLANDIRMA
# ════════════════════════════════════════════════════════════════════════════

def abc_with_limits(values: np.ndarray, class_pct: dict) -> tuple[np.ndarray, dict]:
    """
    ABC sınıfı (0=A, 1=B, 2=C) ve sınırlar: {'A': son A ürününün değeri,
    'B': son B ürününün değeri}. Eşitlikte düşük ürün numarası önce.
    """
    n = len(values)
    order = np.lexsort((np.arange(n), -np.asarray(values, dtype=float)))
    n_a = int(n * class_pct['A'])
    n_b = int(n * class_pct['B'])
    cls = np.full(n, 2, dtype=np.int8)
    cls[order[:n_a]] = 0
    cls[order[n_a:n_a + n_b]] = 1
    limits = {'A': float(values[order[n_a - 1]]) if n_a else float('inf'),
              'B': float(values[order[n_a + n_b - 1]]) if n_a + n_b else float('inf')}
    return cls, limits


def relevant_limit(current: int, target: int) -> str:
    """Mevcut ve hedef sınıf arasındaki ilgili sınır ('A' ya da 'B')."""
    if target < current:                       # yükselen: hedefin alt sınırı
        return RANK_CLASS[target]
    return RANK_CLASS[current]                 # düşen: mevcut sınıfın alt sınırı


# ════════════════════════════════════════════════════════════════════════════
# SONUÇ TİPLERİ
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Move:
    item: int
    src: int
    dst: int
    src_class: str
    dst_class: str


@dataclass
class Suggestion:
    scenario: int
    moves: list[Move]
    effort: float = 0.0
    tdr: float = 0.0
    future_gain: float = 0.0
    accepted: bool = False
    reason: str = ''


@dataclass
class PeriodRelocation:
    period: int
    candidates: int = 0
    tested: int = 0
    accepted: int = 0
    effort_LU: float = 0.0
    td_before_LU: float = 0.0      # bu dönemin siparişleri, taşıma öncesi
    td_after_LU: float = 0.0       # aynı siparişler, kabul edilen taşımalarla
    suggestions: list[Suggestion] = field(default_factory=list)

    @property
    def relocated_items(self) -> int:
        return sum(len(s.moves) for s in self.suggestions if s.accepted)


# ════════════════════════════════════════════════════════════════════════════
# ANA SINIF
# ════════════════════════════════════════════════════════════════════════════

class DynamicRelocation:
    """
    Kullanım (bkz. run_dynamic.py):

        reloc = DynamicRelocation(warehouse, zones, initial_locations, demand, warmup)
        for p in test_periods:
            ... dönemi çöz ...
            res = reloc.run_period(p, period_orders, batch_fn)
    """

    E_PHY = ITEMS['physical_effort_LU']   # 180 LU
    E_ADM = ITEMS['admin_effort_LU']      # 60 LU

    def __init__(self, warehouse, zones: dict[str, list[int]],
                 initial_locations, demand: np.ndarray, warmup: int,
                 cfg: dict | None = None):
        self.wh = warehouse
        self.cfg = {**DYNAMIC_STORAGE, **(cfg or {})}
        self.o = self.cfg['min_periods_in_wrong_class_o']
        self.u = self.cfg['min_periods_in_target_class_u']
        self.U_for = self.cfg['forecast_horizon']
        self.max_suggestions = self.cfg['max_relocation_suggestions']
        self.rng = random.Random(self.cfg['seed'])

        self.demand = np.asarray(demand, dtype=float)
        self.n_items = self.demand.shape[0]
        self.class_pct = warehouse.class_pct

        # Lokasyon → sınıf ve sınıf bölgeleri
        self.zone_of = {}
        for c, locs in zones.items():
            for l in locs:
                self.zone_of[int(l)] = CLASS_RANK[c]
        self.loc = np.asarray(initial_locations, dtype=np.int64).copy()
        self.item_at = {int(l): i for i, l in enumerate(self.loc)}
        self.empty = {r: set() for r in range(3)}
        for l, r in self.zone_of.items():
            if l not in self.item_at:
                self.empty[r].add(l)
        # o eşiği için geçmiş: ısınma dönemlerinde ürünler başlangıç yerinde
        # durur; "son dönemde de yanlış sınıftaydı" koşulu ilk test döneminin
        # sonunda da değerlendirilebilsin (makale Tab. 3: 1. dönemde taşıma var).
        self.wrong_count = np.zeros(self.n_items, dtype=np.int32)
        cur0 = np.array([self.zone_of[int(l)] for l in self.loc])
        for t in range(warmup):
            cls_t, _ = abc_with_limits(self.demand[:, t], self.class_pct)
            self.wrong_count = np.where(cls_t != cur0, self.wrong_count + 1, 0)

        # Holt-Winters: ısınma dönemleriyle kurulur, her dönem sonunda güncellenir
        self.forecaster = ItemForecaster()
        self.forecaster.fit_all(self.demand, warmup_periods=warmup)
        self._last_update = warmup - 1

    # ── yardımcılar ───────────────────────────────────────────────────
    def current_class(self, i: int) -> int:
        return self.zone_of[int(self.loc[i])]

    def remap(self, orders: list[Order]) -> list[Order]:
        """Siparişlerin lokasyonlarını ürünlerin ŞU ANKİ yerine göre güncelle."""
        out = []
        for o in orders:
            lines = [OrderLine(item=l.item, quantity=l.quantity,
                               location=int(self.loc[l.item]), weight=l.weight)
                     for l in o.orderlines]
            out.append(Order(order_id=o.order_id, num_orderlines=o.num_orderlines,
                             total_weight=o.total_weight, orderlines=lines))
        return out

    def _advance_forecaster(self, period: int) -> None:
        """Tahminciyi `period` dahil gerçekleşen talebe kadar ilerlet."""
        for t in range(self._last_update + 1, period + 1):
            self.forecaster.update_all(self.demand[:, t])
        self._last_update = max(self._last_update, period)

    # ══════════════════════════════════════════════════════════════════
    # DÖNEM SONU
    # ══════════════════════════════════════════════════════════════════

    def run_period(self, period: int, period_orders: list[list[Order]],
                   batch_fn: BatchFn | None = None,
                   batches: list[list[list[Order]]] | None = None,
                   tdr_scale: float = 1.0) -> PeriodRelocation:
        """
        period: biten dönemin (t-1) mutlak indeksi.
        period_orders: o dönemin siparişleri, alt dönemlere bölünmüş.
        batches: alt dönem başına algoritmanın grupları (varsa yeniden
            gruplanmaz). Yoksa batch_fn ile bir kez gruplanır.
        tdr_scale: dönemin yalnızca bir kısmı çözüldüyse (hızlı deneme)
            Tdr'yi tüm döneme ölçekler; kabul kararında kullanılır.
        """
        res = PeriodRelocation(period=period)
        self._advance_forecaster(period)

        realized = self.demand[:, period]
        cls_now, lim_now = abc_with_limits(realized, self.class_pct)
        horizon = [np.asarray(self.forecaster.predict_all(tau), dtype=float)
                   for tau in range(1, self.U_for + 1)]
        fc = [abc_with_limits(v, self.class_pct) for v in horizon]

        cur = np.array([self.current_class(i) for i in range(self.n_items)])
        wrong = cls_now != cur
        self.wrong_count = np.where(wrong, self.wrong_count + 1, 0)

        # 5.3.1-5.3.2 adaylar ve öncelik
        cand = []
        for i in np.flatnonzero(self.wrong_count >= self.o):
            target = int(cls_now[i])
            u_tar = 0
            for cls_r, _ in fc:
                if cls_r[i] == target:
                    u_tar += 1
                else:
                    break
            if u_tar < self.u:
                continue
            key = relevant_limit(int(cur[i]), target)
            pv = sum(abs(horizon[r][i] - fc[r][1][key]) for r in range(u_tar))
            cand.append({'item': int(i), 'cur': int(cur[i]), 'target': target,
                         'pv': float(pv), 'u_tar': u_tar, 'key': key})
        cand.sort(key=lambda c: (-c['pv'], c['item']))
        res.candidates = len(cand)

        # 5.3.3 yer kontrolü
        cand = self._feasible(cand)

        # Td_com: dönemin siparişleri, bir kez gruplanmış, mevcut yerleşimle
        if batches is None:
            if batch_fn is None:
                raise ValueError("batch_fn ya da batches verilmeli")
            batches = [batch_fn(self.remap(sub), self.wh) for sub in period_orders if sub]
        groups = [[{l.item for o in b for l in o.orderlines} for b in sub] for sub in batches]
        groups = [g for sub in groups for g in sub]
        routes = RouteCache(self.wh)
        td = [routes.distance([int(self.loc[i]) for i in g]) for g in groups]
        groups_of_item: dict[int, list[int]] = {}
        for gi, g in enumerate(groups):
            for i in g:
                groups_of_item.setdefault(i, []).append(gi)
        td_com = sum(td)
        res.td_before_LU = td_com

        # 5.3.4-5.3.5 önerileri sırayla dene
        tested = 0
        while cand and tested < self.max_suggestions:
            asc_idx = next((k for k, c in enumerate(cand) if c['target'] < c['cur']), None)
            if asc_idx is None:
                break
            asc = cand.pop(asc_idx)
            sug = self._build_suggestion(asc, cand)
            tested += 1
            if sug is None:
                res.suggestions.append(Suggestion(0, [], reason='uygun takas yok'))
                continue
            for mv in sug.moves:                     # ilgili ürünler listeden çıkar
                cand[:] = [c for c in cand if c['item'] != mv.item]

            sug.effort = sum(self.wh.distance(mv.src, mv.dst) + self.E_PHY + self.E_ADM
                             for mv in sug.moves)
            affected = sorted({gi for mv in sug.moves for gi in groups_of_item.get(mv.item, [])})
            new_loc = {mv.item: mv.dst for mv in sug.moves}
            new_td = {gi: routes.distance([new_loc.get(i, int(self.loc[i])) for i in groups[gi]])
                      for gi in affected}
            td_rel = td_com - sum(td[gi] for gi in affected) + sum(new_td.values())
            sug.tdr = td_com - td_rel

            if sug.tdr <= 0:
                sug.reason = 'bu dönemde kazanç yok'
            else:
                d_prev = abs(realized[asc['item']] - lim_now[asc['key']])
                rel_prev = 100.0 * d_prev / lim_now[asc['key']] if lim_now[asc['key']] > 0 else 0.0
                if rel_prev <= 0:
                    sug.reason = 'göreli uzaklık sıfır'
                else:
                    lam = sug.tdr * tdr_scale / rel_prev
                    gain = 0.0
                    for r in range(asc['u_tar']):
                        lim_r = fc[r][1][asc['key']]
                        if lim_r > 0:
                            gain += lam * 100.0 * abs(horizon[r][asc['item']] - lim_r) / lim_r
                    sug.future_gain = gain
                    if gain > sug.effort:
                        sug.accepted = True
                        sug.reason = 'kabul'
                        self._apply(sug)
                        for gi, v in new_td.items():
                            td[gi] = v
                        td_com = td_rel
                        res.accepted += 1
                        res.effort_LU += sug.effort
                    else:
                        sug.reason = 'kazanç < efor'
            res.suggestions.append(sug)

        res.tested = tested
        res.td_after_LU = td_com
        return res

    # ── 5.3.3 ─────────────────────────────────────────────────────────
    def _feasible(self, cand: list[dict]) -> list[dict]:
        cand = list(cand)
        while True:
            fv = {}
            for r in range(3):
                leaving = sum(1 for c in cand if c['cur'] == r)
                entering = sum(1 for c in cand if c['target'] == r)
                fv[r] = len(self.empty[r]) + leaving - entering
            worst = min(fv, key=lambda r: fv[r])
            if fv[worst] >= 0:
                return cand
            entering = sorted((c for c in cand if c['target'] == worst), key=lambda c: c['pv'])
            drop = {c['item'] for c in entering[:-fv[worst]]}
            cand = [c for c in cand if c['item'] not in drop]

    # ── 5.3.4 ─────────────────────────────────────────────────────────
    def _pick_desc(self, cand, now_in: int, goes_to: int):
        pool = [c for c in cand if c['cur'] == now_in and c['target'] == goes_to]
        if not pool:
            return None
        depot = self.wh.DEPOT
        return max(pool, key=lambda c: (c['pv'], -self.wh.distance(depot, int(self.loc[c['item']]))))

    def _nearest_empty(self, r: int):
        if not self.empty[r]:
            return None
        depot = self.wh.DEPOT
        return min(self.empty[r], key=lambda l: (self.wh.distance(depot, l), l))

    def _build_suggestion(self, asc: dict, cand: list[dict]) -> Suggestion | None:
        i, C, T = asc['item'], asc['cur'], asc['target']
        X = 3 - C - T                              # üçüncü sınıf
        src = int(self.loc[i])
        mv = lambda item, dst, a, b: Move(item, int(self.loc[item]), int(dst), RANK_CLASS[a], RANK_CLASS[b])

        # 1: hedef sınıfta boş yer (kapıya en yakın boş yer)
        e = self._nearest_empty(T)
        if e is not None:
            return Suggestion(1, [mv(i, e, C, T)])

        options = []
        d2 = self._pick_desc(cand, T, C)
        if d2 is not None:
            j = d2['item']
            options.append(Suggestion(2, [mv(i, self.loc[j], C, T), mv(j, src, T, C)]))
        d3 = self._pick_desc(cand, T, X)
        e3 = self._nearest_empty(X)
        if d3 is not None and e3 is not None:
            j = d3['item']
            options.append(Suggestion(3, [mv(i, self.loc[j], C, T), mv(j, e3, T, X)]))
        if options:
            return self.rng.choice(options)

        # 4: i → T (j1'in yeri), j1 → X (j2'nin yeri), j2 → C (i'nin yeri)
        d4a = self._pick_desc(cand, T, X)
        d4b = self._pick_desc(cand, X, C)
        if d4a is not None and d4b is not None:
            j1, j2 = d4a['item'], d4b['item']
            return Suggestion(4, [mv(i, self.loc[j1], C, T), mv(j1, self.loc[j2], T, X),
                                  mv(j2, src, X, C)])
        return None

    def _apply(self, sug: Suggestion) -> None:
        srcs = {mv.src for mv in sug.moves}
        dsts = {mv.dst for mv in sug.moves}
        for l in srcs - dsts:                      # boşalan yerler
            self.item_at.pop(l, None)
            self.empty[self.zone_of[l]].add(l)
        for mv in sug.moves:
            self.empty[self.zone_of[mv.dst]].discard(mv.dst)
            self.loc[mv.item] = mv.dst
            self.item_at[mv.dst] = mv.item
            self.wrong_count[mv.item] = 0


# ════════════════════════════════════════════════════════════════════════════
# YAKLAŞIMIN DOĞRULANMASI
# ════════════════════════════════════════════════════════════════════════════

def validate_approximation(reloc: DynamicRelocation, period_orders: list[list[Order]],
                           solve_fn: Callable[[list[Order], object], tuple[float, list[list[Order]]]],
                           suggestions: list[Suggestion]) -> list[dict]:
    """
    Her öneri için bu dönemdeki mesafe kazancını (Tdr) iki yolla hesaplar,
    ikisi de AYNI başlangıç yerleşiminden:

      yaklaşık: algoritmanın grupları sabit, yalnızca etkilenen grupların
                rotası yeniden hesaplanır (bu modülün yöntemi)
      tam:      taşıma uygulanmış yerleşimle algoritma dönemi baştan çözer
                (makaledeki yöntem)

    solve_fn(orders, wh) -> (toplam mesafe, gruplar). Yerleşim değişmez.
    """
    wh = reloc.wh
    base = [solve_fn(reloc.remap(sub), wh) for sub in period_orders if sub]
    base_total = sum(d for d, _ in base)
    groups = [{l.item for o in g for l in o.orderlines} for _, gs in base for g in gs]
    routes = RouteCache(wh)
    out = []
    for sug in suggestions:
        if not sug.moves:
            continue
        new_loc = {mv.item: mv.dst for mv in sug.moves}
        approx = 0.0
        for g in groups:
            if g & new_loc.keys():
                before = routes.distance([int(reloc.loc[i]) for i in g])
                after = routes.distance([new_loc.get(i, int(reloc.loc[i])) for i in g])
                approx += before - after
        saved = reloc.loc.copy()
        for mv in sug.moves:
            reloc.loc[mv.item] = mv.dst
        full_total = sum(solve_fn(reloc.remap(sub), wh)[0] for sub in period_orders if sub)
        reloc.loc[:] = saved
        out.append({'scenario': sug.scenario, 'tdr_approx': round(approx, 2),
                    'tdr_full': round(base_total - full_total, 2)})
    return out
