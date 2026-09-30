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

from algorithms.routing import fast
from algorithms.routing.nearest_neighbor import nearest_neighbor_route
from algorithms.routing.two_opt import two_opt_improve


# Önbellekte tutulan toplam lokasyon sayısı sınırı (işlem başına). Aşılınca
# önbellek boşaltılır; hesap deterministik olduğu için sonuç değişmez, yalnızca
# bazı rotalar yeniden hesaplanır. Sınırsız hâlde RBRS-AE'nin son yerel
# iyileştirmesi büyük depolarda (620 sipariş) işlem başına ~1 GB tutuyordu;
# 16 paralel işlemde bellek bitiyordu. 3 milyon lokasyon ≈ 230 MB.
MAX_CACHED_LOCATIONS = 3_000_000


class RouteCache:
    def __init__(self, warehouse, max_locations: int = MAX_CACHED_LOCATIONS):
        self.wh = warehouse
        self._cache: dict[frozenset, tuple[tuple[int, ...], float]] = {}
        self.hits = 0
        self.misses = 0
        self.max_locations = max_locations
        self._stored = 0
        self.flushes = 0

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
            # Sıralı liste: rota yalnızca kümeye bağlı olsun. (Eskiden list(key)
            # kullanılıyordu; frozenset'in gezinme sırası kümenin nasıl
            # kurulduğuna göre değişebildiği için NN'deki eşitlik çözümü ilk
            # görülen sıraya bağlıydı ve önbellek boşaltılınca sonuç değişebiliyordu.)
            locs = sorted(key)
            res = fast.route(locs, self.wh)             # derlenmiş, sonuç aynı
            if res is None:
                route, _ = nearest_neighbor_route(locs, self.wh)
                route, dist = two_opt_improve(route, self.wh)
            else:
                route, dist = res
            cached = (tuple(route), dist)
            if self._stored + len(key) > self.max_locations:
                self._cache.clear()
                self._stored = 0
                self.flushes += 1
            self._cache[key] = cached
            self._stored += len(key)
        else:
            self.hits += 1
        return list(cached[0]), cached[1]

    def distance(self, locations) -> float:
        return self.get(locations)[1]

    def __len__(self) -> int:
        return len(self._cache)
