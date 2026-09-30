# Algoritma karşılaştırması: deney protokolü

İlk 35 senaryo koşumu (ALNS 26–27/35 senaryoda en iyi) üç yöntemsel eksikle
alınmıştı. Bu belge eksikleri ve kodda nasıl giderildiklerini anlatır.

| Eksik | Neden sorun | Çözüm |
|---|---|---|
| Commit'lenmemiş kodla koşum | Sonucun hangi kodla alındığı bilinmez, tekrarlanamaz | Koşucular commit'lenmemiş değişiklik varsa başlamaz; sonuç dosyasına commit ve durum yazılır |
| Eşit olmayan iş bütçesi | RBRS-AE 100, DEPSO ve ALNS 500 iterasyon; ALNS ~2 kat uzun çalışıyor. Kalite farkının bir kısmı arama süresinden gelebilir | `--time-budget` / `--time-per-order`: üç algoritma aynı süreyi kullanır |
| Örnek başına tek tohum | Algoritmanın kendi rastgeleliği ölçülmüyor; fark şans olabilir | `--seeds N`: her örnek N tohumla; Wilcoxon testi |
| Süre paralel koşumda ölçüldü | 16 işlem aynı anda çalışırken süreler gürültülü | Hız karşılaştırması `--jobs 1` ile ayrı koşulur; rapor paralel ölçümü uyarır |

## Kod sürümü

`run_batch.py` ve `run_generated.py`, izlenen dosyalarda commit'lenmemiş
değişiklik varsa durur ve dosyaları listeler. Koşumların kendi çıktıları
(`results/`, `site/data/`) ve izlenmeyen dosyalar sayılmaz. Yalnızca deneme için
`--allow-dirty`; o zaman sonuç dosyasında `"dirty": true` yazar ve rapor uyarır.

## Eşit süre bütçesi

`time_limit` verilen algoritma iterasyon sınırına değil süreye göre durur:

- **DEPSO:** Süre dolunca iterasyon biter. Yerel arama eşiğindeki
  `It_cur / It_max` oranı yerine geçen süre oranı kullanılır.
- **RBRS-AE:** Bütçenin %70'i ana döngüye, kalanı son yerel iyileştirmeye
  ayrılır. "15 iterasyon iyileşme yoksa dur" kuralı bütçe modunda kapalıdır.
  Eleme oranı (%20 → %10) süre oranıyla azalır. Son yerel iyileştirme süre
  dolunca o ana kadarki en iyi hamleyle biter.
- **ALNS:** Süre dolunca durur; soğutma ve ağırlık güncellemesi aynen işler.

Taşma, bir iterasyon süresi kadardır (testte < 1 sn).

İki seçenek var:

- `--time-budget S`: her örnekte S saniye.
- `--time-per-order s`: k siparişlik örnekte k × s saniye (önerilen). Böylece
  200 siparişlik örnek 50 siparişlikten 4 kat fazla süre alır.

Bütçeli koşumda süreler paralel işlemde ölçülür. Tüm algoritmalar aynı yük
altında çalıştığı için eşitlik korunur, ama mutlak süreler tek işlemli ölçümle
karşılaştırılamaz.

## Çoklu tohum

`--seeds N` ile SOP ve FCFS bir kez, üç metasezgisel N farklı tohumla çözülür.
İlk tohum eski tek tohumlu koşumla aynıdır. Sonuçta örnek başına `td` tohumların
ortalamasıdır; ham değerler `td_seeds` ve `rt_seeds` alanlarında durur.

İlk gözlem: RBRS-AE farklı tohumlarla neredeyse aynı sonucu veriyor (50
siparişte 3 tohum: 756, 756, 755 LU). Rastgele bileşeni zayıf ve erken
yakınsıyor. ALNS'nin tohumlar arası farkı %2 düzeyinde.

## Rapor

```bash
python compare_algorithms.py results/compare__s5__tpo0.5
```

`karsilastirma.md` içinde:

- uyarılar (temiz olmayan kod, eşit olmayan bütçe, tek tohum, paralel süre)
- senaryo ve örnek bazında en iyi algoritma
- ikili ortalama fark ve Wilcoxon işaretli sıralar testi; üç karşılaştırma için
  Holm düzeltmesi
- sipariş sayısı ve satır sayısına göre kırılım
- tohumlar arası değişkenlik ve süre

Eski koşumun raporu: `results/karsilastirma.md`. Aynı üç uyarıyı gösterir;
Wilcoxon'a göre ALNS'nin hem DEPSO'dan hem RBRS-AE'den farkı anlamlı
(p < 0,001), RBRS-AE ile DEPSO arasındaki fark küçük (p = 0,023, DEPSO lehine).

## Komutlar

```bash
# 1) Adil kalite karşılaştırması: 35 senaryo, 5 örnek, 5 tohum, sipariş başına 0,5 sn
python run_batch.py --batch all --jobs 16 --seeds 5 --time-per-order 0.5
python compare_algorithms.py results/compare__s5__tpo0.5

# 2) Hız ölçümü: tek işlem, varsayılan ayarlar, birkaç senaryo
python run_batch.py --only 50_2_6,100_6_6,150_10_2,200_10_10 --n 3 --jobs 1
python compare_algorithms.py results/only.json

# 3) Kendi ızgaramızda aynısı
python run_generated.py --jobs 16 --seeds 5 --time-per-order 0.5 --k 50 100
python compare_algorithms.py results/generated/results__s5__tpo0.5.json
```

Süre tahmini (1): örnek başına 3 algoritma × 5 tohum × 0,5·k sn; 35 senaryo × 5
örnek, 16 paralel işlemle yaklaşık 3 saat.
