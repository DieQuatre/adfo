# Algoritma karşılaştırması

Kaynak: `results`  
Kod sürümü: `9a2108c`  
Protokol: iterasyon sınırlı (DEPSO 500, RBRS-AE ve ALNS config.py), örnek başına 1 tohum, 175 örnek, 35 grup  
Paralel işlem: kayıtlı değil

> **Uyarılar**
>
> - Kod durumu kayıtlı değil (eski koşum).
> - Algoritmaların iş bütçesi eşit değil (iterasyon sınırları farklı); kalite farkının bir kısmı arama süresinden gelebilir.
> - Örnek başına tek tohum: algoritmanın kendi rastgeleliği ölçülmüyor.
> - Süreler paralel koşumda ölçüldü; hız karşılaştırması için `--jobs 1` ile ayrı ölçüm gerekir.

## En iyi algoritma

| | DEPSO | RBRS-AE | ALNS | berabere |
|---|---|---|---|---|
| Grup (ortalama mesafe) | 6/35 | 3/35 | 26/35 | 0/35 |
| Örnek | 32/175 | 15/175 | 124/175 | 4/175 |

## İkili karşılaştırma

Ortalama fark: örnek bazında (A − B) / B. Negatif: A daha kısa mesafe.  
p: Wilcoxon işaretli sıralar testi (iki yönlü), Holm düzeltmeli; < 0,05 fark anlamlı.

| A | B | ortalama fark | A daha iyi | B daha iyi | eşit | p (Holm) |
|---|---|---|---|---|---|---|
| ALNS | DEPSO | %-3,95 | 134 | 39 | 2 | < 0,001 |
| ALNS | RBRS-AE | %-4,26 | 147 | 28 | 0 | < 0,001 |
| RBRS-AE | DEPSO | %+0,37 | 77 | 96 | 2 | 0,023 |

## Kırılımlar

### Sipariş sayısı

Her algoritmanın, örnekteki en iyi sonuca göre ortalama sapması (%):

| Sipariş sayısı | n | DEPSO | RBRS-AE | ALNS |
|---|---|---|---|---|
| 50 | 40 | 2,34 | 3,24 | 1,04 |
| 100 | 45 | 4,23 | 4,53 | 0,69 |
| 150 | 45 | 5,14 | 5,65 | 0,56 |
| 200 | 45 | 7,95 | 7,42 | 0,21 |

### Sipariş başına en fazla satır

Her algoritmanın, örnekteki en iyi sonuca göre ortalama sapması (%):

| Sipariş başına en fazla satır | n | DEPSO | RBRS-AE | ALNS |
|---|---|---|---|---|
| 2 | 55 | 7,39 | 5,39 | 0,64 |
| 6 | 60 | 5,67 | 5,91 | 0,35 |
| 10 | 60 | 2,11 | 4,50 | 0,84 |

## Süre

| Algoritma | ortalama süre (sn) |
|---|---|
| DEPSO | 167,3 |
| RBRS-AE | 194,1 |
| ALNS | 376,5 |

Süre bütçeli koşumda süreler bütçeye yakın olmalı; paralel ölçümde süreler karşılaştırma için kullanılmamalı.
