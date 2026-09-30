"""
core/generator.py
=================
Parametrik problem üreticisi (Kübler veri setinden bağımsız).

Bir problem örneği beş değerle tam olarak belirlenir:

    InstanceSpec(size, blocks, fill, dynamics, seed)

Aynı spec her zaman aynı depoyu, ürünleri, talebi ve siparişleri üretir.
Bu yüzden siparişler diske yazılmak zorunda değildir; gerektiğinde yeniden
üretilir. Ayrıntılı açıklama: docs/URETICI.md.

Adımlar
-------
1. Depo:      hedef boyut + blok sayısı → Warehouse(layout)
2. Ürünler:   ürün sayısı = doluluk × lokasyon; ağırlık U(w_min, w_max)
3. Popülerlik: güç yasası, en popüler %20'nin payı = top20_share
4. Talep:     her ürüne bir profil (durağan / artan / azalan / mevsimsel /
              ani değişim); karışım dinamiklik seviyesine göre. Ayrıca çok
              satan ↔ az satan dönüşümü: popüler ürünlerin bir kısmı söner,
              yerlerine az satan ürünler benzer büyüklüğe çıkar (swap_share)
5. Yerleşim:  ısınma döneminin son talebine göre ABC; A ürünleri kapıya en
              yakın bölgeye, C en uzağa; bölge içinde rastgele
6. Siparişler: her dönemin gerçekleşen satırları siparişlere bölünür,
              siparişler alt dönemlere EŞİT dağıtılır
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, asdict, field
from pathlib import Path

import numpy as np

from config import GENERATOR as GEN, ITEMS
from core.data_loader import Order, OrderLine
from core.warehouse import Warehouse

PROFILES = ('stable', 'up', 'down', 'seasonal', 'shock')
CLASSES = ('A', 'B', 'C')


# ════════════════════════════════════════════════════════════════════════════
# SPEC
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class InstanceSpec:
    size: int                 # hedef lokasyon sayısı (5000, 10000, ...)
    blocks: int               # 1 geçişsiz, 2 tek geçişli, 3 iki geçişli
    fill: float               # doluluk oranı (0-1)
    dynamics: str = GEN['default_dynamics']
    seed: int = 0

    @property
    def name(self) -> str:
        return f"S{self.size}_B{self.blocks}_F{int(round(self.fill * 100))}_{self.dynamics}_s{self.seed}"

    def rng(self, *stream: int) -> np.random.Generator:
        """Spec'e ve akış numarasına bağlı, platformdan bağımsız RNG."""
        key = f"{self.size}|{self.blocks}|{self.fill:.6f}|{self.dynamics}|{self.seed}"
        base = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], 'little')
        return np.random.default_rng(np.random.SeedSequence([base, *stream]))


def layout_for(size: int, blocks: int, cfg: dict = GEN) -> dict:
    """
    Hedef boyuta en yakın depo düzeni. Koridor derinliği sabit
    (racks_per_side_total), koridor sayısı boyuta göre seçilir.
    """
    depth = cfg['racks_per_side_total']
    if depth % blocks:
        raise ValueError(f"racks_per_side_total={depth}, {blocks} bloğa bölünmüyor")
    per_aisle = 2 * depth * cfg['locs_per_rack']
    aisles = max(1, round(size / per_aisle))
    return {'num_aisles': aisles, 'num_blocks': blocks,
            'racks_per_side_per_block': depth // blocks,
            'locs_per_rack': cfg['locs_per_rack']}


def grid(seed: int = 0, dynamics: str | None = None) -> list[InstanceSpec]:
    """Toplantıdaki ızgara: boyut × koridor yapısı × doluluk."""
    dyn = dynamics or GEN['default_dynamics']
    return [InstanceSpec(s, b, f, dyn, seed)
            for s in GEN['grid_sizes'] for b in GEN['grid_blocks'] for f in GEN['grid_fills']]


# ════════════════════════════════════════════════════════════════════════════
# ÜRETİLMİŞ ÖRNEK
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class GeneratedInstance:
    spec: InstanceSpec
    warehouse: Warehouse
    weights: np.ndarray            # ürün ağırlığı (WU)
    profiles: list[str]            # ürün başına talep profili
    expected: np.ndarray           # (ürün × dönem) beklenen satır sayısı
    demand: np.ndarray             # (ürün × dönem) gerçekleşen satır sayısı
    locations: np.ndarray          # ürün başına başlangıç lokasyonu
    initial_class: list[str]       # ürün başına başlangıç sınıfı
    location_zones: dict           # {'A': [...], 'B': [...], 'C': [...]}
    stats: dict = field(default_factory=dict)
    _orders_cache: dict = field(default_factory=dict, repr=False)

    @property
    def num_items(self) -> int:
        return len(self.weights)

    @property
    def num_periods(self) -> int:
        return self.demand.shape[1]

    @property
    def first_test_period(self) -> int:
        return GEN['warmup_periods']

    # ── Siparişler ────────────────────────────────────────────────────
    def period_orders(self, period: int) -> list[list[Order]]:
        """Bir dönemin siparişleri, alt dönemlere bölünmüş (liste listesi)."""
        if period not in self._orders_cache:
            self._orders_cache[period] = _build_orders(self, period)
        return self._orders_cache[period]

    def sample_orders(self, k: int, set_id: int, period: int | None = None) -> list[Order]:
        """
        Algoritma karşılaştırması için k siparişlik set. Varsayılan dönem:
        ilk test dönemi. set_id farklı setler verir, aynı set_id aynı seti.
        """
        period = self.first_test_period if period is None else period
        pool = [o for sub in self.period_orders(period) for o in sub]
        if len(pool) < k:
            raise ValueError(f"{self.spec.name}: dönem {period} yalnızca {len(pool)} sipariş")
        idx = self.spec.rng(9, period, set_id).permutation(len(pool))[:k]
        return [pool[i] for i in sorted(idx)]

    # ── Diske yazma ───────────────────────────────────────────────────
    def save(self, directory: Path, with_orders: bool = False) -> Path:
        d = Path(directory) / self.spec.name
        d.mkdir(parents=True, exist_ok=True)
        meta = {'spec': asdict(self.spec), 'name': self.spec.name,
                'layout': self.warehouse.layout,
                'total_locations': self.warehouse.total_locations,
                'num_items': self.num_items, 'stats': self.stats,
                'generator_config': {k: v for k, v in GEN.items()}}
        (d / 'meta.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
        items = [{'item': i, 'weight_WU': round(float(self.weights[i]), 4),
                  'profile': self.profiles[i], 'initial_class': self.initial_class[i],
                  'initial_location': int(self.locations[i])}
                 for i in range(self.num_items)]
        (d / 'items.json').write_text(json.dumps(items), encoding='utf-8')
        (d / 'demand.json').write_text(json.dumps(self.demand.astype(int).tolist()), encoding='utf-8')
        if with_orders:
            p = self.first_test_period
            subs = self.period_orders(p)
            data = [[{'order_id': o.order_id, 'lines': [[l.item, l.quantity, l.location, l.weight]
                                                        for l in o.orderlines]} for o in sub]
                    for sub in subs]
            (d / f'orders_period{p:02d}.json').write_text(json.dumps(data), encoding='utf-8')
        return d


# ════════════════════════════════════════════════════════════════════════════
# ÜRETİM
# ════════════════════════════════════════════════════════════════════════════

def generate(spec: InstanceSpec) -> GeneratedInstance:
    if spec.dynamics not in GEN['dynamics']:
        raise ValueError(f"Bilinmeyen dinamiklik: {spec.dynamics}")
    if not 0 < spec.fill <= 1:
        raise ValueError("fill (0, 1] aralığında olmalı")

    wh = Warehouse(layout_for(spec.size, spec.blocks))
    n_items = int(round(spec.fill * wh.total_locations))
    P = GEN['warmup_periods'] + GEN['test_periods']

    # 2) ağırlıklar
    w_lo, w_hi = GEN['weight_range_WU']
    weights = np.round(spec.rng(1).uniform(w_lo, w_hi, n_items), 4)

    # 3) popülerlik (güç yasası), ürün sırası rastgele
    base = _power_law_shares(n_items, GEN['top20_share'])
    base = base[spec.rng(2).permutation(n_items)]
    mean_lines = (1 + GEN['max_lines_per_order']) / 2
    lines_per_period = GEN['orders_per_item'] * n_items * mean_lines
    base = base * lines_per_period

    # 4) talep profilleri
    profiles, multipliers = _profiles(spec, n_items, P)
    _apply_swaps(spec, base, multipliers, profiles, P)
    expected = base[:, None] * multipliers
    noise = spec.rng(4).lognormal(0.0, GEN['irregular_sigma'], expected.shape)
    demand = spec.rng(5).poisson(expected * noise)

    # 5) yerleşim
    zones = wh.assign_locations_to_classes()
    ref_period = GEN['placement_period']
    init_class = _abc(demand[:, ref_period], wh.class_pct)
    locations = np.empty(n_items, dtype=np.int64)
    rng = spec.rng(6)
    for c in CLASSES:
        members = np.flatnonzero(np.array(init_class) == c)
        zone = np.array(zones[c])
        if len(members) > len(zone):
            raise ValueError(f"{spec.name}: {c} bölgesine sığmıyor")
        locations[members] = rng.choice(zone, size=len(members), replace=False)

    inst = GeneratedInstance(spec=spec, warehouse=wh, weights=weights, profiles=profiles,
                             expected=expected, demand=demand, locations=locations,
                             initial_class=list(init_class), location_zones=zones)
    inst.stats = _stats(inst)
    return inst


def _power_law_shares(n: int, top20_share: float) -> np.ndarray:
    """rank^(-α) payları; α, en üst %20'nin payı top20_share olacak şekilde."""
    ranks = np.arange(1, n + 1, dtype=float)
    top = max(1, int(round(0.2 * n)))

    def share(alpha):
        w = ranks ** (-alpha)
        return w[:top].sum() / w.sum()

    lo, hi = 0.0, 5.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if share(mid) < top20_share:
            lo = mid
        else:
            hi = mid
    w = ranks ** (-(lo + hi) / 2)
    return w / w.sum()


def _profiles(spec: InstanceSpec, n: int, P: int) -> tuple[list[str], np.ndarray]:
    mix = GEN['dynamics'][spec.dynamics]
    rng = spec.rng(3)
    probs = np.array([mix[p] for p in PROFILES], dtype=float)
    kinds = rng.choice(len(PROFILES), size=n, p=probs / probs.sum())
    t = np.arange(P, dtype=float)
    L = GEN['season_length']
    M = np.ones((n, P))
    for i, kind in enumerate(kinds):
        name = PROFILES[kind]
        if name == 'up':
            g = rng.uniform(*GEN['trend_total_change'])
            M[i] = 1 + g * t / (P - 1)
        elif name == 'down':
            g = rng.uniform(*GEN['trend_total_change'])
            M[i] = np.maximum(0.1, 1 - min(g, 0.9) * t / (P - 1))
        elif name == 'seasonal':
            a = rng.uniform(*GEN['season_amplitude'])
            phase = rng.uniform(0, L)
            M[i] = 1 + a * np.sin(2 * np.pi * (t + phase) / L)
        elif name == 'shock':
            t0 = rng.integers(GEN['warmup_periods'] // 2, P)
            f = (rng.uniform(*GEN['shock_up']) if rng.random() < 0.5
                 else rng.uniform(*GEN['shock_down']))
            M[i, t0:] = f
    return [PROFILES[k] for k in kinds], M


def _apply_swaps(spec: InstanceSpec, base: np.ndarray, M: np.ndarray,
                 profiles: list[str], P: int) -> None:
    """
    Çok satan ↔ az satan dönüşümü (yerinde değiştirir). En popüler %20'den
    swap_share oranında ürün popülerlikle orantılı seçilir; her birinin talebi t0'dan başlayarak
    `süre` dönemde swap_floor düzeyine iner. Eşine (en popüler %20 dışından
    rastgele bir ürün) aynı sürede sönen ürünün talebi × U(swap_level) kadar
    talep eklenir. Kübler (2020) §6.3'teki temel ürün / karşı ürün fikri.
    """
    share = GEN['swap_share'].get(spec.dynamics, 0.0)
    n = len(base)
    top = max(1, int(round(0.2 * n)))
    n_pairs = int(round(share * top))
    if n_pairs == 0 or n - top < n_pairs:
        return
    rng = spec.rng(10)
    ranked = np.argsort(-base, kind='stable')
    # Kübler'deki gibi en çok satanların sönme olasılığı en yüksek:
    # popülerlikle orantılı, iadesiz seçim
    w = base[ranked[:top]]
    fading = rng.choice(ranked[:top], size=n_pairs, replace=False, p=w / w.sum())
    rising = rng.choice(ranked[top:], size=n_pairs, replace=False)
    t = np.arange(P, dtype=float)
    floor = GEN['swap_floor']
    for bi, ci in zip(fading, rising):
        t0 = int(rng.integers(GEN['swap_start'][0], GEN['swap_start'][1] + 1))
        dur = int(rng.integers(GEN['swap_duration'][0], GEN['swap_duration'][1] + 1))
        ramp = np.clip((t - t0) / dur, 0.0, 1.0)
        level = rng.uniform(*GEN['swap_level'])
        M[bi] = M[bi] * (1.0 - ramp * (1.0 - floor))
        M[ci] = M[ci] + ramp * level * base[bi] / base[ci]
        profiles[bi] = 'swap_down'
        profiles[ci] = 'swap_up'


def _abc(values: np.ndarray, class_pct: dict) -> list[str]:
    """Değere göre azalan sırada ilk %A → A, sonraki %B → B, kalan C."""
    n = len(values)
    order = np.argsort(-values, kind='stable')
    n_a = int(n * class_pct['A'])
    n_b = int(n * class_pct['B'])
    out = np.empty(n, dtype='<U1')
    out[order[:n_a]] = 'A'
    out[order[n_a:n_a + n_b]] = 'B'
    out[order[n_a + n_b:]] = 'C'
    return list(out)


def _build_orders(inst: GeneratedInstance, period: int) -> list[list[Order]]:
    """
    Dönemin gerçekleşen satırlarını siparişlere böl.

    - Satır havuzu: her ürün, o dönemdeki talebi kadar tekrar eder; karıştırılır.
    - Sipariş: 1..max_lines farklı ürün, her satıra 1..max_qty adet.
      Toplam ağırlık kapasiteyi aşarsa adetler azaltılır (min 1), yine
      aşarsa satır bir sonraki siparişe bırakılır.
    - Siparişler alt dönemlere EŞİT sayıda dağıtılır (Kübler verisindeki
      alt dönem dengesizliği burada yoktur).
    """
    rng = inst.spec.rng(7, period)
    cap = ITEMS['picker_capacity_WU']
    pool = np.repeat(np.arange(inst.num_items), inst.demand[:, period])
    rng.shuffle(pool)
    pool = pool.tolist()

    orders: list[Order] = []
    pos = 0
    carry: list[int] = []
    while pos < len(pool) or carry:
        want = int(rng.integers(1, GEN['max_lines_per_order'] + 1))
        lines, used, total = [], set(), 0.0
        candidates = carry
        carry = []
        while len(lines) < want and (candidates or pos < len(pool)):
            if candidates:
                item = candidates.pop(0)
            else:
                item = pool[pos]
                pos += 1
            if item in used:
                carry.append(item)
                continue
            qty = int(rng.integers(1, GEN['max_qty_per_line'] + 1))
            w_item = float(inst.weights[item])
            while qty > 1 and total + qty * w_item > cap:
                qty -= 1
            if total + qty * w_item > cap:
                carry.append(item)
                break
            weight = round(qty * w_item, 4)
            lines.append(OrderLine(item=int(item), quantity=qty,
                                   location=int(inst.locations[item]), weight=weight))
            used.add(item)
            total += weight
        carry = candidates + carry
        if not lines:
            if carry and not (pos < len(pool)):
                # Kalan satırlar yalnızca tekrar eden ürünlerden oluşuyorsa
                # her birini tek başına sipariş yap.
                item = carry.pop(0)
                w_item = float(inst.weights[item])
                lines.append(OrderLine(item=int(item), quantity=1,
                                       location=int(inst.locations[item]),
                                       weight=round(w_item, 4)))
                total = w_item
            else:
                continue
        orders.append(Order(order_id=len(orders), num_orderlines=len(lines),
                            total_weight=round(total, 4), orderlines=lines))

    S = GEN['subperiods']
    order_idx = rng.permutation(len(orders))
    subs: list[list[Order]] = [[] for _ in range(S)]
    for rank, oi in enumerate(order_idx):
        subs[rank % S].append(orders[oi])
    return subs


def _stats(inst: GeneratedInstance) -> dict:
    """
    Hakemin göreceği doğrulama ölçüleri (meta.json'a yazılır).

    Dinamiklik iki şekilde ölçülür:
    - yapısal: BEKLENEN talebe göre ABC sınıfı değişen ürün oranı. Profillerin
      yarattığı gerçek değişimi gösterir; dinamiklik seviyesini bu ayırır.
    - gözlenen: GERÇEKLEŞEN talebe göre. Az satan ürünlerde Poisson gürültüsü
      baskındır, bu yüzden seviyeler arasında fark küçüktür.
    """
    D, E = inst.demand, inst.expected
    first = inst.first_test_period
    test = list(range(first, inst.num_periods))
    pct = inst.warehouse.class_pct

    def change_rates(M):
        cl = [np.array(_abc(M[:, t], pct)) for t in range(first - 1, inst.num_periods)]
        per = [float(np.mean(a != b)) for a, b in zip(cl[:-1], cl[1:])]
        horizon = float(np.mean(cl[0] != cl[-1]))
        return per, horizon

    def top20(M):
        vals = []
        for t in test:
            col = np.sort(M[:, t])[::-1]
            top = max(1, int(round(0.2 * len(col))))
            vals.append(float(col[:top].sum() / max(1e-12, col.sum())))
        return float(np.mean(vals))

    s_per, s_hor = change_rates(E)
    o_per, o_hor = change_rates(D)
    return {
        'total_locations': inst.warehouse.total_locations,
        'num_items': inst.num_items,
        'fill_realised': round(inst.num_items / inst.warehouse.total_locations, 4),
        'lines_per_period_mean': round(float(D[:, test].sum(axis=0).mean()), 1),
        'top20_share_expected': round(top20(E), 4),
        'top20_share_realised': round(top20(D), 4),
        'structural_class_change_per_period': round(float(np.mean(s_per)), 4),
        'structural_class_change_test_horizon': round(s_hor, 4),
        'observed_class_change_per_period': round(float(np.mean(o_per)), 4),
        'profile_counts': {p: inst.profiles.count(p)
                           for p in PROFILES + ('swap_down', 'swap_up')},
    }
