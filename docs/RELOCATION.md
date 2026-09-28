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

## İlk sonuçlar ve açık soru

Kübler senaryo 1, 9 dönem, tüm alt dönemler, hızlı gruplama (FIRSTFIT):

| | Bu uygulama | Makale (DEPSO) |
|---|---|---|
| Mesafe azalması | %0,89 | %15,02 |
| Relocation eforu | %1,20 | %2,79 |
| Dönem başına taşınan ürün | 4–11 | 3–25 |
| Statik mesafe / dönem | ~130–151 bin LU | ~146–158 bin LU |

Taşınan ürün sayısı ve statik mesafe makaleyle aynı düzeyde, ama mesafe
azalması çok küçük. İnceleme:

- Elimizdeki Kübler veri setinde en çok satan ürünler dönemler boyunca en
  çok satan olarak kalıyor (ör. ürün 0: 826 → 676 satır; hep A sınıfında).
  Sınıf değiştiren ürünler sınıf sınırındaki az satan ürünler (A sınırı ≈ 6
  satır/dönem); bunları taşımak dönem başına birkaç on LU kazandırıyor.
- Makalenin veri üretim yöntemi (Şekil 10, adım 1–10) ise bilerek **çok
  satan ürünleri az satana, rastgele ürünleri çok satana çeviriyor**
  ("fast-moving items can (frequently) become slow movers"). Makaledeki
  %15'lik kazanç bu büyük yer değiştirmelerden geliyor.
- Veri setimizdeki 1. dönem sipariş sayısı ~10 300; makalede 5 000.

Sonuç: relocation kodu makaleyi izliyor; fark büyük olasılıkla verinin
dinamiğinden kaynaklanıyor. Kübler veri üreticisinin repoda olmaması (denetim
K5) burada doğrudan önem kazanıyor. Sonraki adım: Şekil 10'daki yöntemi
yeniden kurup senaryo 1 ve 2'yi DEPSO ile tekrar koşmak. Kendi üreticimize de
"çok satan ↔ az satan" takası yapan bir profil eklenebilir.

## Komutlar

```bash
python run_dynamic.py --source kubler --scenario 1 --algo DEPSO --jobs 16
python run_dynamic.py --source generated --size 10000 --blocks 2 --fill 0.7 \
    --dynamics yuksek --algo ALNS --jobs 16
python run_dynamic.py --source kubler --scenario 1 --algo FIRSTFIT      # hızlı
python validate_relocation.py --algo RBRS-AE
```
