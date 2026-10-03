# Algoritma karşılaştırması

Kaynak: `results/compare__s5__tpo0.05`  
Kod sürümü: `1d5dd37`  
Protokol: sipariş başına 0.05 sn eşit süre bütçesi, örnek başına 5 tohum, 175 örnek, 35 grup  
Paralel işlem: 16

> **Uyarılar**
>
> - Süreler paralel koşumda ölçüldü; hız karşılaştırması için `--jobs 1` ile ayrı ölçüm gerekir.

## En iyi algoritma

| | DEPSO | RBRS-AE | RBRS-AE2 | ALNS | berabere |
|---|---|---|---|---|---|
| Grup (ortalama mesafe) | 7/35 | 0/35 | 20/35 | 8/35 | 0/35 |
| Örnek | 28/175 | 6/175 | 77/175 | 56/175 | 8/175 |

## İkili karşılaştırma

Ortalama fark: örnek bazında (A − B) / B. Negatif: A daha kısa mesafe.  
p: Wilcoxon işaretli sıralar testi (iki yönlü), Holm düzeltmeli; < 0,05 fark anlamlı.

| A | B | ortalama fark | A daha iyi | B daha iyi | eşit | p (Holm) |
|---|---|---|---|---|---|---|
| ALNS | DEPSO | %-2,36 | 114 | 60 | 1 | < 0,001 |
| ALNS | RBRS-AE | %-2,00 | 123 | 52 | 0 | < 0,001 |
| RBRS-AE | DEPSO | %-0,34 | 100 | 74 | 1 | 0,074 |
| RBRS-AE2 | RBRS-AE | %-2,58 | 157 | 11 | 7 | < 0,001 |
| ALNS | RBRS-AE2 | %+0,59 | 66 | 108 | 1 | < 0,001 |
| RBRS-AE2 | DEPSO | %-2,93 | 139 | 35 | 1 | < 0,001 |

## Kırılımlar

### Sipariş sayısı

Her algoritmanın, örnekteki en iyi sonuca göre ortalama sapması (%):

| Sipariş sayısı | n | DEPSO | RBRS-AE | RBRS-AE2 | ALNS |
|---|---|---|---|---|---|
| 50 | 40 | 2,84 | 3,13 | 0,76 | 0,89 |
| 100 | 45 | 4,45 | 3,88 | 0,84 | 1,89 |
| 150 | 45 | 4,90 | 4,12 | 1,16 | 2,03 |
| 200 | 45 | 4,64 | 3,89 | 1,33 | 1,48 |

### Sipariş başına en fazla satır

Her algoritmanın, örnekteki en iyi sonuca göre ortalama sapması (%):

| Sipariş başına en fazla satır | n | DEPSO | RBRS-AE | RBRS-AE2 | ALNS |
|---|---|---|---|---|---|
| 2 | 55 | 7,20 | 4,85 | 1,45 | 1,09 |
| 6 | 60 | 4,09 | 3,64 | 0,89 | 1,18 |
| 10 | 60 | 1,69 | 2,92 | 0,79 | 2,47 |

## Tohumlar arası değişkenlik

Aynı örnekte farklı tohumlarla mesafenin değişim katsayısı (std / ortalama, %) ve en iyi–en kötü tohum farkı:

| Algoritma | ort. değişim katsayısı | ort. en iyi–en kötü fark |
|---|---|---|
| DEPSO | %1,39 | %3,40 |
| RBRS-AE | %1,83 | %4,48 |
| RBRS-AE2 | %1,79 | %4,39 |
| ALNS | %2,05 | %5,02 |

## Süre

| Algoritma | ortalama süre (sn) |
|---|---|
| DEPSO | 6,4 |
| RBRS-AE | 5,8 |
| RBRS-AE2 | 6,1 |
| ALNS | 6,4 |

Süre bütçeli koşumda süreler bütçeye yakın olmalı; paralel ölçümde süreler karşılaştırma için kullanılmamalı.
