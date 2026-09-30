"""
algorithms/routing/fast.py
==========================
NN + 2-opt rota sezgiselinin derlenmiş (numba) sürümü.

Sonuç Python sürümüyle (nearest_neighbor.py + two_opt.py) BİREBİR aynıdır:
- Mesafeler aynı float32 matrisinden okunur ve float64'te aynı sırayla toplanır.
- NN'de eşit mesafeli adaylar arasında Python'daki `min(set)` davranışı
  korunur: adaylar Python kümesinin gezinme sırasıyla verilir, ilk en küçük
  seçilir.
- 2-opt aynı döngü sırası, aynı 1e-9 eşiği ve aynı durma kurallarıyla çalışır.
Test: tests/test_routing_fast_path.py.

numba kurulu değilse ya da ADFO_NO_NUMBA=1 ise kullanılmaz; çağıranlar eski
Python yoluna düşer (sonuç aynı, yalnızca yavaş).
"""

from __future__ import annotations

import os

import numpy as np

try:
    if os.environ.get('ADFO_NO_NUMBA') == '1':
        raise ImportError
    from numba import njit
    AVAILABLE = True
except ImportError:          # pragma: no cover - numba'sız ortam
    AVAILABLE = False


if AVAILABLE:
    @njit(cache=True)
    def _nn_2opt(order, depot, M, max_iterations, max_no_improvement):
        n = order.shape[0]
        route = np.empty(n + 2, dtype=np.int64)
        visited = np.zeros(n, dtype=np.bool_)
        route[0] = depot
        cur = depot
        for step in range(n):
            best = -1
            bd = 0.0
            for k in range(n):
                if not visited[k]:
                    d = np.float64(M[cur, order[k]])
                    if best == -1 or d < bd:
                        best = k
                        bd = d
            visited[best] = True
            cur = order[best]
            route[step + 1] = cur
        route[n + 1] = depot

        m = n + 2
        dist = 0.0
        for i in range(m - 1):
            dist += np.float64(M[route[i], route[i + 1]])
        if m <= 4:
            return route, dist

        no_imp = 0
        for _ in range(max_iterations):
            improved = False
            for i in range(1, m - 2):
                for j in range(i + 1, m - 1):
                    a = route[i - 1]
                    b = route[i]
                    c = route[j]
                    d = route[j + 1]
                    d_before = np.float64(M[a, b]) + np.float64(M[c, d])
                    d_after = np.float64(M[a, c]) + np.float64(M[b, d])
                    if d_after < d_before - 1e-9:
                        lo = i
                        hi = j
                        while lo < hi:
                            t = route[lo]
                            route[lo] = route[hi]
                            route[hi] = t
                            lo += 1
                            hi -= 1
                        dist += (d_after - d_before)
                        improved = True
            if not improved:
                no_imp += 1
                if no_imp >= max_no_improvement:
                    break
            else:
                no_imp = 0
        return route, dist


def route(locations, warehouse, max_iterations: int = 30,
          max_no_improvement: int = 2):
    """
    NN + 2-opt, derlenmiş. (rota, mesafe) ya da kullanılamıyorsa None döner.
    locations: ziyaret edilecek lokasyonlar (tekrar olabilir, depo hariç).
    """
    if not AVAILABLE or warehouse._matrix is None:
        return None
    # Python sürümüyle aynı aday sırası: nearest_neighbor_route içindeki
    # `remaining = set(list(set(locations)))` kümesinin gezinme sırası.
    remaining = set(list(set(locations)))
    if not remaining:
        return None
    idx = warehouse._matrix_idx
    try:
        order = np.fromiter((idx[l] for l in remaining), dtype=np.int64, count=len(remaining))
        depot = idx[warehouse.DEPOT]
    except KeyError:
        return None
    r, dist = _nn_2opt(order, depot, warehouse._matrix, max_iterations, max_no_improvement)
    locs = warehouse._matrix_locs
    return [locs[k] for k in r.tolist()], float(dist)
