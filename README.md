# Depoda sipariş toplama: DEPSO · RBRS-AE · RBRS-AE2 · ALNS

Bir depoda siparişleri hazırlayan kişi (toplayıcı) arabasıyla raflar arasında
dolaşıp ürünleri toplar ve zamanının büyük kısmını yürüyerek geçirir. Bu proje
aynı siparişleri daha az yürüyerek toplamanın yollarını arar. Üç karar birlikte
ele alınır:

- **Storage location assignment:** ürün hangi rafa konmalı?
- **Order batching:** hangi siparişler aynı turda toplanmalı?
- **Picker routing:** bir turda raflar hangi sırayla gezilmeli?

Repoda dört algoritma var. Hepsi aynı depo modelini, aynı araba kapasitesini
(100 ağırlık birimi) ve aynı rota hesabını (en yakın komşu + 2-opt) kullanır.

| Algoritma | Kısaca | Kod |
|---|---|---|
| DEPSO | Kübler, Glock ve Bauernhansl'ın (2020) yöntemi; projenin başlangıç noktası | `algorithms/depso.py` |
| RBRS-AE | Bizim ilk yöntemimiz: pişmanlık sırasıyla yerleştirme, verimsiz turları sökme | `algorithms/rbrs_ae.py` |
| RBRS-AE2 | RBRS-AE'nin iyileştirilmiş sürümü: çeşitli sökme kuralları, pişmanlıkla geri yerleştirme | `algorithms/rbrs_ae2.py` |
| ALNS | Uyarlamalı büyük komşuluk araması: sökme ve kurma yöntemlerinden işe yarayanı daha sık seçer | `algorithms/alns.py` |

Karşılaştırma için iki basit kural da var: SOP (her sipariş ayrı tur) ve FCFS
(geliş sırasına göre doldur).

**Web sitesi (Raf Arası):** https://diequatre.github.io/adfo/
Algoritmaların rotalarını, deney sonuçlarını ve tarayıcıda çalışan bir
"Kendin dene" bölümünü içerir.

## Sonuçlar

Bütün karşılaştırmalarda algoritmalara aynı süre verildi (sipariş başına
0,05 sn), her örnek 5 farklı tohumla çözüldü ve farklar Wilcoxon testiyle
sınandı. Kod sürümü: `1d5dd37`. Negatif fark, daha kısa yol demektir.

### Kübler'in deney senaryoları (35 senaryo × 5 örnek)

| | DEPSO | RBRS-AE | RBRS-AE2 | ALNS |
|---|---|---|---|---|
| En kısa yolu bulduğu örnek | 28 | 6 | **77** | 56 |

- RBRS-AE2, RBRS-AE'den %2,6 kısa (175 örneğin 157'sinde), ALNS'den %0,6 kısa.
- RBRS-AE ile DEPSO arasındaki fark anlamlı değil.
- Rapor: `results/compare__s5__tpo0.05/karsilastirma.md`

### Kendi ürettiğimiz depolar (2 160 örnek)

4 depo boyutu (5 000–20 000 lokasyon) × 3 koridor yapısı × 6 doluluk oranı ×
10 sipariş seti × 3 sipariş sayısı (50/100/200).

| | DEPSO | RBRS-AE | RBRS-AE2 | ALNS |
|---|---|---|---|---|
| En kısa yolu bulduğu örnek | 15 | 48 | 378 | **1 710** |
| ALNS'nin yolu bundan ne kadar kısa | %6,4 | %3,8 | %1,4 | — |

- RBRS-AE2, RBRS-AE'den %2,5 kısa (2 160 örneğin 1 997'sinde).
- Fark sipariş sayısıyla açılıyor; doluluk ve koridor yapısının etkisi küçük.
- Rapor: `results/generated/karsilastirma_results__s5__tpo0.05.md`

### Dinamik yer ataması (talep değişince ürünleri taşımak)

Kendi depolarımızda (iki blok, %70 doluluk, yüksek dinamik), 9 dönem.
Taşımadan sonraki toplam yürüme mesafesi (LU):

| Depo | DEPSO | RBRS-AE | RBRS-AE2 | ALNS |
|---|---|---|---|---|
| 5 000 | 335 837 | 329 712 | 310 734 | **301 060** |
| 10 000 | 1 104 736 | 1 026 915 | 946 389 | **922 546** |
| 15 000 | 1 884 767 | 1 783 249 | 1 621 159 | **1 573 431** |
| 20 000 | 2 991 434 | 2 914 369 | 2 617 216 | **2 526 707** |

Taşıma her algoritmada mesafeyi azaltıyor; yüzde kazancı en yüksek olan DEPSO,
çünkü başlangıç planı en uzun olan o. Not: RBRS-AE2 koşuları `1d5dd37`,
diğerleri bir önceki kod sürümüyle alındı. Ayrıntılar: `docs/RELOCATION.md`.

### Referans doğrulama

DEPSO, Kübler ve arkadaşlarının 35 senaryosunda makalede raporlanan SOP'a
göre kazanca 35/35 senaryoda ±3,6 puan içinde yaklaşıyor. Dinamik yer
atamasında yön ve büyüklük makaleyle uyumlu, birebir değil. Mutlak mesafeler
makaledekinin yaklaşık yarısı; yüzde karşılaştırmalar bundan etkilenmiyor,
nedeni açık bir nokta olarak duruyor. Ayrıntılar: `docs/KUBLER_VERI.md`.

## Kurulum

Python 3.10 veya üstü.

```bash
pip install -r requirements.txt
python -m pytest tests/ -q
```

`numba` kuruluysa rota hesabı derlenmiş hâliyle ~10–20 kat hızlı çalışır;
sonuçlar aynıdır. Kurulu değilse kod yine çalışır, yalnızca yavaştır.

## Deneyleri koşmak

Koşucular commit'lenmemiş değişiklik varsa başlamaz; böylece her sonucun hangi
kodla alındığı bellidir (yalnızca deneme için `--allow-dirty`). Kesilen koşum
aynı komutla kaldığı yerden devam eder. Protokolün tamamı:
`docs/DENEY_PROTOKOLU.md`.

```bash
# Kübler'in 35 senaryosu, eşit süre, 5 tohum (~3 saat, 16 işlem)
python run_batch.py --batch all --jobs 16 --seeds 5 --time-per-order 0.05
python compare_algorithms.py results/compare__s5__tpo0.05

# Kendi ürettiğimiz depolar (~3-4 saat)
python run_generated.py --jobs 16 --seeds 5 --time-per-order 0.05
python compare_algorithms.py results/generated/results__s5__tpo0.05.json

# Dinamik yer ataması: bir depo, bir algoritma
python run_dynamic.py --source generated --size 10000 --blocks 2 --fill 0.7 \
    --dynamics yuksek --algo RBRS-AE2 --jobs 16

# Kübler'in dinamik senaryosu (makale Şekil 10 verisi)
python run_dynamic.py --source kubler-fig10 --scenario 1 --algo DEPSO --jobs 16

# RBRS-AE iyileştirme denemeleri (hangi değişiklik ne kazandırıyor)
python rbrs_ablation.py --jobs 16 --full --seeds 5

# Hızlı deneme
python run_batch.py --only 50_2_6 --n 2
```

Windows'ta Türkçe karakterli çıktılar için komutların başına `PYTHONUTF8=1`
eklemek gerekebilir.

## Web sitesi

Site `site/` klasöründedir ve sayılar elle girilmez, `results/` altındaki
deney dosyalarından üretilir:

```bash
python site_data.py            # sonuçları site/data/catalog.js'e toplar
python site_data.py --races    # yarış bölümünün rotalarını yeniden hesaplar (yavaş)
```

Yerelde görmek için `site/index.html` dosyasını tarayıcıda açmak yeterli.
`site/` master'a gönderildiğinde GitHub Pages ile yayınlanır
(`.github/workflows/pages.yml`). "Kendin dene" bölümü algoritmaların
hafifletilmiş JavaScript sürümüyle (`site/solver.js`) ziyaretçinin
tarayıcısında çalışır; sitedeki deney sonuçları ise Python kodundan gelir.

Eski Streamlit arayüzü de duruyor: `streamlit run ui/app.py`.

## Klasörler

```
algorithms/           DEPSO, RBRS-AE, RBRS-AE2, ALNS, yer değişimi (relocation)
  routing/            rota hesabı (en yakın komşu + 2-opt, numba ile derlenmiş yol, önbellek)
  batching/           first-fit ve savings gruplama
benchmarks/           SOP ve FCFS
core/                 depo modeli, problem üreticileri, deney protokolü, talep tahmini
data/                 Kübler senaryolarının sipariş verisi
results/              deney sonuçları (her dosya kod sürümünü içerir)
site/                 Raf Arası web sitesi
docs/                 yöntem ve deney notları
tests/                testler (Python ve sitenin çözücüsü için)
run_batch.py          Kübler'in 35 senaryosu
run_generated.py      kendi ürettiğimiz depolar
run_dynamic.py        dinamik yer ataması
compare_algorithms.py eşit süreli karşılaştırma raporu
rbrs_ablation.py      RBRS-AE iyileştirme denemeleri
site_data.py          site verisini üretir
```

## Belgeler

| Belge | İçerik |
|---|---|
| `docs/DENEY_PROTOKOLU.md` | Eşit süre, çoklu tohum, kod sürümü kontrolü, istatistik test |
| `docs/RBRS_AE2.md` | RBRS-AE'nin zayıf yanları, denenen yedi değişiklik ve sonuçları |
| `docs/URETICI.md` | Kendi depo ve sipariş üreticimiz |
| `docs/KUBLER_VERI.md` | Kübler'in veri üretiminin yeniden kurulumu |
| `docs/RELOCATION.md` | Dinamik yer ataması, makaleye göre farklar |
| `docs/ALNS_formulasyon.md` | ALNS'nin matematiksel tanımı |
| `docs/DENETIM_2026-09-28.md` | Eylül sonu kod denetimi ve düzeltmeler |

## Kaynak

Kübler, P., Glock, C. H. ve Bauernhansl, T. (2020). A new iterative method for
solving the joint dynamic storage location assignment, order batching and
picker routing problem in manual picker-to-parts warehouses. *Computers and
Industrial Engineering*, 147, 106645.
