# Parametrik problem üreticisi

Kod: `core/generator.py`. Parametreler: `config.py` içinde `GENERATOR`.
Komutlar: `generate_instances.py` (depoları üret ve özetle),
`run_generated.py` (algoritma karşılaştırması).

Bu üretici Kübler veri setinden bağımsızdır. Kübler verisi (`data*/`)
yalnızca problemin tanımı ve DEPSO'nun doğrulanması için kullanılır;
algoritmaların asıl karşılaştırması bu üreticinin depolarında yapılır.

## Bir problem örneği nasıl tanımlanır

Bir örnek beş değerle tam olarak belirlenir:

| Değer | Anlamı | Izgaradaki değerler |
|---|---|---|
| `size` | hedef lokasyon sayısı | 5000, 10000, 15000, 20000 |
| `blocks` | koridor yapısı: 1 geçişsiz, 2 tek geçişli, 3 iki geçişli | 1, 2, 3 |
| `fill` | doluluk oranı | 0,9 / 0,7 / 0,5 (grup kararı bekliyor) |
| `dynamics` | talebin zamanla ne kadar değiştiği | düşük / orta / yüksek |
| `seed` | tohum | 0, 1, 2, ... |

Aynı beş değer her zaman aynı depoyu, ürünleri, talebi ve siparişleri
üretir. Bu yüzden siparişlerin diske yazılması gerekmez; istenince yeniden
üretilir. Hakem ya da başka bir araştırmacı yalnızca bu beş değerle ve kodla
aynı veriyi elde edebilir.

Izgara: 4 boyut × 3 koridor yapısı × 3 doluluk = **36 depo**. Her depo için
10 sipariş seti → **360 problem örneği** (Emre Hoca toplantısı, 2026-08-17).

## Üretim adımları

1. **Depo.** Koridor derinliği sabit (her kenarda 60 raf, 1/2/3 bloğa tam
   bölünür, raf başına 4 lokasyon). Depo büyüdükçe koridor sayısı artar.
   Hedef boyuta en yakın koridor sayısı seçilir. Gerçek lokasyon sayıları:
   4800, 10 080, 14 880, 20 160. Kapı (depo girişi) sabittir.
2. **Ürünler.** Ürün sayısı = doluluk × lokasyon sayısı. Ağırlık
   U(0,1; 1,0) WU.
3. **Popülerlik.** Güç yasası: en popüler %20 ürünün beklenen satır payı
   `top20_share` (varsayılan 0,70). Dönem başına sipariş sayısı ürün
   sayısıyla orantılı (`orders_per_item`).
4. **Talep profilleri.** Her ürüne bir profil atanır:

   | Profil | Davranış |
   |---|---|
   | durağan | sabit, yalnızca gürültü |
   | artan / azalan | ufuk boyunca %50–150 değişim |
   | mevsimsel | 12 dönemlik sinüs, genlik %20–50 |
   | ani değişim | rastgele bir dönemden sonra ×2–4 ya da ×0,2–0,5 |

   Profillerin oranı dinamiklik seviyesini belirler:

   | Seviye | durağan | artan | azalan | mevsimsel | ani |
   |---|---|---|---|---|---|
   | düşük | 80 | 5 | 5 | 10 | 0 |
   | orta | 55 | 10 | 10 | 15 | 10 |
   | yüksek | 30 | 15 | 15 | 20 | 20 |

   **Çok satan ↔ az satan dönüşümü** (Kübler 2020 §6.3'teki fikir): en
   popüler %20'den, popülerlikle orantılı olasılıkla ürünler seçilir
   (`swap_share`: düşük %5, orta %15, yüksek %30). Seçilen ürünün talebi
   2.–16. dönemler arasında başlayıp 3–8 dönemde %5'ine iner; eşine (en
   popüler %20 dışından rastgele bir ürün) aynı sürede, sönen ürünün
   talebinin 0,7–1,3 katı eklenir. Profil adları `swap_down` / `swap_up`.
   Bu olmadan az satan bir ürün kendi küçük talebinin birkaç katına çıksa
   bile A sınıfına ulaşamıyordu; yer değişimi deneyinde kazanç %1'in
   altında kalıyordu.

   Beklenen talep × lognormal gürültü → Poisson ile gerçekleşen satır sayısı.
5. **Yerleşim.** 1. dönemin talebine göre ABC (`placement_period`; Kübler'deki
   gibi depo bir kez yerleştirilmiş, sonra 20 dönem boyunca talep değişmiş).
   Önceki sürümde ısınmanın son dönemi kullanılıyordu; o zaman ısınmadaki
   değişimler yerleşime zaten yansıyordu. Yerleşim kuralı: ABC
   (%5 / %15 / %80). A ürünleri kapıya en yakın %5'lik lokasyon bölgesine,
   B sonraki %15'e, C kalanına; bölge içinde rastgele. Doluluk %100'ün
   altında olduğu için her bölgede boş yer kalır (relocation için gerekli).
6. **Siparişler.** Dönemin gerçekleşen satırları karıştırılır ve
   siparişlere bölünür: sipariş başına 1–4 farklı ürün, satır başına 1–4
   adet, toplam ağırlık kapasiteyi (100 WU) aşmaz. Siparişler 20 alt döneme
   eşit dağıtılır.

Bu iki değişiklik (Paket 11) aynı spec'in ürettiği talebi ve siparişleri
değiştirdi; önceki üretici sürümüyle alınan sonuçlar repodan kaldırıldı.

Yer değişimi deneyinde etkisi (5 000 lokasyon, tek geçişli, %70, FIRSTFIT,
9 dönem): önce yüksek dinamikte azalma %0,56 / net %−0,55. Şimdi, üç tohumun
ortalaması:

| Dinamiklik | Mesafe azalması | Taşıma emeği | Net |
|---|---|---|---|
| düşük | %4,3 | %2,0 | %2,3 |
| orta | %6,2 | %3,0 | %3,2 |
| yüksek | %6,5 | %3,8 | %2,6 |

Azalma ve emek dinamiklikle artıyor; net kazanç ortada en yüksek, çünkü
yüksek dinamikte ürünler daha sık yer değiştirmek zorunda kalıyor.

Zaman yapısı: 12 ısınma dönemi (Holt-Winters tahmininin bir tam sezonu
görmesi için) + 9 test dönemi. Algoritma karşılaştırmasında sipariş setleri
ilk test döneminden çekilir.

## Doğrulama ölçüleri

Her depo için `meta.json` / `instances/index.csv` içinde raporlanır:

- `fill_realised`: gerçekleşen doluluk
- `top20_share_expected` / `top20_share_realised`: beklenen ve gerçekleşen
  popülerlik payı. Gerçekleşen değer biraz yüksektir; az satan ürünlerde
  Poisson sıfırları payı artırır.
- `structural_class_change_test_horizon`: test ufku boyunca BEKLENEN talebe
  göre sınıfı değişen ürün oranı. Dinamiklik seviyesini ayıran ölçü budur
  (10 000 lokasyon, %70 doluluk: düşük ≈ %3, orta ≈ %9, yüksek ≈ %13).
- `observed_class_change_per_period`: gerçekleşen talebe göre dönemden
  döneme değişim. Poisson gürültüsü nedeniyle seviyeler arasında fark
  küçüktür (≈ %18–20).

## Grup kararı bekleyen değerler

Hepsi `config.GENERATOR` içinde; değiştirmek için yalnızca orayı düzenleyin.

| Parametre | Şu anki değer | Not |
|---|---|---|
| `grid_fills` | 0,9 / 0,7 / 0,5 | toplantıda 90-70-50 ve 80-60-40 konuşuldu |
| `order_set_size` | 100 | bir setteki sipariş sayısı; birden fazla da verilebilir (`--k 50 100 200`) |
| `top20_share` | 0,70 | |
| `orders_per_item` | 0,8 | |
| `max_lines_per_order`, `max_qty_per_line` | 4, 4 | |
