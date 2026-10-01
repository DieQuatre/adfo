# Algoritma karşılaştırması

Kaynak: `results\generated\results__s5__tpo0.05.json`  
Kod sürümü: `fe49fc5`  
Protokol: sipariş başına 0.05 sn eşit süre bütçesi, örnek başına 5 tohum, 2160 örnek, 72 grup  
Paralel işlem: 16

> **Uyarılar**
>
> - Süreler paralel koşumda ölçüldü; hız karşılaştırması için `--jobs 1` ile ayrı ölçüm gerekir.

## En iyi algoritma

| | DEPSO | RBRS-AE | ALNS | berabere |
|---|---|---|---|---|
| Grup (ortalama mesafe) | 0/72 | 0/72 | 72/72 | 0/72 |
| Örnek | 22/2160 | 90/2160 | 2045/2160 | 3/2160 |

## İkili karşılaştırma

Ortalama fark: örnek bazında (A − B) / B. Negatif: A daha kısa mesafe.  
p: Wilcoxon işaretli sıralar testi (iki yönlü), Holm düzeltmeli; < 0,05 fark anlamlı.

| A | B | ortalama fark | A daha iyi | B daha iyi | eşit | p (Holm) |
|---|---|---|---|---|---|---|
| ALNS | DEPSO | %-6,41 | 2130 | 30 | 0 | < 0,001 |
| ALNS | RBRS-AE | %-3,98 | 2061 | 96 | 3 | < 0,001 |
| RBRS-AE | DEPSO | %-2,51 | 1702 | 457 | 1 | < 0,001 |

## Kırılımlar

### Sipariş sayısı

Her algoritmanın, örnekteki en iyi sonuca göre ortalama sapması (%):

| Sipariş sayısı | n | DEPSO | RBRS-AE | ALNS |
|---|---|---|---|---|
| 50 | 720 | 3,36 | 2,69 | 0,09 |
| 100 | 720 | 6,53 | 4,25 | 0,07 |
| 200 | 720 | 11,36 | 5,91 | 0,00 |

### Depo boyutu

Her algoritmanın, örnekteki en iyi sonuca göre ortalama sapması (%):

| Depo boyutu | n | DEPSO | RBRS-AE | ALNS |
|---|---|---|---|---|
| 5000 | 540 | 8,06 | 6,40 | 0,06 |
| 10000 | 540 | 8,12 | 4,33 | 0,02 |
| 15000 | 540 | 6,78 | 3,60 | 0,05 |
| 20000 | 540 | 5,37 | 2,80 | 0,08 |

### Blok sayısı

Her algoritmanın, örnekteki en iyi sonuca göre ortalama sapması (%):

| Blok sayısı | n | DEPSO | RBRS-AE | ALNS |
|---|---|---|---|---|
| 1 | 720 | 7,34 | 4,84 | 0,05 |
| 2 | 720 | 7,08 | 4,14 | 0,05 |
| 3 | 720 | 6,82 | 3,88 | 0,06 |

## Tohumlar arası değişkenlik

Aynı örnekte farklı tohumlarla mesafenin değişim katsayısı (std / ortalama, %) ve en iyi–en kötü tohum farkı:

| Algoritma | ort. değişim katsayısı | ort. en iyi–en kötü fark |
|---|---|---|
| DEPSO | %1,62 | %3,99 |
| RBRS-AE | %1,74 | %4,27 |
| ALNS | %1,42 | %3,48 |

## Süre

| Algoritma | ortalama süre (sn) |
|---|---|
| DEPSO | 5,9 |
| RBRS-AE | 5,2 |
| ALNS | 5,9 |

Süre bütçeli koşumda süreler bütçeye yakın olmalı; paralel ölçümde süreler karşılaştırma için kullanılmamalı.
