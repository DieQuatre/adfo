# Dinamik yer ataması (relocation)

Kod: `algorithms/relocation.py`. Deney: `run_dynamic.py`. Doğrulama:
`validate_relocation.py`. Veri görünümü: `core/dynamic_data.py`.

## Ne yapıyor

Her test döneminin sonunda, talebi değişen ürünlerin yerinin değiştirilip
değiştirilmeyeceğine karar verir. Kübler, Glock ve Bauernhansl (2020) Bölüm 5.3
adım adım uygulanmıştır:

| Bölüm | Kodda |
|---|---|
| 5.3.1 Sınıflandırma, `o` ve `u` eşikleri | `run_period`: gerçekleşen ve Holt-Winters tahminli ABC sınıfları, sınıf sınırları, yanlış sınıf sayacı, `U_tar` |
| 5.3.2 Öncelik değeri PV | `run_period`: ilgili sınırdan uzaklıkların toplamı, azalan sıra |
| 5.3.3 Yer kontrolü FV | `_feasible` |
| 5.3.4 Dört takas senaryosu | `_build_suggestion`: 1 boş yer, 2 doğrudan takas, 3 dolaylı takas, 4 üç ürünlü döngü; 2 ile 3 arasında rastgele seçim |
| 5.3.5 Efor ve kabul | `run_period`: efor = mevcut → hedef mesafe + 180 + 60 LU; Tdr ≤ 0 ret; λ ile gelecek kazanç; kazanç > efor kabul |

Parametreler `config.DYNAMIC_STORAGE`: `o = 2`, `u = 1`, en fazla 50 öneri
(makale §6.4), tahmin ufku 4 dönem (makalede sayı yok, Şekil 4'teki örnek).

## Taşıma kazancının (Tdr) ölçümü

Makale Td_rel'i, her öneri için dönemin siparişlerini DEPSO ile yeniden
çözerek hesaplar. Bu, dönem başına 50 öneri × 20 alt dönem DEPSO demek; bizim
ölçümümüzle (DEPSO 500 iterasyon, ~380 sipariş, 16 paralel işlemde çözüm
başına ~3 dk) senaryo başına 40 saatin üstünde. Bu yüzden üç ölçüm yolu var
(`run_dynamic.py --tdr-eval`):

| Seçenek | Nasıl | Ne zaman |
|---|---|---|
| `firstfit` (varsayılan) | Dönemin siparişleri konuma bakmayan first-fit ile bir kez gruplanır; öneri denenirken gruplar sabit, yalnızca etkilenen rotalar yeniden hesaplanır | Kendi deneylerimiz: hızlı, gürültüsüz, her algoritma aynı taşıma kararlarını alır |
| `full` | Makaledeki gibi her öneride algoritma yeniden çalışır; süre için dönemin ilk N alt dönemi (`--eval-subperiods`) ve kısaltılmış DEPSO (`--eval-iter`), alt dönem başına sabit tohum | Kübler doğrulaması |
| `algo` | Seçilen algoritmanın kendi grupları sabit tutulur (Paket 8'e kadarki davranış) | Yalnızca karşılaştırma için |

`algo` neden bırakıldı: DEPSO, RBRS-AE ve ALNS yakın siparişleri aynı gruba
koyar. Grupları sabit tutunca uzaktaki bir ürünü kapıya taşımak neredeyse
kazançsız görünür, çünkü o ürünün grubu zaten o bölgeye gidiyordur; oysa
yeniden gruplamayla kazanç ortaya çıkar. Ölçüm (senaryo 1, 1. test dönemi,
4 alt dönem, aynı 50 öneri): ortalama Tdr first-fit gruplarıyla 62 LU,
DEPSO gruplarıyla 10 LU. Tam DEPSO koşumunda (500 iterasyon, 20 alt dönem)
bu yüzden dönem başına 0-2 öneri kabul edildi ve sonuç makalenin çok altında
kaldı:

| Senaryo | `algo` ile DEPSO | `firstfit` ile DEPSO (100 it., 4/20 alt dönem) | Makale |
|---|---|---|---|
| 1 | %9,02 / %0,62 / %8,40 | %25,18 / %8,05 / %17,13 | %15,02 / %2,79 / %12,23 |
| 2 | %0,94 / %0,13 / %0,81 | koşulmadı | %7,45 / %2,08 / %5,37 |

(azalma / efor / net)

`full` ile küçük ölçekli kontrol (senaryo 1, DEPSO 100 it., dönem başına 2
alt dönem, öneri başına 2 alt dönem × 50 it. yeniden çözüm, ilk 4 dönem),
dönem dönem makalenin ek tablolarıyla (Ek Tab. 1-3):

| Dönem | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| Azalma, bizde | %0,0 | %5,4 | %7,5 | %12,5 |
| Azalma, makale | %−0,4 | %6,8 | %13,1 | %15,1 |
| Efor, bizde | %3,9 | %2,9 | %4,1 | %1,4 |
| Efor, makale | %4,5 | %4,1 | %2,9 | %0,5 |
| Kabul edilen öneri, bizde | 10 | 8 | 11 | 4 |
| Taşınan ürün, makale | 24 | 22 | 16 | 3 |

Makaledeki yöntem küçük ölçekte bile makalenin dönem dönem gidişini izliyor.
Asıl doğrulama tam ölçekte (20 alt dönem, 500 iterasyon, öneri başına 16 alt
dönem) Kübra'nın bilgisayarında koşulacak.

`firstfit` ile DEPSO makaleden fazla taşıma yapıyor; efor yüzdesinin yüksek
çıkmasında mutlak mesafe ölçeği de rol oynuyor (bizde bir alt dönemin DEPSO
mesafesi makalenin yaklaşık yarısı; taşıma başına 240 LU sabit efor bizde
oransal olarak iki kat büyük; docs/KUBLER_VERI.md).

Önceki doğrulama (`results/dynamic/validation_RBRS-AE.md`, 20 öneri):
yeniden çözümde, taşınan ürün siparişlerde hiç geçmediği hâlde ±90 LU'ya
varan Tdr değerleri çıkıyor; bu algoritmanın dalgalanması. `full` seçeneği
bu gürültüyü azaltmak için her alt dönemde aynı tohumu kullanır.

## `o` sayacının başlangıcı

Makale Tab. 3'te 1. test döneminin sonunda taşıma yapılıyor (senaryo 1: 24
ürün). `o = 2` "son dönemde ve bu dönemde yanlış sınıfta" demek; bunun ilk test
döneminde de değerlendirilebilmesi için yanlış sınıf sayacı ısınma
dönemlerinin gerçekleşen talebiyle başlatılır (ürünler ısınmada başlangıç
yerinde durur). Önceki sürümde sayaç sıfırdan başlıyordu ve 1. dönemde hiç
taşıma yapılmıyordu.

## Sonuçlar: veri setinin etkisi

Aynı relocation kodu, FIRSTFIT gruplama, 9 dönem, tüm alt dönemler:

| Veri | Mesafe azalması | Efor | Net |
|---|---|---|---|
| Eski veri seti (`data/`), senaryo 1 | %0,97 | %1,32 | %−0,35 |
| **Şekil 10 ile yeniden üretilen, senaryo 1** | **%17,09** | **%4,07** | **%13,02** |
| Makale, senaryo 1 (DEPSO) | %15,02 | %2,79 | %12,23 |
| **Şekil 10 ile yeniden üretilen, senaryo 2** | **%6,83** | **%2,24** | **%4,59** |
| Makale, senaryo 2 (DEPSO) | %7,45 | %2,08 | %5,37 |
| Kendi üreticimiz, 5000 lok., tek geçişli, %70, yüksek dinamik | %0,56 | %1,11 | %−0,55 |

Eski veri setinde çok satan ürünler hep çok satan kalıyordu; makalenin
Şekil 10 yöntemi ise bilerek çok satanları yavaşlatıp rastgele ürünleri
hızlandırıyor. Yöntem yeniden kurulunca (`core/kubler_generator.py`,
`docs/KUBLER_VERI.md`) sonuç makaleye yaklaştı. Relocation kodu değişmedi
(yalnızca yukarıdaki sayaç başlangıcı).

Kendi üreticimizin "yüksek" dinamiği de aynı eksikliği taşıyor: talep seviyesi
değişiyor ama çok satan ↔ az satan dönüşümü yok. Oraya da bir takas profili
eklenmeli.

## Komutlar

```bash
python run_dynamic.py --source kubler-fig10 --scenario 1 --algo DEPSO --jobs 16
python run_dynamic.py --source kubler-fig10 --scenario 1 --algo DEPSO --jobs 16 \
    --tdr-eval full --eval-subperiods 16 --eval-iter 100          # makaledeki yöntem
python run_dynamic.py --source kubler --scenario 1 --algo DEPSO --jobs 16   # eski veri
python run_dynamic.py --source generated --size 10000 --blocks 2 --fill 0.7 \
    --dynamics yuksek --algo ALNS --jobs 16
python run_dynamic.py --source kubler --scenario 1 --algo FIRSTFIT      # hızlı
python validate_relocation.py --algo RBRS-AE
```
