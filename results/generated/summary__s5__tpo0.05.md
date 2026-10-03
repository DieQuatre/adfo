# Parametrik ızgara — algoritma karşılaştırması

Kod sürümü: `1d5dd37`, 2160 örnek, protokol {'depso_iter': 500, 'n_seeds': 5, 'time_budget': None, 'time_per_order': 0.05}.

## Depo boyutuna göre

| grup | n | DEPSO LU | RBRS-AE LU | RBRS-AE2 LU | ALNS LU | DEPSO s | RBRS-AE s | RBRS-AE2 s | ALNS s | en iyi (adet) |
|---|---|---|---|---|---|---|---|---|---|---|
| 5000 | 540 | 1674 | 1640 | 1570 | 1534 | 5.9 | 4.9 | 5.4 | 5.9 | DEPSO 8, RBRS-AE 9, RBRS-AE2 74, ALNS 445, berabere 4 |
| 10000 | 540 | 2677 | 2557 | 2490 | 2441 | 5.9 | 5.1 | 5.5 | 5.9 | DEPSO 0, RBRS-AE 8, RBRS-AE2 93, ALNS 439, berabere 0 |
| 15000 | 540 | 3351 | 3215 | 3156 | 3098 | 5.9 | 5.3 | 5.6 | 5.9 | DEPSO 7, RBRS-AE 14, RBRS-AE2 81, ALNS 433, berabere 5 |
| 20000 | 540 | 3951 | 3804 | 3736 | 3693 | 5.9 | 5.3 | 5.6 | 5.9 | DEPSO 0, RBRS-AE 17, RBRS-AE2 130, ALNS 393, berabere 0 |

## Koridor yapısına göre (blok sayısı)

| grup | n | DEPSO LU | RBRS-AE LU | RBRS-AE2 LU | ALNS LU | DEPSO s | RBRS-AE s | RBRS-AE2 s | ALNS s | en iyi (adet) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 720 | 3377 | 3251 | 3166 | 3106 | 5.9 | 5.1 | 5.5 | 5.9 | DEPSO 6, RBRS-AE 18, RBRS-AE2 113, ALNS 578, berabere 5 |
| 2 | 720 | 2810 | 2705 | 2642 | 2599 | 5.9 | 5.2 | 5.5 | 5.9 | DEPSO 5, RBRS-AE 13, RBRS-AE2 137, ALNS 564, berabere 1 |
| 3 | 720 | 2552 | 2456 | 2406 | 2369 | 5.9 | 5.2 | 5.6 | 5.9 | DEPSO 4, RBRS-AE 17, RBRS-AE2 128, ALNS 568, berabere 3 |

## Doluluğa göre

| grup | n | DEPSO LU | RBRS-AE LU | RBRS-AE2 LU | ALNS LU | DEPSO s | RBRS-AE s | RBRS-AE2 s | ALNS s | en iyi (adet) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.4 | 360 | 2908 | 2797 | 2728 | 2680 | 5.9 | 5.1 | 5.5 | 5.9 | DEPSO 3, RBRS-AE 7, RBRS-AE2 61, ALNS 288, berabere 1 |
| 0.5 | 360 | 2918 | 2801 | 2735 | 2691 | 5.9 | 5.1 | 5.5 | 5.9 | DEPSO 2, RBRS-AE 6, RBRS-AE2 66, ALNS 285, berabere 1 |
| 0.6 | 360 | 2897 | 2797 | 2729 | 2682 | 5.9 | 5.2 | 5.5 | 5.9 | DEPSO 3, RBRS-AE 9, RBRS-AE2 65, ALNS 280, berabere 3 |
| 0.7 | 360 | 2893 | 2787 | 2723 | 2681 | 5.9 | 5.2 | 5.5 | 5.9 | DEPSO 4, RBRS-AE 12, RBRS-AE2 72, ALNS 270, berabere 2 |
| 0.8 | 360 | 2946 | 2832 | 2768 | 2720 | 5.9 | 5.2 | 5.5 | 5.9 | DEPSO 1, RBRS-AE 8, RBRS-AE2 59, ALNS 290, berabere 2 |
| 0.9 | 360 | 2918 | 2809 | 2746 | 2695 | 5.9 | 5.2 | 5.5 | 5.9 | DEPSO 2, RBRS-AE 6, RBRS-AE2 55, ALNS 297, berabere 0 |

## Sipariş sayısına göre

| grup | n | DEPSO LU | RBRS-AE LU | RBRS-AE2 LU | ALNS LU | DEPSO s | RBRS-AE s | RBRS-AE2 s | ALNS s | en iyi (adet) |
|---|---|---|---|---|---|---|---|---|---|---|
| 50 | 720 | 1429 | 1419 | 1394 | 1385 | 2.5 | 1.8 | 1.9 | 2.5 | DEPSO 12, RBRS-AE 40, RBRS-AE2 154, ALNS 505, berabere 9 |
| 100 | 720 | 2547 | 2490 | 2419 | 2402 | 5.0 | 3.9 | 4.5 | 5.0 | DEPSO 3, RBRS-AE 4, RBRS-AE2 186, ALNS 527, berabere 0 |
| 200 | 720 | 4763 | 4502 | 4401 | 4288 | 10.1 | 9.8 | 10.2 | 10.1 | DEPSO 0, RBRS-AE 4, RBRS-AE2 38, ALNS 678, berabere 0 |
