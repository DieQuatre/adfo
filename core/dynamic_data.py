"""
core/dynamic_data.py
====================
Dinamik (çok dönemli) deney için ortak veri görünümü. İki kaynak:

- Kübler veri seti (data/, senaryo 1 ve 2)
- Parametrik üretici (core/generator.py)

Her ikisi de aynı alanları verir; relocation ve run_dynamic.py kaynağı bilmez.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from config import TIME_SERIES
from core.data_loader import DataLoader, Order
from core.warehouse import Warehouse


@dataclass
class DynamicProblem:
    name: str
    warehouse: Warehouse
    demand: np.ndarray                     # (ürün × dönem) gerçekleşen satır sayısı
    warmup: int                            # ısınma dönemi sayısı
    test_periods: list[int]                # mutlak dönem indeksleri
    zones: dict[str, list[int]]            # A/B/C lokasyon bölgeleri
    initial_locations: np.ndarray          # ürün başına başlangıç yeri
    orders_fn: Callable[[int], list[list[Order]]]   # dönem → alt dönemlere bölünmüş siparişler
    subperiods: int


def _rebalance(orders: list[Order], parts: int) -> list[list[Order]]:
    """Siparişleri sırası korunarak `parts` eşit parçaya böl."""
    n = len(orders)
    bounds = [round(k * n / parts) for k in range(parts + 1)]
    return [orders[bounds[k]:bounds[k + 1]] for k in range(parts)]


def from_kubler(scenario: int, loader: DataLoader | None = None) -> DynamicProblem:
    """
    Kübler veri seti. Test dönemi p (1..9) mutlak indeks 12 + p − 1'dir.

    Not: veri setindeki alt dönemler dengesiz (ilk alt dönemde ~2900, son
    alt dönemde ~110 sipariş; docs/NOTES.md). Makalede dönem başına 5000
    sipariş 20 alt döneme bölünür; burada dönemin siparişleri sıraları
    korunarak 20 eşit alt döneme yeniden bölünür.
    """
    loader = loader or DataLoader()
    wh = Warehouse()
    demand = loader.load_scenario_demand(scenario)
    items = loader.load_items()
    warmup = TIME_SERIES['num_warmup_periods']
    S = TIME_SERIES['num_subperiods']

    def orders_fn(period: int) -> list[list[Order]]:
        p = period - warmup + 1
        return _rebalance(loader.all_orders_in_period(scenario, p), S)

    return DynamicProblem(
        name=f"kubler_s{scenario}", warehouse=wh, demand=demand, warmup=warmup,
        test_periods=list(range(warmup, warmup + TIME_SERIES['num_test_periods'])),
        zones=loader.load_location_classes(),
        initial_locations=np.array([it.initial_location for it in items]),
        orders_fn=orders_fn, subperiods=S)


def from_generated(inst) -> DynamicProblem:
    """core.generator.GeneratedInstance → DynamicProblem."""
    from config import GENERATOR as GEN
    return DynamicProblem(
        name=inst.spec.name, warehouse=inst.warehouse, demand=inst.demand,
        warmup=GEN['warmup_periods'],
        test_periods=list(range(GEN['warmup_periods'], inst.num_periods)),
        zones=inst.location_zones, initial_locations=inst.locations.copy(),
        orders_fn=inst.period_orders, subperiods=GEN['subperiods'])
