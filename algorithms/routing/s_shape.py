"""
algorithms/routing/s_shape.py
==============================
GERÇEK S-Shape (traversal) heuristic — paper'ın benchmark routing yöntemi.

S-Shape kuralı (Roodbergen & de Koster, klasik tanım):
- Picker depot'tan başlar.
- İçinde pick olan her aisle TAM kat edilir (traversal): bir uçtan girilir,
  DİĞER uçtan çıkılır. Picker aisle içinde "en kısa yol" seçemez.
- Aisle'lar sırayla ziyaret edilir, giriş yönü dönüşümlü (S şekli).
- İçinde pick olmayan aisle'lar atlanır.
- İlk aisle'a depot'a yakın uçtan girilir.
- Son aisle'da (ve tek aisle varsa) TAM traversal yerine en uzak pick'e gidip
  geri dönülür (return traversal) — bu S-shape'in standart istisnasıdır.

Bu bilinçli olarak optimal-olmayan bir BENCHMARK'tır. NN+2opt / DEPSO bunu geçmelidir.

Geometri (bu depoda):
- Aisle'lar YATAY: sabit y, x boyunca uzanır. Aisle uçları x=0 (sol) ve x=94 (sağ).
- Aisle'lar y = [1.5, 4.5, ..., 28.5]; aisle 0 depot'a en yakın.
- Depot: x=96, y=0 (sağda). Yani sağ uç (x=94) depot'a yakın.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.warehouse import Warehouse


def s_shape_route(locations: list[int], warehouse: Warehouse) -> tuple[list[int], float]:
    """
    Gerçek S-Shape (traversal) rotası. Koordinat bazlı mesafe hesabı.

    Döndürür: (route, total_distance)
    """
    if not locations:
        return [warehouse.DEPOT, warehouse.DEPOT], 0.0

    unique_locs = list(set(locations))

    aisles_with_picks: dict[int, list[int]] = {}
    for loc in unique_locs:
        a = warehouse._aisle_of(loc)
        if a is None:
            continue
        aisles_with_picks.setdefault(a, []).append(loc)

    if not aisles_with_picks:
        return [warehouse.DEPOT, warehouse.DEPOT], 0.0

    sorted_aisles = sorted(aisles_with_picks.keys())

    X_LEFT  = warehouse.cross_aisle_x[0]    # 0.0
    X_RIGHT = warehouse.cross_aisle_x[-1]   # 94.0

    depot_x, depot_y = warehouse.depot_x, warehouse.depot_y

    # Depot sağda (x=96 > 94) → ilk aisle'a SAĞDAN girmek depot'a yakın.
    # enter_right = True → sağdan (x=94) gir, sola (x=0) çık.
    depot_near_right = (depot_x >= (X_LEFT + X_RIGHT) / 2)

    route = [warehouse.DEPOT]
    total = 0.0
    cur_x, cur_y = depot_x, depot_y
    n = len(sorted_aisles)

    for idx, aisle in enumerate(sorted_aisles):
        locs = aisles_with_picks[aisle]
        ay = warehouse.aisle_y[aisle]

        # Giriş yönü: ilk aisle depot'a yakın uçtan; sonra dönüşümlü
        if depot_near_right:
            enter_right = (idx % 2 == 0)   # çift: sağdan gir
        else:
            enter_right = (idx % 2 == 1)

        entry_x = X_RIGHT if enter_right else X_LEFT
        exit_x  = X_LEFT  if enter_right else X_RIGHT

        # Pick'leri geçiş yönünde sırala
        locs.sort(key=lambda l: warehouse.coords(l)[0], reverse=enter_right)

        is_last = (idx == n - 1)

        if not is_last:
            # TAM TRAVERSAL: giriş ucundan gir, tüm aisle'ı kat et, çıkış ucundan çık
            total += abs(entry_x - cur_x) + abs(ay - cur_y)  # girişe git
            for loc in locs:
                route.append(loc)
            total += abs(exit_x - entry_x)  # aisle'ı tam kat et
            cur_x, cur_y = exit_x, ay
        else:
            # SON AISLE: return traversal — en uzak pick'e git, geri dön
            total += abs(entry_x - cur_x) + abs(ay - cur_y)  # girişe git
            for loc in locs:
                route.append(loc)
            xs = [warehouse.coords(l)[0] for l in locs]
            # Giriş ucundan en uzak pick
            if enter_right:
                farthest_x = min(xs)   # sağdan girdi, en sol pick en uzak
            else:
                farthest_x = max(xs)   # soldan girdi, en sağ pick en uzak
            total += 2 * abs(farthest_x - entry_x)  # git-gel
            cur_x, cur_y = entry_x, ay

    # Depot'a dön
    total += abs(depot_x - cur_x) + abs(depot_y - cur_y)
    route.append(warehouse.DEPOT)

    return route, total
