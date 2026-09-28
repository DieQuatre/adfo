# Parametrik ızgara — algoritma karşılaştırması

Kod sürümü: `9a2108c`, 84 örnek.

## Depo boyutuna göre

| grup | n | DEPSO LU | RBRS-AE LU | ALNS LU | DEPSO s | RBRS-AE s | ALNS s | en iyi (adet) |
|---|---|---|---|---|---|---|---|---|
| 5000 | 24 | 914 | 906 | 876 | 11.7 | 5.7 | 18.1 | DEPSO 3, RBRS-AE 7, ALNS 14, berabere 0 |
| 10000 | 24 | 1354 | 1353 | 1316 | 14.5 | 6.2 | 24.1 | DEPSO 3, RBRS-AE 3, ALNS 16, berabere 2 |
| 15000 | 18 | 1429 | 1412 | 1402 | 7.1 | 3.4 | 16.6 | DEPSO 2, RBRS-AE 5, ALNS 11, berabere 0 |
| 20000 | 18 | 1650 | 1622 | 1616 | 7.0 | 3.3 | 16.9 | DEPSO 1, RBRS-AE 8, ALNS 7, berabere 2 |

## Koridor yapısına göre (blok sayısı)

| grup | n | DEPSO LU | RBRS-AE LU | ALNS LU | DEPSO s | RBRS-AE s | ALNS s | en iyi (adet) |
|---|---|---|---|---|---|---|---|---|
| 1 | 24 | 1488 | 1478 | 1462 | 6.5 | 2.7 | 12.9 | DEPSO 4, RBRS-AE 9, ALNS 10, berabere 1 |
| 2 | 36 | 1349 | 1331 | 1300 | 15.6 | 7.4 | 26.0 | DEPSO 3, RBRS-AE 9, ALNS 22, berabere 2 |
| 3 | 24 | 1066 | 1061 | 1043 | 6.8 | 3.1 | 15.4 | DEPSO 2, RBRS-AE 5, ALNS 16, berabere 1 |

## Doluluğa göre

| grup | n | DEPSO LU | RBRS-AE LU | ALNS LU | DEPSO s | RBRS-AE s | ALNS s | en iyi (adet) |
|---|---|---|---|---|---|---|---|---|
| 0.5 | 28 | 1297 | 1294 | 1268 | 10.6 | 3.6 | 16.8 | DEPSO 2, RBRS-AE 7, ALNS 17, berabere 2 |
| 0.7 | 28 | 1323 | 1313 | 1288 | 9.9 | 4.9 | 20.3 | DEPSO 2, RBRS-AE 8, ALNS 16, berabere 2 |
| 0.9 | 28 | 1304 | 1280 | 1264 | 11.0 | 5.9 | 20.7 | DEPSO 5, RBRS-AE 8, ALNS 15, berabere 0 |

## Sipariş sayısına göre

| grup | n | DEPSO LU | RBRS-AE LU | ALNS LU | DEPSO s | RBRS-AE s | ALNS s | en iyi (adet) |
|---|---|---|---|---|---|---|---|---|
| 50 | 72 | 1252 | 1239 | 1226 | 6.7 | 2.8 | 14.6 | DEPSO 9, RBRS-AE 23, ALNS 36, berabere 4 |
| 100 | 12 | 1644 | 1638 | 1554 | 33.0 | 16.8 | 47.1 | DEPSO 0, RBRS-AE 0, ALNS 12, berabere 0 |
