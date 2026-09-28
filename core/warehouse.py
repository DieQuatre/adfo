"""
core/warehouse.py
=================
Depo geometrisi ve mesafe hesaplamaları.

Bu modül, Kübler et al. (2020) Section 6'da tanımlanan depo düzenini implemente eder:
- 10 picking aisle × 3 blok = 7200 lokasyon
- Multi-block layout, Manhattan + Steiner TSP mesafeleri
- Cross aisle'lar üzerinden en kısa yol hesabı

Önemli kavramlar:
- LU (Length Unit): paper'da kullanılan mesafe birimi (1 rack = 1 LU)
- Depot: -1 ID'siyle gösterilir
- Lokasyon ID encoding: aisle × 720 + side × 360 + rack × 4 + within_rack
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable
import numpy as np

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import WAREHOUSE, ITEMS, RUNTIME


# ════════════════════════════════════════════════════════════════════════════
# YARDIMCI VERİ SINIFLARI
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Location:
    """Bir lokasyonun fiziksel konumu."""
    loc_id: int
    aisle: int       # 0..9
    side: int        # 0=sol, 1=sağ
    rack: int        # 0..89
    within_rack: int # 0..3
    x: float         # LU
    y: float         # LU


# ════════════════════════════════════════════════════════════════════════════
# WAREHOUSE SINIFI
# ════════════════════════════════════════════════════════════════════════════

class Warehouse:
    """
    Depo geometrisi ve mesafe hesabı.

    Kullanım:
        wh = Warehouse()
        d = wh.distance(loc_a=100, loc_b=2500)
        d_depot = wh.distance(loc_a=-1, loc_b=100)  # depot'tan lokasyon 100'e
    """

    DEPOT = RUNTIME['depot_location_id']  # -1

    # Parametrik depo düzeni için kullanılabilen anahtarlar. Verilmeyenler
    # config.WAREHOUSE'dan (Kübler düzeni) gelir.
    LAYOUT_KEYS = (
        'num_aisles', 'num_blocks', 'racks_per_side_per_block', 'locs_per_rack',
        'rack_width_LU', 'cross_aisle_width_LU', 'aisle_spacing_LU',
        'class_A_pct', 'class_B_pct',
    )

    def __init__(self, layout: dict | None = None):
        """
        layout: depo düzeni. None → Kübler düzeni (config.WAREHOUSE).
            Örn. Warehouse({'num_aisles': 20, 'num_blocks': 1,
                            'racks_per_side_per_block': 60})
        num_blocks: 1 = ara koridorsuz (geçişsiz), 2 = bir ara koridor
            (tek geçişli), 3 = iki ara koridor (iki geçişli).
        """
        layout = dict(layout or {})
        unknown = set(layout) - set(self.LAYOUT_KEYS) - {'total_locations', 'num_cross_aisles'}
        if unknown:
            raise ValueError(f"Bilinmeyen depo parametresi: {sorted(unknown)}")
        L = {k: WAREHOUSE[k] for k in self.LAYOUT_KEYS}
        L.update({k: v for k, v in layout.items() if k in self.LAYOUT_KEYS})
        if L['num_blocks'] < 1 or L['num_aisles'] < 1:
            raise ValueError("num_blocks ve num_aisles en az 1 olmalı")
        self.layout = L

        # Topoloji
        self.num_aisles = L['num_aisles']
        self.num_blocks = L['num_blocks']
        self.racks_per_block = L['racks_per_side_per_block']
        self.locs_per_rack = L['locs_per_rack']
        self.total_locations = (self.num_aisles * 2 * self.num_blocks *
                                self.racks_per_block * self.locs_per_rack)
        for key, derived in (('total_locations', self.total_locations),
                             ('num_cross_aisles', self.num_blocks + 1)):
            given = layout.get(key, WAREHOUSE[key] if not layout else None)
            if given is not None and given != derived:
                raise ValueError(f"{key}={given} düzenle tutarsız (hesaplanan {derived})")

        # Boyutlar
        self.rack_width = L['rack_width_LU']
        self.cross_aisle_width = L['cross_aisle_width_LU']
        self.aisle_spacing = L['aisle_spacing_LU']
        self.class_pct = {'A': L['class_A_pct'], 'B': L['class_B_pct'],
                          'C': 1.0 - L['class_A_pct'] - L['class_B_pct']}

        # Türetilmiş ölçüler
        self.racks_per_aisle_side = self.num_blocks * self.racks_per_block
        self.locs_per_aisle_side = self.racks_per_aisle_side * self.locs_per_rack
        self.locs_per_aisle = 2 * self.locs_per_aisle_side

        # Cross aisle x koordinatları
        # Yapı: cross[0] | blok 0 | cross[1] | blok 1 | ... | cross[num_blocks]
        self.block_length = self.racks_per_block * self.rack_width
        self.cross_aisle_x: list[float] = []
        x = 0.0
        for b in range(self.num_blocks + 1):
            self.cross_aisle_x.append(x)
            if b < self.num_blocks:
                x += self.block_length + (self.cross_aisle_width if b > 0 else 0)

        # Aisle merkez y koordinatları
        self.aisle_y: list[float] = [
            (i + 0.5) * self.aisle_spacing for i in range(self.num_aisles)
        ]

        # Depot: sağ cross aisle, en alt aisle yanında
        self.depot_x = self.cross_aisle_x[-1] + self.cross_aisle_width
        self.depot_y = 0.0  # en altta (aisle 0'ın altında)

        # Aisle uzunluğu (toplam)
        self.aisle_length = (
            self.num_blocks * self.block_length +
            (self.num_cross_aisles_inner) * self.cross_aisle_width
        )

        # Lokasyon koordinatlarını önbelleğe al (7200 lokasyon, hızlı)
        self._location_cache: dict[int, Location] = {}
        self._build_location_cache()

        # Mesafe önbelleği (çift bazlı) — genel amaçlı
        self._distance_cache: dict[tuple[int, int], float] = {}

        # Aktif problem için numpy matris cache
        self._matrix: 'np.ndarray | None' = None
        self._matrix_locs: list[int] = []
        self._matrix_idx: dict[int, int] = {}

    @property
    def num_cross_aisles_inner(self) -> int:
        """İç cross aisle sayısı (uçlar hariç) = blok sayısı - 1."""
        return self.num_blocks - 1

    # ────────────────────────────────────────────────────────────
    # LOKASYON KODLAMA / ÇÖZME
    # ────────────────────────────────────────────────────────────

    def decode_location(self, loc_id: int) -> tuple[int, int, int, int]:
        """
        Lokasyon ID → (aisle, side, rack, within_rack)

        Encoding:
            loc_id = aisle * 720 + side * 360 + rack * 4 + within_rack
        """
        if loc_id < 0 or loc_id >= self.total_locations:
            raise ValueError(f"Geçersiz loc_id: {loc_id}")

        aisle = loc_id // self.locs_per_aisle
        remainder = loc_id % self.locs_per_aisle
        side = remainder // self.locs_per_aisle_side
        remainder2 = remainder % self.locs_per_aisle_side
        rack = remainder2 // self.locs_per_rack
        within = remainder2 % self.locs_per_rack
        return aisle, side, rack, within

    def encode_location(self, aisle: int, side: int, rack: int, within: int) -> int:
        return (aisle * self.locs_per_aisle +
                side * self.locs_per_aisle_side +
                rack * self.locs_per_rack +
                within)

    def get_location(self, loc_id: int) -> Location:
        """Önbellekten lokasyon nesnesi getir."""
        return self._location_cache[loc_id]

    def _build_location_cache(self) -> None:
        """7200 lokasyonun fiziksel konumlarını hesapla ve cache'e koy."""
        for loc_id in range(self.total_locations):
            aisle, side, rack, within = self.decode_location(loc_id)

            # Rack'in hangi blokta olduğunu bul
            block_idx = rack // self.racks_per_block          # 0, 1, veya 2
            rack_in_block = rack % self.racks_per_block       # 0..29

            # X koordinatı: blok başlangıcı + rack pozisyonu
            block_start_x = self.cross_aisle_x[block_idx]
            if block_idx > 0:
                block_start_x += self.cross_aisle_width  # önceki cross aisle'dan sonra

            # Rack merkezi
            x = block_start_x + (rack_in_block + 0.5) * self.rack_width

            # Y koordinatı: aisle merkezi
            # Not: side (sol/sağ) y koordinatını değiştirmez —
            # rafa erişim yatay olarak yapılır (Assumption 9 in paper)
            y = self.aisle_y[aisle]

            self._location_cache[loc_id] = Location(
                loc_id=loc_id, aisle=aisle, side=side, rack=rack,
                within_rack=within, x=x, y=y
            )

    # ────────────────────────────────────────────────────────────
    # KOORDİNATLAR
    # ────────────────────────────────────────────────────────────

    def coords(self, loc_id: int) -> tuple[float, float]:
        """Bir lokasyonun (x, y) koordinatlarını döner. Depot için (depot_x, depot_y)."""
        if loc_id == self.DEPOT:
            return self.depot_x, self.depot_y
        return self._location_cache[loc_id].x, self._location_cache[loc_id].y

    # ────────────────────────────────────────────────────────────
    # MESAFE HESABI (Steiner TSP / Manhattan)
    # ────────────────────────────────────────────────────────────

    def distance(self, loc_a: int, loc_b: int) -> float:
        """
        İki lokasyon arasındaki en kısa mesafe (LU cinsinden).
        Cache'lenmiş — aynı çift için tekrar tekrar hesaplanmaz.
        """
        if loc_a == loc_b:
            return 0.0

        # Cache key (sıralı çift) — min/max yerine if ile (daha hızlı)
        if loc_a < loc_b:
            key = (loc_a, loc_b)
        else:
            key = (loc_b, loc_a)

        cached = self._distance_cache.get(key)
        if cached is not None:
            return cached

        d = self._compute_distance(loc_a, loc_b)
        self._distance_cache[key] = d
        return d

    def _compute_distance(self, loc_a: int, loc_b: int) -> float:
        """Asıl mesafe hesabı (cache miss durumunda)."""
        if loc_a == loc_b:
            return 0.0

        xa, ya = self.coords(loc_a)
        xb, yb = self.coords(loc_b)

        # Hangi aisle'larda?
        aisle_a = self._aisle_of(loc_a)
        aisle_b = self._aisle_of(loc_b)

        # Aynı aisle ise direkt
        if aisle_a is not None and aisle_b is not None and aisle_a == aisle_b:
            return abs(xa - xb)

        # Aksi halde her cross aisle üzerinden yolu dene
        candidate_x_levels = list(self.cross_aisle_x)
        if loc_a == self.DEPOT or loc_b == self.DEPOT:
            candidate_x_levels.append(self.depot_x)

        min_dist = float('inf')
        for cx in candidate_x_levels:
            # A'dan cross aisle x=cx'e → cross boyunca → B'ye
            d = abs(xa - cx) + abs(ya - yb) + abs(xb - cx)
            if d < min_dist:
                min_dist = d

        return min_dist

    def _aisle_of(self, loc_id: int) -> int | None:
        """Depot için None, diğerleri için aisle indeksi."""
        if loc_id == self.DEPOT:
            return None
        return loc_id // self.locs_per_aisle

    # ────────────────────────────────────────────────────────────
    # MESAFE MATRİSİ (alt-küme için)
    # ────────────────────────────────────────────────────────────

    def distance_matrix(self, location_ids: list[int]) -> np.ndarray:
        """
        Verilen lokasyon listesi için mesafe matrisi.
        Tam 7200×7200 yapmak gereksiz (51M element); sadece kullanılanlar.

        location_ids: depot dahil olabilir (-1).
        """
        n = len(location_ids)
        D = np.zeros((n, n), dtype=np.float64)
        for i in range(n):
            for j in range(i + 1, n):
                d = self.distance(location_ids[i], location_ids[j])
                D[i, j] = d
                D[j, i] = d
        return D

    def build_problem_matrix(self, orders: list) -> None:
        """
        Bir problem instance'ındaki TÜM lokasyonlar için numpy mesafe matrisi
        önceden hesapla. DEPSO başlangıcında 1 kez çağrılır.

        Sonra dist_m(a, b) ile O(1) erişim → dict lookup overhead yok.

        orders: Order nesneleri listesi
        """
        # Kullanılan tüm lokasyonları topla (depot dahil)
        locs: set[int] = {self.DEPOT}
        for o in orders:
            for ol in o.orderlines:
                locs.add(ol.location)

        self._matrix_locs = sorted(locs, key=lambda x: (x == self.DEPOT, x))
        self._matrix_idx = {lid: i for i, lid in enumerate(self._matrix_locs)}

        n = len(self._matrix_locs)
        M = np.zeros((n, n), dtype=np.float32)  # float32 → yarı bellek
        for i in range(n):
            for j in range(i + 1, n):
                d = self._compute_distance(self._matrix_locs[i],
                                           self._matrix_locs[j])
                M[i, j] = d
                M[j, i] = d
        self._matrix = M

    def dist_m(self, loc_a: int, loc_b: int) -> float:
        """
        Numpy matrisinden O(1) mesafe okuma.
        build_problem_matrix() sonrası kullanılabilir.
        Matris yoksa normal distance()'a düşer.
        """
        if loc_a == loc_b:
            return 0.0
        if self._matrix is None:
            return self.distance(loc_a, loc_b)
        ia = self._matrix_idx.get(loc_a)
        ib = self._matrix_idx.get(loc_b)
        if ia is None or ib is None:
            return self.distance(loc_a, loc_b)
        return float(self._matrix[ia, ib])

    def submatrix(self, loc_ids: list[int]) -> 'list[list[float]] | None':
        """
        Verilen lokasyonlar için mesafe alt-matrisi (iç içe Python listesi).

        Rota sezgisellerinin iç döngüsünde dist_m() çağrısı yerine liste
        indekslemesi kullanmak için. Değerler dist_m() ile birebir aynıdır
        (aynı float32 matrisinden okunur). Matris yoksa ya da lokasyonlardan
        biri matriste değilse None döner; çağıran eski yola düşer.
        """
        if self._matrix is None:
            return None
        idx = self._matrix_idx
        try:
            rows = [idx[l] for l in loc_ids]
        except KeyError:
            return None
        return self._matrix[np.ix_(rows, rows)].tolist()

    # ────────────────────────────────────────────────────────────
    # SINIFLANDIRMA YARDIMCISI
    # ────────────────────────────────────────────────────────────

    def locations_sorted_by_depot_distance(self) -> list[int]:
        """
        Tüm 7200 lokasyonu depot'a uzaklığa göre sıralı döndürür.
        Sınıflara atama yaparken kullanılır.
        """
        all_locs = list(range(self.total_locations))
        all_locs.sort(key=lambda lid: self.distance(self.DEPOT, lid))
        return all_locs

    def assign_locations_to_classes(self) -> dict[str, list[int]]:
        """
        Lokasyonları A, B, C sınıflarına böler:
        - A: %5 depot'a en yakın
        - B: sonraki %15
        - C: kalan %80
        """
        sorted_locs = self.locations_sorted_by_depot_distance()
        n = self.total_locations

        n_a = int(n * self.class_pct['A'])
        n_b = int(n * self.class_pct['B'])

        return {
            'A': sorted_locs[:n_a],
            'B': sorted_locs[n_a:n_a + n_b],
            'C': sorted_locs[n_a + n_b:],
        }

    # ────────────────────────────────────────────────────────────
    # ÖZET
    # ────────────────────────────────────────────────────────────

    def summary(self) -> dict:
        return {
            'layout': dict(self.layout),
            'num_aisles': self.num_aisles,
            'num_blocks': self.num_blocks,
            'total_locations': self.total_locations,
            'aisle_length_LU': self.aisle_length,
            'warehouse_width_LU': self.num_aisles * self.aisle_spacing,
            'cross_aisle_x_LU': self.cross_aisle_x,
            'depot_xy': (self.depot_x, self.depot_y),
        }

    def __repr__(self) -> str:
        return (f"Warehouse({self.num_aisles} aisle × {self.num_blocks} blok, "
                f"{self.total_locations} lok, depot=({self.depot_x:.1f},{self.depot_y:.1f}))")


# ════════════════════════════════════════════════════════════════════════════
# HIZLI TEST
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    wh = Warehouse()
    print(wh)
    print()
    print("Özet:")
    for k, v in wh.summary().items():
        print(f"  {k}: {v}")

    print()
    print("Bazı lokasyonların koordinatları:")
    for lid in [0, 359, 360, 719, 720, 3599, 7199]:
        x, y = wh.coords(lid)
        a, s, r, w = wh.decode_location(lid)
        print(f"  loc {lid:4d}: aisle={a}, side={s}, rack={r:2d}, w={w} → ({x:5.1f}, {y:5.1f})")

    print()
    print("Mesafe örnekleri (LU):")
    cases = [
        (-1, 0,      "depot → loc 0 (aisle 0, en sol rack)"),
        (-1, 7199,   "depot → loc 7199 (aisle 9, en uzak rack)"),
        (0, 1,       "loc 0 → loc 1 (aynı rack)"),
        (0, 4,       "loc 0 → loc 4 (yan rack, aynı aisle)"),
        (0, 720,     "loc 0 → loc 720 (aisle 0 → aisle 1)"),
        (0, 6480,    "loc 0 → loc 6480 (aisle 0 → aisle 9)"),
    ]
    for a, b, desc in cases:
        d = wh.distance(a, b)
        print(f"  {desc:50s} = {d:6.2f} LU")

    print()
    print("Sınıf ataması:")
    classes = wh.assign_locations_to_classes()
    for cls, locs in classes.items():
        print(f"  Sınıf {cls}: {len(locs):4d} lokasyon (ilk: {locs[0]}, son: {locs[-1]})")
