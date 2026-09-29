"""
core/kubler_generator.py
========================
Kübler, Glock & Bauernhansl (2020) veri üretim yönteminin yeniden kurulumu.

Makale veri seti vermiyor, yalnızca üretim yöntemini anlatıyor:
  Fig. 8   1. dönemin siparişleri (DEPSO deneyleriyle aynı yöntem)
  §6.3     ürün talebinin zaman serisi (trend + mevsimsellik + düzensiz bileşen)
  §6.3     hızlı ↔ yavaş ürün dönüşümü (Adım 1-10, S_prob eşiği)
  Fig. 10  t > 1 dönemlerin siparişleri
  Table 2  parametreler

Her adım aşağıda makaledeki adım numarasıyla işaretli. Makalede açık
bırakılan noktalarda seçtiğimiz yorum "YORUM:" ile belirtildi
(docs/KUBLER_VERI.md).

Kullanım:
    from core.kubler_generator import KublerSpec, generate_kubler
    data = generate_kubler(KublerSpec(scenario=1))
    data.demand            # (6000 × 21) ürün × dönem satır sayısı
    data.period_orders(12) # mutlak dönem 12 (1. test dönemi) → 20 alt dönem
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from core.data_loader import Order, OrderLine

# Table 2: senaryoya göre değişen parametreler
SCENARIOS = {1: {'Tf': 0.300, 'Sf': 0.150},     # yüksek dinamik
             2: {'Tf': 0.150, 'Sf': 0.075}}     # düşük dinamik


@dataclass(frozen=True)
class KublerSpec:
    scenario: int = 1
    seed: int = 0
    n_orders_p1: int = 5000        # N_ord^1
    n_maxol: int = 2               # N_maxol
    a_maxol: int = 6               # A_maxol
    access_frequency: float = 0.6  # AF: en çok çekilen %20 ürünün erişim payı
    n_items: int = 6000
    n_subperiods: int = 20
    n_periods: int = 21            # 12 ısınma + 9 test
    season_L: int = 12
    max_fluct_M: float = 2.0
    irregular_f: float = 0.025
    weight_range: tuple = (0.1, 1.0)
    class_items: tuple = (0.05, 0.15)   # A %5, B %15, C %80 (ürün sayısına göre)

    @property
    def Tf(self) -> float:
        return SCENARIOS[self.scenario]['Tf']

    @property
    def Sf(self) -> float:
        return SCENARIOS[self.scenario]['Sf']

    @property
    def name(self) -> str:
        return f"kubler_fig10_s{self.scenario}" + (f"_seed{self.seed}" if self.seed else "")


# ── Fig. 8: erişim fonksiyonu ──────────────────────────────────────────

def access_lines(total_lines: int, n_items: int, af: float) -> np.ndarray:
    """
    Z(y) = y^c, c = log10(AF) / log10(0.2)  (Reschke 2013).
    Z(y): en çok çekilen y oranındaki ürünlerin toplam erişim payı.
    Ürün m (sıra 1..n) payı Z(m/n) − Z((m−1)/n). Toplam korunarak
    en büyük kalan yöntemiyle tam sayıya yuvarlanır. Sonuç azalan sıralı.
    """
    c = math.log10(af) / math.log10(0.2)
    y = np.arange(n_items + 1) / n_items
    share = np.diff(y ** c)
    raw = share * total_lines
    lines = np.floor(raw).astype(np.int64)
    rest = total_lines - lines.sum()
    if rest > 0:
        lines[np.argsort(-(raw - lines), kind='stable')[:rest]] += 1
    return lines


# ── Siparişleri oluşturma (Fig. 8 ve Fig. 10 ortak) ────────────────────

def _order_sizes(rng, n_orders: int | None, total_lines: int | None, n_maxol: int) -> np.ndarray:
    """
    Fig. 8: N_ord sipariş, her birine U{1..N_maxol} satır.
    Fig. 10 (t>1): toplam satır sayısına ulaşana kadar yeni sipariş aç;
    YORUM: son sipariş kalan satır sayısına kırpılır.
    """
    if n_orders is not None:
        return rng.integers(1, n_maxol + 1, n_orders)
    sizes = []
    left = int(total_lines)
    while left > 0:
        s = min(int(rng.integers(1, n_maxol + 1)), left)
        sizes.append(s)
        left -= s
    return np.array(sizes, dtype=np.int64)


def _distribute(rng, item_lines: np.ndarray, sizes: np.ndarray) -> list[list[int]]:
    """
    Ürünlerin satırlarını siparişlere rastgele dağıt; bir ürün bir siparişte
    en fazla bir kez (Fig. 8). Önce karıştırılmış yuvalara sırayla yerleştir,
    sonra aynı siparişe düşen tekrarları rastgele takasla düzelt.
    """
    n_orders = len(sizes)
    slot_order = np.repeat(np.arange(n_orders), sizes)
    rng.shuffle(slot_order)
    slot_item = np.repeat(np.arange(len(item_lines)), item_lines)
    assert len(slot_item) == len(slot_order), "satır sayıları tutmuyor"

    # sipariş → ürün kümesi
    content = [set() for _ in range(n_orders)]
    dup = []
    for pos, (o, it) in enumerate(zip(slot_order.tolist(), slot_item.tolist())):
        if it in content[o]:
            dup.append(pos)
        else:
            content[o].add(it)

    n = len(slot_order)
    dup_set = set(dup)
    for pos in dup:
        it, o = int(slot_item[pos]), int(slot_order[pos])
        for _ in range(10 * n):
            q = int(rng.integers(n))
            o2, it2 = int(slot_order[q]), int(slot_item[q])
            if o2 == o or it in content[o2] or it2 in content[o] or q in dup_set:
                continue
            content[o2].discard(it2)
            content[o2].add(it)
            content[o].add(it2)
            slot_order[pos], slot_order[q] = o2, o
            break
        else:
            raise RuntimeError("tekrar eden satır düzeltilemedi")

    orders = [[] for _ in range(n_orders)]
    for o, it in zip(slot_order.tolist(), slot_item.tolist()):
        orders[o].append(it)
    return orders


# ── §6.3: talep zaman serisi ve hızlı ↔ yavaş dönüşümü ────────────────

def demand_series(spec: KublerSpec, lines_p1: np.ndarray, rng) -> tuple[np.ndarray, dict]:
    """
    Her ürün için U dönemlik satır sayısı:
      N_m,t = round(N_m,1 + T_m·(t−1) + S_m·cos(2π(t−1)/L) + Ir_m,t)
      T_m = Tf·N_m,1·rand,  S_m = Sf·N_m,1·rand
      Ir_m,t = Irf·N^woIr_m,t·rand, rand<0.5 ise işareti ters
    Hızlı ↔ yavaş dönüşümü (Adım 1-10): sıralı listenin başındaki ürün
    temel ürün (BI); S_prob olasılıkla trendi negatife çevrilir. Rastgele
    seçilen karşı ürünün (CI) trend ve mevsimselliği BI'nin 1. dönem
    talebinden, ters işaretli trendle hesaplanır. Adım 8: tüm ürünlerin
    toplamında max ≤ M·min tutmazsa ikisi de sabit kalır.

    YORUM (makalede açık değil):
      - t = 1 değeri Fig. 8'de üretilen gerçek talep olarak kalır; formül t ≥ 2 için.
      - Talep 0'ın altına inemez (negatif satır sayısı olmaz).
      - M koşulu, henüz işlenmemiş ürünler 1. dönem değerinde sabit
        varsayılarak her çift için artımlı kontrol edilir.
    """
    n, U, L = spec.n_items, spec.n_periods, spec.season_L
    t = np.arange(U)                                   # t − 1
    cos = np.cos(2 * math.pi * t / L)

    def series(base: float, trend: float, season: float) -> np.ndarray:
        wo = base + trend * t + season * cos
        ir = spec.irregular_f * wo * rng.random(U)
        ir = np.where(rng.random(U) < 0.5, -ir, ir)
        s = np.maximum(np.rint(wo + ir), 0)
        s[0] = base
        return s

    D = np.repeat(lines_p1[:, None].astype(float), U, axis=1)   # başlangıçta hepsi sabit
    total = D.sum(axis=0)

    # Adım 1: 1. dönem satır sayısına göre azalan sıra (eşitler rastgele)
    order = np.lexsort((rng.random(n), -lines_p1))
    remaining = list(order.tolist())
    s_prob = 1.0                                       # Adım 3
    stats = {'pairs': 0, 'kept': 0, 'rejected_M': 0, 'bi_declining': 0}

    while len(remaining) >= 2:
        bi = remaining.pop(0)                          # Adım 2 / 10
        n_bi = float(lines_p1[bi])
        # Adım 4
        t_bi = spec.Tf * n_bi * rng.random()
        s_bi = spec.Sf * n_bi * rng.random()
        # Adım 5
        if rng.random() < s_prob:
            t_bi = -t_bi
        # Adım 6
        ci = remaining.pop(int(rng.integers(len(remaining))))
        # Adım 7: CI, BI'nin büyüklüğüyle ve ters yönde trend alır
        t_ci = spec.Tf * n_bi * rng.random()
        if t_bi > 0:
            t_ci = -t_ci
        s_ci = spec.Sf * n_bi * rng.random()
        new_bi = series(n_bi, t_bi, s_bi)
        new_ci = series(float(lines_p1[ci]), t_ci, s_ci)
        # Adım 8
        cand = total - D[bi] - D[ci] + new_bi + new_ci
        stats['pairs'] += 1
        if cand.max() <= spec.max_fluct_M * cand.min():
            D[bi], D[ci], total = new_bi, new_ci, cand
            stats['kept'] += 1
            stats['bi_declining'] += int(t_bi < 0)
        else:
            stats['rejected_M'] += 1
        # Adım 9
        s_prob *= 0.995
    return D.astype(np.int64), stats


# ── Tüm veri seti ──────────────────────────────────────────────────────

@dataclass
class KublerData:
    spec: KublerSpec
    weights: np.ndarray            # ürün ağırlığı (WU / adet)
    demand: np.ndarray             # (ürün × dönem) satır sayısı
    initial_locations: np.ndarray  # ürün → lokasyon (1. dönem ABC'ye göre)
    item_class: np.ndarray         # 1. dönem sınıfı 0/1/2
    zones: dict
    stats: dict
    _p1_orders: list = field(default_factory=list)
    _cache: dict = field(default_factory=dict)

    def period_orders(self, period: int) -> list[list[Order]]:
        """Mutlak dönem (0 = 1. dönem) → 20 alt dönemin siparişleri."""
        if period not in self._cache:
            if len(self._cache) > 3:
                self._cache.clear()
            self._cache[period] = self._build(period)
        return self._cache[period]

    def _build(self, period: int) -> list[list[Order]]:
        sp = self.spec
        if period == 0:
            item_lists = self._p1_orders
            rng = np.random.default_rng([sp.seed, 0, 1])
        else:
            rng = np.random.default_rng([sp.seed, sp.scenario, 100 + period])
            lines = self.demand[:, period]
            sizes = _order_sizes(rng, None, int(lines.sum()), sp.n_maxol)
            if lines.max() > len(sizes):
                # YORUM: bir ürünün satır sayısı sipariş sayısını aşamaz
                lines = np.minimum(lines, len(sizes))
                sizes = _order_sizes(rng, None, int(lines.sum()), sp.n_maxol)
            item_lists = _distribute(rng, lines, sizes)
        orders = []
        for k, items in enumerate(item_lists):
            ols = []
            for it in items:
                q = int(rng.integers(1, sp.a_maxol + 1))
                ols.append(OrderLine(item=it, quantity=q, location=int(self.initial_locations[it]),
                                     weight=round(q * float(self.weights[it]), 4)))
            orders.append(Order(order_id=k, num_orderlines=len(ols),
                                total_weight=round(sum(o.weight for o in ols), 4), orderlines=ols))
        # alt dönemlere düzgün dağıt
        idx = rng.permutation(len(orders))
        S = sp.n_subperiods
        bounds = [round(s * len(orders) / S) for s in range(S + 1)]
        return [[orders[i] for i in sorted(idx[bounds[s]:bounds[s + 1]])] for s in range(S)]


def generate_kubler(spec: KublerSpec, zones: dict | None = None) -> KublerData:
    """
    1. dönem, ağırlıklar ve başlangıç yerleşimi yalnızca `seed`'e bağlıdır
    (iki senaryo aynı başlangıç deposunu paylaşır); dinamikler senaryoya bağlı.
    """
    if zones is None:
        from core.data_loader import DataLoader
        zones = DataLoader().load_location_classes()
    base = np.random.default_rng([spec.seed, 0, 0])
    n = spec.n_items

    weights = np.round(base.uniform(*spec.weight_range, n), 4)

    # Fig. 8: 1. dönem siparişleri
    sizes = _order_sizes(base, spec.n_orders_p1, None, spec.n_maxol)
    lines_rank = access_lines(int(sizes.sum()), n, spec.access_frequency)
    # ürün kimlikleri popülerlik sırasına rastgele eşlenir
    perm = base.permutation(n)
    lines_p1 = np.empty(n, dtype=np.int64)
    lines_p1[perm] = lines_rank
    p1_orders = _distribute(base, lines_p1, sizes)

    # 1. dönem ABC → sınıf içinde rastgele yer (§6.3 son paragraf)
    ranked = np.lexsort((base.random(n), -lines_p1))
    nA = round(spec.class_items[0] * n)
    nB = round(spec.class_items[1] * n)
    item_class = np.full(n, 2)
    item_class[ranked[:nA]] = 0
    item_class[ranked[nA:nA + nB]] = 1
    loc = np.empty(n, dtype=np.int64)
    for r, key in enumerate('ABC'):
        items = np.flatnonzero(item_class == r)
        slots = base.permutation(np.array(zones[key]))[:len(items)]
        assert len(slots) == len(items), f"{key} bölgesinde yer yetmiyor"
        loc[base.permutation(items)] = slots

    dyn = np.random.default_rng([spec.seed, spec.scenario, 1])
    demand, stats = demand_series(spec, lines_p1, dyn)
    stats['p1_orders'] = int(len(sizes))
    stats['p1_lines'] = int(sizes.sum())
    tot = demand.sum(axis=0)
    stats['total_lines_min_max'] = [int(tot.min()), int(tot.max())]

    return KublerData(spec=spec, weights=weights, demand=demand, initial_locations=loc,
                      item_class=item_class, zones=zones, stats=stats, _p1_orders=p1_orders)
