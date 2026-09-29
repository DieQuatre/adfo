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

## Makaleden bilinçli sapma

Makale Td_rel'i, her öneri için dönemin tüm siparişlerini DEPSO ile yeniden
çözerek hesaplar. Burada dönemin siparişleri seçilen algoritmayla **bir kez**
gruplanır; öneri denenirken gruplar sabit tutulur ve yalnızca taşınan ürünün
geçtiği grupların rotası (NN + 2-opt) yeniden hesaplanır.

Neden: 9 dönem × 20 alt dönem × 50 öneri için tam yöntem günler sürer.

Ölçülen etkisi (`results/dynamic/validation_RBRS-AE.md`, 20 öneri):

- Ortalama Tdr: yaklaşık yöntem 7,2 LU, tam yöntem 9,4 LU.
- Tam yöntemde, taşınan ürün siparişlerde hiç geçmediği hâlde ±90 LU'ya varan
  Tdr değerleri çıkıyor. Bu, algoritmanın değişen girdiyle farklı bir gruplama
  bulmasından gelen dalgalanma; taşımanın etkisinden büyük. İki yöntemin
  işaret uyumu bu yüzden %40.
- Gruplaması lokasyona bakmayan first-fit ile iki yöntem birebir aynı sonucu
  veriyor (test: `test_approximation_exact_for_location_blind_batching`).

Yorum: yaklaşık yöntem, taşımanın kendi etkisini gürültüsüz ölçüyor. Tam
yöntemin ölçümüne ise algoritmanın dalgalanması karışıyor. Ortalamalar
birbirine yakın.

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
python run_dynamic.py --source kubler --scenario 1 --algo DEPSO --jobs 16   # eski veri
python run_dynamic.py --source generated --size 10000 --blocks 2 --fill 0.7 \
    --dynamics yuksek --algo ALNS --jobs 16
python run_dynamic.py --source kubler --scenario 1 --algo FIRSTFIT      # hızlı
python validate_relocation.py --algo RBRS-AE
```
