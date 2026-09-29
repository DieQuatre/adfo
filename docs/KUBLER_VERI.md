# Kübler (2020) veri üretiminin yeniden kurulumu

Kod: `core/kubler_generator.py`. Testler: `tests/test_kubler_generator.py`.
Dinamik deneyde kaynak adı: `--source kubler-fig10`.

Makale (Kübler, Glock & Bauernhansl 2020, CIE 147, 106645) veri seti
vermiyor, üretim yöntemini anlatıyor. Bu modül o yöntemi adım adım uygular.
Veri dosyaya yazılmaz; tohumdan (`seed`) her seferinde aynı veri üretilir
(~0,2 s).

## Neden

Eski veri setinde (`data/`) relocation makalenin %15'lik kazancının yanına
yaklaşamıyordu (%0,9). Sebep: çok satan ürünler hep çok satan kalıyordu.
Makalenin yöntemi bilerek çok satanları yavaşlatıp rastgele ürünleri
hızlandırıyor. Ayrıca eski veriyi üreten kod repoda yoktu.

## Makaledeki adımlar ve koddaki karşılığı

| Makale | Ne | Kodda |
|---|---|---|
| Fig. 8, §6.1 | 1. dönem: 5 000 sipariş, sipariş başına U{1..2} satır, satır başına U{1..6} adet | `_order_sizes`, `KublerData._build` |
| §6.1 | Erişim fonksiyonu Z(y) = y^c, c = log AF / log 0,2, AF = 0,6 | `access_lines` |
| Fig. 8 | Ürün satırları siparişlere rastgele, bir ürün bir siparişte en fazla bir kez | `_distribute` |
| §6.3 | Talep serisi: N₁ + T·(t−1) + S·cos(2π(t−1)/L) + Ir | `demand_series` |
| §6.3 Adım 1–10 | Hızlı ↔ yavaş dönüşümü: temel ürün (BI) S_prob olasılıkla azalan trend alır, rastgele karşı ürün (CI) BI'nin büyüklüğünde ters trend alır; S_prob her çiftte × 0,995 | `demand_series` |
| §6.3 Adım 8 | Toplam talepte max ≤ M·min (M = 2), tutmazsa çift sabit kalır | `demand_series` |
| Fig. 10 | t > 1: toplam satıra ulaşana kadar sipariş aç, ürünleri rastgele dağıt, alt dönemlere düzgün böl | `KublerData._build` |
| §6.3 son paragraf | Başlangıç yerleşimi 1. dönem ABC'sine göre, sınıf içinde rastgele | `generate_kubler` |
| Table 2 | Senaryo 1: Tf 0,30, Sf 0,15; senaryo 2: Tf 0,15, Sf 0,075; L 12, Irf 0,025, 20 alt dönem, 12 + 9 dönem | `KublerSpec`, `SCENARIOS` |

## Makalede açık bırakılan noktalar (bizim yorumumuz)

- 1. dönem talebi Fig. 8'de üretilen gerçek değer olarak kalır; zaman serisi
  formülü t ≥ 2 için uygulanır.
- Talep sıfırın altına inemez.
- Adım 8'deki M koşulu artımlı kontrol edilir: henüz işlenmemiş ürünler
  1. dönem değerinde sabit sayılır.
- t > 1'de son sipariş, kalan satır sayısına kırpılır.
- İki senaryo aynı 1. dönemi, ağırlıkları ve başlangıç yerleşimini paylaşır;
  yalnızca dinamikler farklıdır.
- Ürün kimlikleri popülerlik sırasına rastgele eşlenir (ürün 0 en çok satan
  değildir).

## Makaleyle karşılaştırma

| | Yeniden üretilen | Makale |
|---|---|---|
| 1. dönem sipariş / satır | 5 000 / 7 474 | 5 000 / ~7 500 |
| En çok satan %20'nin payı | %60 | AF = 0,6 |
| Test dönemleri boyunca statik mesafe artışı, senaryo 1 | %+27 (FIRSTFIT) | %+32 (DEPSO, Ek Tab. 1) |
| Test dönemleri boyunca statik mesafe artışı, senaryo 2 | %+28 (FIRSTFIT) | %+31 (DEPSO, Ek Tab. 6) |
| 1. test döneminde A sınıfındaki 300 üründen başlangıçta A olmayan | 170 (s1), 148 (s2) | (verilmiyor) |
| Relocation: azalma / efor / net, senaryo 1 | %17,09 / %4,07 / %13,02 (FIRSTFIT) | %15,02 / %2,79 / %12,23 |
| Aynısı, DEPSO (100 iterasyon, 20 alt dönemin 4'ü, hızlı kontrol) | %14,42 / %1,72 / %12,70 | %15,02 / %2,79 / %12,23 |
| Relocation: azalma / efor / net, senaryo 2 | %6,83 / %2,24 / %4,59 (FIRSTFIT) | %7,45 / %2,08 / %5,37 |

Açık nokta: mutlak mesafe ölçeği. 1. test döneminin bir alt döneminde
(~380 sipariş) DEPSO bizde ~4 000 LU, makalenin ek tablosunda ~7 800 LU.
Oranlar (DEPSO/SOP, mesafe artışı, relocation yüzdeleri) tutuyor; mutlak
değerdeki fark büyük olasılıkla mesafe matrisinin ya da depo geometrisinin
yorumundan geliyor. Yüzde karşılaştırmalarını etkilemiyor.

## Statik 35 senaryo

Statik doğrulama (`run_batch.py`) hâlâ `data*/` klasörlerindeki 1. dönem
havuzlarını kullanıyor ve bu değişiklikten etkilenmiyor. Aynı Fig. 8 yöntemi
bu modülde olduğundan, istenirse statik örnekler de buradan üretilebilir.

## Kullanım

```bash
python run_dynamic.py --source kubler-fig10 --scenario 1 --algo FIRSTFIT --jobs 16   # ~1,5 dk
python run_dynamic.py --source kubler-fig10 --scenario 1 --algo DEPSO --jobs 16      # makaledeki gibi
python run_dynamic.py --source kubler-fig10 --scenario 1 --seed 3 --algo RBRS-AE --jobs 16
```
