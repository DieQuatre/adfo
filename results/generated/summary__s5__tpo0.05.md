# Parametrik ızgara — algoritma karşılaştırması

Kod sürümü: `fe49fc5`, 2160 örnek, protokol {'depso_iter': 500, 'n_seeds': 5, 'time_budget': None, 'time_per_order': 0.05}.

## Depo boyutuna göre

| grup | n | DEPSO LU | RBRS-AE LU | ALNS LU | DEPSO s | RBRS-AE s | ALNS s | en iyi (adet) |
|---|---|---|---|---|---|---|---|---|
| 5000 | 540 | 1668 | 1635 | 1525 | 5.9 | 4.8 | 5.8 | DEPSO 5, RBRS-AE 18, ALNS 516, berabere 1 |
| 10000 | 540 | 2676 | 2553 | 2437 | 5.9 | 5.1 | 5.9 | DEPSO 1, RBRS-AE 13, ALNS 526, berabere 0 |
| 15000 | 540 | 3349 | 3218 | 3091 | 5.9 | 5.3 | 5.9 | DEPSO 7, RBRS-AE 20, ALNS 511, berabere 2 |
| 20000 | 540 | 3989 | 3867 | 3741 | 5.9 | 5.5 | 5.9 | DEPSO 9, RBRS-AE 39, ALNS 492, berabere 0 |

## Koridor yapısına göre (blok sayısı)

| grup | n | DEPSO LU | RBRS-AE LU | ALNS LU | DEPSO s | RBRS-AE s | ALNS s | en iyi (adet) |
|---|---|---|---|---|---|---|---|---|
| 1 | 720 | 3385 | 3267 | 3112 | 5.9 | 5.1 | 5.9 | DEPSO 7, RBRS-AE 27, ALNS 684, berabere 2 |
| 2 | 720 | 2814 | 2711 | 2601 | 5.9 | 5.2 | 5.9 | DEPSO 6, RBRS-AE 28, ALNS 685, berabere 1 |
| 3 | 720 | 2561 | 2476 | 2382 | 5.9 | 5.3 | 5.9 | DEPSO 9, RBRS-AE 35, ALNS 676, berabere 0 |

## Doluluğa göre

| grup | n | DEPSO LU | RBRS-AE LU | ALNS LU | DEPSO s | RBRS-AE s | ALNS s | en iyi (adet) |
|---|---|---|---|---|---|---|---|---|
| 0.4 | 360 | 2912 | 2813 | 2692 | 5.9 | 5.2 | 5.9 | DEPSO 3, RBRS-AE 17, ALNS 340, berabere 0 |
| 0.5 | 360 | 2927 | 2819 | 2699 | 5.9 | 5.2 | 5.9 | DEPSO 5, RBRS-AE 14, ALNS 341, berabere 0 |
| 0.6 | 360 | 2905 | 2805 | 2686 | 5.9 | 5.2 | 5.9 | DEPSO 6, RBRS-AE 13, ALNS 340, berabere 1 |
| 0.7 | 360 | 2899 | 2801 | 2684 | 5.9 | 5.2 | 5.9 | DEPSO 6, RBRS-AE 17, ALNS 336, berabere 1 |
| 0.8 | 360 | 2956 | 2846 | 2726 | 5.9 | 5.2 | 5.9 | DEPSO 0, RBRS-AE 12, ALNS 347, berabere 1 |
| 0.9 | 360 | 2923 | 2825 | 2703 | 5.9 | 5.2 | 5.9 | DEPSO 2, RBRS-AE 17, ALNS 341, berabere 0 |

## Sipariş sayısına göre

| grup | n | DEPSO LU | RBRS-AE LU | ALNS LU | DEPSO s | RBRS-AE s | ALNS s | en iyi (adet) |
|---|---|---|---|---|---|---|---|---|
| 50 | 720 | 1429 | 1419 | 1386 | 2.5 | 1.8 | 2.5 | DEPSO 12, RBRS-AE 64, ALNS 642, berabere 2 |
| 100 | 720 | 2553 | 2493 | 2404 | 5.0 | 4.0 | 5.0 | DEPSO 10, RBRS-AE 22, ALNS 687, berabere 1 |
| 200 | 720 | 4779 | 4542 | 4305 | 10.0 | 9.8 | 10.1 | DEPSO 0, RBRS-AE 4, ALNS 716, berabere 0 |
