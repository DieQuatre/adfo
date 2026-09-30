# Algoritma karşılaştırması

Kaynak: `results\compare__s5__tpo0.5`  
Kod sürümü: `15f060e`  
Protokol: sipariş başına 0.5 sn eşit süre bütçesi, örnek başına 5 tohum, 175 örnek, 35 grup  
Paralel işlem: 16

> **Uyarılar**
>
> - Süreler paralel koşumda ölçüldü; hız karşılaştırması için `--jobs 1` ile ayrı ölçüm gerekir.

## En iyi algoritma

| | DEPSO | RBRS-AE | ALNS | berabere |
|---|---|---|---|---|
| Grup (ortalama mesafe) | 9/35 | 6/35 | 20/35 | 0/35 |
| Örnek | 55/175 | 28/175 | 92/175 | 0/175 |

## İkili karşılaştırma

Ortalama fark: örnek bazında (A − B) / B. Negatif: A daha kısa mesafe.  
p: Wilcoxon işaretli sıralar testi (iki yönlü), Holm düzeltmeli; < 0,05 fark anlamlı.

| A | B | ortalama fark | A daha iyi | B daha iyi | eşit | p (Holm) |
|---|---|---|---|---|---|---|
| ALNS | DEPSO | %-1,56 | 104 | 71 | 0 | 0,007 |
| ALNS | RBRS-AE | %-2,38 | 126 | 49 | 0 | < 0,001 |
| RBRS-AE | DEPSO | %+0,88 | 75 | 100 | 0 | 0,026 |

## Kırılımlar

### Sipariş sayısı

Her algoritmanın, örnekteki en iyi sonuca göre ortalama sapması (%):

| Sipariş sayısı | n | DEPSO | RBRS-AE | ALNS |
|---|---|---|---|---|
| 50 | 40 | 2,44 | 3,15 | 0,98 |
| 100 | 45 | 3,09 | 3,74 | 1,28 |
| 150 | 45 | 3,68 | 4,50 | 2,33 |
| 200 | 45 | 3,96 | 4,99 | 1,41 |

### Sipariş başına en fazla satır

Her algoritmanın, örnekteki en iyi sonuca göre ortalama sapması (%):

| Sipariş başına en fazla satır | n | DEPSO | RBRS-AE | ALNS |
|---|---|---|---|---|
| 2 | 55 | 6,16 | 4,98 | 1,37 |
| 6 | 60 | 3,29 | 4,01 | 0,88 |
| 10 | 60 | 0,74 | 3,44 | 2,28 |

## Tohumlar arası değişkenlik

Aynı örnekte farklı tohumlarla mesafenin değişim katsayısı (std / ortalama, %) ve en iyi–en kötü tohum farkı:

| Algoritma | ort. değişim katsayısı | ort. en iyi–en kötü fark |
|---|---|---|
| DEPSO | %1,42 | %3,50 |
| RBRS-AE | %1,57 | %3,88 |
| ALNS | %1,73 | %4,19 |

## Süre

| Algoritma | ortalama süre (sn) |
|---|---|
| DEPSO | 63,9 |
| RBRS-AE | 60,6 |
| ALNS | 64,0 |

Süre bütçeli koşumda süreler bütçeye yakın olmalı; paralel ölçümde süreler karşılaştırma için kullanılmamalı.
