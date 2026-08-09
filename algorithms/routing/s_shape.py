"""
algorithms/routing/s_shape.py
==============================
S-Shape (traversal) heuristic — Roodbergen & de Koster (2001).
Paper'ın SOP ve FCFS benchmark'larında kullandığı picker routing yöntemi.

TANIM (gerçek S-shape)
----------------------
- Picker depot'tan çıkar.
- Pick içeren her koridor BAŞTAN SONA geçilir. Koridorun pick olmayan kısmı
  da yürünür — S-shape'i optimal rotadan ayıran ve maliyetini yaratan şey
  tam olarak budur.
- Bloklar depot'a yakın olandan uzağa doğru işlenir. Her blokta, pick içeren
  koridorlar sırayla ve yön değiştirerek (S çizerek) geçilir.
- Bir bloktaki SON koridor, picker'ın bir sonraki adım için doğru kapıda
  kalması gerekiyorsa tam geçilmez: içeri girilir, en derin pick alınır ve
  aynı kapıdan geri çıkılır.
- Depot'a dönülür.

ÖNCEKİ SÜRÜMDEN FARKI
---------------------
Eski implementasyon koridoru baştan sona geçmiyordu; yalnızca pick'leri x'e
göre sıralayıp aralarını `warehouse.dist_m()` ile, yani EN KISA YOL
mesafesiyle topluyordu. Bu bir S-shape değil, neredeyse optimal bir rotaydı.
Sonucu: SOP/FCFS baseline'ları olduğundan iyi görünüyor, DEPSO'nun bu
baseline'lara göre kazanç oranı sistematik olarak küçülüyordu.

DÖNÜŞ DEĞERİ
------------
(route, distance)
  route    : ziyaret sırasına göre lokasyon ID'leri, başta ve sonda DEPOT.
  distance : gerçek S-shape yürüme mesafesi.

NOT: `distance`, `route` üzerindeki nokta-nokta en kısa yol mesafelerinin
toplamından BÜYÜKTÜR. Aradaki fark, koridorların pick içermeyen kısımlarında
yürünen yoldur ve S-shape'in tanımı gereği maliyete dahildir. Bu nedenle
`compute_route_distance(route, wh)` ile bu değeri karşılaştırmayın.

GEOMETRİ VARSAYIMLARI (core/warehouse.py ile aynı)
--------------------------------------------------
- Picking koridoru i: y = aisle_y[i] sabit, x boyunca uzanır.
- Cross aisle'lar sabit x = cross_aisle_x[b] konumlarında, y boyunca uzanır.
- Blok b'nin kapıları: cross_aisle_x[b] (uzak) ve cross_aisle_x[b+1] (yakın).
- Depot (depot_x, 0); y=0 ön koridoru tüm cross aisle'ları birbirine bağlar.
"""

from __future__ import annotations

from collections import defaultdict
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.warehouse import Warehouse


def _block_of(warehouse: Warehouse, loc_id: int) -> int:
    """Lokasyonun hangi blokta olduğunu döner (0..num_blocks-1)."""
    return warehouse.get_location(loc_id).rack // warehouse.racks_per_block


def s_shape_route(locations: list[int],
                  warehouse: Warehouse) -> tuple[list[int], float]:
    """Bir batch'in lokasyonları için S-shape turu kurar."""
    depot = warehouse.DEPOT
    if not locations:
        return [depot, depot], 0.0

    # (blok, koridor) -> [(x, loc_id), ...]
    picks: dict[tuple[int, int], list[tuple[float, int]]] = defaultdict(list)
    for loc in set(locations):
        aisle = warehouse._aisle_of(loc)
        if aisle is None:          # depot veya geçersiz
            continue
        x, _ = warehouse.coords(loc)
        picks[(_block_of(warehouse, loc), aisle)].append((x, loc))

    if not picks:
        return [depot, depot], 0.0

    gates = warehouse.cross_aisle_x        # ör. [0, 30, 62, 94]
    aisle_y = warehouse.aisle_y
    depot_x, depot_y = warehouse.depot_x, warehouse.depot_y

    # Depot en sağda → bloklar sağdan (yüksek indeks) sola doğru işlenir
    blocks = sorted({b for b, _ in picks}, reverse=True)

    route: list[int] = [depot]
    total = 0.0
    cur_x, cur_y = depot_x, depot_y

    for block_pos, b in enumerate(blocks):
        entry_x = gates[b + 1]             # depot'a yakın kapı
        exit_x = gates[b]                  # uzak kapı
        is_last_block = (block_pos == len(blocks) - 1)

        # Bu blok bitince hangi kapıda olmalıyız?
        #   son blok değilse: uzak kapı (bir sonraki bloğa geçmek için)
        #   son blok ise:     yakın kapı (depot'a dönmek için)
        need_x = entry_x if is_last_block else exit_x

        aisles = sorted(a for bb, a in picks if bb == b)
        n = len(aisles)

        # n koridorun HEPSİ tam geçilirse hangi kapıda biteriz?
        end_after_full = entry_x if n % 2 == 0 else exit_x
        traverse_all = (end_after_full == need_x)

        # Bloğun giriş kapısına git (x boyunca, mevcut y'de)
        total += abs(cur_x - entry_x)
        cur_x = entry_x
        side = entry_x

        for j, aisle in enumerate(aisles):
            y = aisle_y[aisle]
            total += abs(cur_y - y)        # cross aisle boyunca
            cur_y = y

            sub = sorted(picks[(b, aisle)])          # x'e göre artan
            is_last_aisle = (j == n - 1)

            if is_last_aisle and not traverse_all:
                # Gir-çık: en derin pick'e kadar git, aynı kapıdan dön
                if side > exit_x:                    # yakın (sağ) kapıdayız
                    deepest_x = sub[0][0]            # en küçük x en derin
                    visit = [loc for _, loc in reversed(sub)]
                else:                                # uzak (sol) kapıdayız
                    deepest_x = sub[-1][0]
                    visit = [loc for _, loc in sub]
                total += 2 * abs(side - deepest_x)
                route.extend(visit)
                cur_x = side                         # taraf değişmedi
            else:
                # TAM geçiş: kapıdan kapıya, boş kısımlar dahil
                other = exit_x if side == entry_x else entry_x
                visit = ([loc for _, loc in reversed(sub)] if side > other
                         else [loc for _, loc in sub])
                total += abs(side - other)
                route.extend(visit)
                side = other
                cur_x = other

        # Blok sonunda gereken kapıda değilsek oraya geç
        if cur_x != need_x:
            total += abs(cur_x - need_x)
            cur_x = need_x

    # Depot'a dön: cross aisle boyunca ön koridora, sonra x boyunca depot'a
    total += abs(cur_y - depot_y)
    total += abs(cur_x - depot_x)
    route.append(depot)

    return route, total


if __name__ == "__main__":
    wh = Warehouse()

    test_locs = [100, 1500, 3700, 5200, 6800, 800, 2400, 4100]
    route, dist = s_shape_route(test_locs, wh)
    print(f"S-Shape rotasi:   {route}")
    print(f"S-Shape mesafesi: {dist:.2f} LU")

    from algorithms.routing.two_opt import nn_then_2opt
    nn2opt_route, nn2opt_dist = nn_then_2opt(test_locs, wh)
    print(f"NN+2opt:          {nn2opt_dist:.2f} LU")
    print(f"S-Shape fazlasi:  {(dist - nn2opt_dist) / nn2opt_dist * 100:+.1f}%")
