# Algoritma karşılaştırması

Kaynak: `results/generated/results__s5__tpo0.05.json`  
Kod sürümü: `1d5dd37`  
Protokol: sipariş başına 0.05 sn eşit süre bütçesi, örnek başına 5 tohum, 2160 örnek, 72 grup  
Paralel işlem: 16

> **Uyarılar**
>
> - Süreler paralel koşumda ölçüldü; hız karşılaştırması için `--jobs 1` ile ayrı ölçüm gerekir.

## En iyi algoritma

| | DEPSO | RBRS-AE | RBRS-AE2 | ALNS | berabere |
|---|---|---|---|---|---|
| Grup (ortalama mesafe) | 0/72 | 0/72 | 0/72 | 72/72 | 0/72 |
| Örnek | 15/2160 | 48/2160 | 378/2160 | 1710/2160 | 9/2160 |

## İkili karşılaştırma

Ortalama fark: örnek bazında (A − B) / B. Negatif: A daha kısa mesafe.  
p: Wilcoxon işaretli sıralar testi (iki yönlü), Holm düzeltmeli; < 0,05 fark anlamlı.

| A | B | ortalama fark | A daha iyi | B daha iyi | eşit | p (Holm) |
|---|---|---|---|---|---|---|
| ALNS | DEPSO | %-6,36 | 2129 | 30 | 1 | < 0,001 |
| ALNS | RBRS-AE | %-3,82 | 2071 | 89 | 0 | < 0,001 |
| RBRS-AE | DEPSO | %-2,63 | 1722 | 435 | 3 | < 0,001 |
| RBRS-AE2 | RBRS-AE | %-2,48 | 1997 | 157 | 6 | < 0,001 |
| ALNS | RBRS-AE2 | %-1,38 | 1746 | 408 | 6 | < 0,001 |
| RBRS-AE2 | DEPSO | %-5,07 | 2110 | 50 | 0 | < 0,001 |

## Kırılımlar

### Sipariş sayısı

Her algoritmanın, örnekteki en iyi sonuca göre ortalama sapması (%):

| Sipariş sayısı | n | DEPSO | RBRS-AE | RBRS-AE2 | ALNS |
|---|---|---|---|---|---|
| 50 | 720 | 3,52 | 2,83 | 0,88 | 0,20 |
| 100 | 720 | 6,59 | 4,35 | 1,11 | 0,31 |
| 200 | 720 | 11,35 | 5,52 | 2,82 | 0,03 |

### Depo boyutu

Her algoritmanın, örnekteki en iyi sonuca göre ortalama sapması (%):

| Depo boyutu | n | DEPSO | RBRS-AE | RBRS-AE2 | ALNS |
|---|---|---|---|---|---|
| 5000 | 540 | 7,95 | 6,23 | 2,07 | 0,20 |
| 10000 | 540 | 8,08 | 4,34 | 1,68 | 0,14 |
| 15000 | 540 | 6,80 | 3,47 | 1,57 | 0,15 |
| 20000 | 540 | 5,79 | 2,89 | 1,10 | 0,24 |

### Blok sayısı

Her algoritmanın, örnekteki en iyi sonuca göre ortalama sapması (%):

| Blok sayısı | n | DEPSO | RBRS-AE | RBRS-AE2 | ALNS |
|---|---|---|---|---|---|
| 1 | 720 | 7,35 | 4,69 | 1,82 | 0,19 |
| 2 | 720 | 7,13 | 4,15 | 1,53 | 0,18 |
| 3 | 720 | 6,99 | 3,86 | 1,46 | 0,17 |

### Doluluk (%)

Her algoritmanın, örnekteki en iyi sonuca göre ortalama sapması (%):

| Doluluk (%) | n | DEPSO | RBRS-AE | RBRS-AE2 | ALNS |
|---|---|---|---|---|---|
| 40 | 360 | 7,31 | 4,27 | 1,59 | 0,15 |
| 50 | 360 | 7,44 | 4,27 | 1,56 | 0,20 |
| 60 | 360 | 7,00 | 4,31 | 1,57 | 0,19 |
| 70 | 360 | 6,85 | 4,05 | 1,53 | 0,25 |
| 80 | 360 | 7,19 | 4,16 | 1,64 | 0,15 |
| 90 | 360 | 7,14 | 4,35 | 1,75 | 0,15 |

## Tohumlar arası değişkenlik

Aynı örnekte farklı tohumlarla mesafenin değişim katsayısı (std / ortalama, %) ve en iyi–en kötü tohum farkı:

| Algoritma | ort. değişim katsayısı | ort. en iyi–en kötü fark |
|---|---|---|
| DEPSO | %1,63 | %4,03 |
| RBRS-AE | %1,68 | %4,10 |
| RBRS-AE2 | %1,56 | %3,83 |
| ALNS | %1,45 | %3,56 |

## Süre

| Algoritma | ortalama süre (sn) |
|---|---|
| DEPSO | 5,9 |
| RBRS-AE | 5,2 |
| RBRS-AE2 | 5,5 |
| ALNS | 5,9 |

Süre bütçeli koşumda süreler bütçeye yakın olmalı; paralel ölçümde süreler karşılaştırma için kullanılmamalı.
