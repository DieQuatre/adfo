"""
algorithms/routing/route_cache.py
=================================
Tüm algoritmaların ortak kullandığı rota servisi: NN + 2-opt, önbellekli.

Neden ortak?
- Aynı lokasyon kümesi için aynı rota ve aynı mesafe döner. Böylece DEPSO,
  RBRS-AE ve ileride ALNS çözümleri aynı ölçüyle değerlendirilir.
- Süre karşılaştırması adil olur: önbellek avantajı artık yalnızca bir
  algoritmaya ait değil.

Anahtar frozenset(lokasyonlar) olduğu için yinelenen lokasyonlar ve sıra
farkı aynı rotayı verir. Önbellek bir problem örneğine aittir; her solve()
çağrısında yeni bir RouteCache oluşturulmalıdır (mesafe matrisi değişebilir).
"""

from __future__ import annotations

from algorithms.routing.nearest_neighbor import nearest_neighbor_route
from algorithms.routing.two_opt import two_opt_improve


class RouteCache:
    def __init__(self, warehouse):
        self.wh = warehouse
        self._cache: dict[frozenset, tuple[tuple[int, ...], float]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, locations) -> tuple[list[int], float]:
        """(rota, mesafe) döndürür. Rota depo ile başlar ve biter.

        Dönen liste her çağrıda yeni bir kopyadır; çağıran değiştirebilir.
        """
        key = frozenset(locations)
        if not key:
            return [self.wh.DEPOT, self.wh.DEPOT], 0.0
        cached = self._cache.get(key)
        if cached is None:
            self.misses += 1
            route, _ = nearest_neighbor_route(list(key), self.wh)
            route, dist = two_opt_improve(route, self.wh)
            cached = (tuple(route), dist)
            self._cache[key] = cached
        else:
            self.hits += 1
        return list(cached[0]), cached[1]

    def distance(self, locations) -> float:
        return self.get(locations)[1]

    def __len__(self) -> int:
        return len(self._cache)
