# RBRS-AE iyileştirmesi (RBRS-AE2)

Kod: `algorithms/rbrs_ae2.py` (özgün `algorithms/rbrs_ae.py` değişmedi).
Deney: `rbrs_ablation.py`. Testler: `tests/test_rbrs_ae2.py`.

## Neden

Eşit süreli karşılaştırmalarda RBRS-AE'nin zayıf yerleri:

- Kübler 35 senaryo: ALNS'den %2,4, DEPSO'dan %0,9 geride; en çok
  6–10 satırlı siparişlerde ve büyük sipariş setlerinde geriliyor.
- Kendi ızgaramız (2 160 örnek): ALNS'den %4,0 geride; sipariş sayısı
  arttıkça fark açılıyor (en iyiye göre 50 siparişte %2,7, 200'de %5,9).
- Normal ayarlarla farklı tohumlar neredeyse aynı sonucu veriyor.

Koddaki sebepler:

1. **Eleme hep aynı grupları seçiyor.** I(b) skoru en kötü grupları yıkıyor;
   skor deterministik olduğu için ardışık iterasyonlarda büyük ölçüde aynı
   gruplar yıkılıp benzer şekilde kuruluyor. Arama aynı bölgede dönüyor.
2. **Eleme konumu görmüyor.** I(b) yalnızca grup başına mesafeye ve
   doluluğa bakıyor. Çok satırlı siparişler depoya dağıldığında, aynı
   bölgeye giden ama farklı gruplardaki siparişleri bir araya getirecek bir
   hamle yok.
3. **Yeniden yerleştirme açgözlü.** Serbest kalan siparişler sırayla en
   ucuz gruba konuyor; "regret" fikri yalnızca başlangıç çözümünde kullanılıyor.

## Denenen değişiklikler

Her seçeneğin varsayılanı özgün davranış; tek tek açılıp ölçüldü.

| Seçenek | Özgün | Denenen |
|---|---|---|
| `destroy` | en kötü I(b) grupları | her iterasyonda rastgele biri: en kötü gruplar / konumca ilişkili siparişler (Shaw) / rastgele siparişler |
| `repair` | en ucuz gruba | regret-2, öncelik ağırlıklı (başlangıçtaki kural) |
| `accept` | her sonuçtan devam | en iyiden %τ kötüyse en iyiye dön (τ %3 → 0) |
| `moves` | takas eşi rastgele | takas eşi en yakın 4 gruptan |
| `final` | tüm sipariş çiftleri | yalnızca yakın gruplar, ilk iyileşme |
| `size` | yıkılan pay %20 → %10 | %10 → %5, en çok 30 sipariş |
| `ls` | her iterasyonda shift + swap | yalnızca yeni en iyide ya da 5 iterasyonda bir |

## Küçük deneme (8 örnek, 2 tohum, sipariş başına 0,05 sn)

10 000 lokasyonlu üretilmiş depo (k = 100, 200) ve Kübler havuzlarından
4 örnek (10_10 ×2, 6_6, 2_6). Üç ayrı koşum; fark negatifse daha kısa mesafe.

| Varyant | Özgün RBRS-AE'ye göre | ALNS'ye göre | Özgünden iyi olduğu örnek |
|---|---|---|---|
| özgün RBRS-AE | — | %+7,2 … +8,0 | — |
| +destroy | **%−4,2** | %+3,3 | 7/8 |
| +repair | %−1,0 | %+6,8 | 6/8 |
| +moves | %−0,8 | %+7,0 | 4/8 |
| +final | %−0,3 | %+7,7 | 1/8 |
| +accept | %+2,6 (kötü) | %+10,8 | 3/8 |
| destroy + repair | **%−5,0 … −5,2** | **%+1,7 … +1,9** | 8/8 |
| destroy + repair + size | %−4,7 | %+2,0 | 7/8 |
| destroy + repair + ls | %−4,7 | %+2,1 | 8/8 |
| hepsi (accept dahil) | %−4,8 … −5,4 | %+2,1 … +2,4 | 8/8 |

Sonuç: farkı yaratan **konuma duyarlı, çeşitli yıkım** ve **regret ile
yeniden yerleştirme**. Diğerleri etkisiz ya da zararlı. **RBRS-AE2 =
özgün RBRS-AE + destroy=mix + repair=regret.** ALNS'ye fark %8'den %2'ye
iniyor.

Uyarı: 8 örnek az; ayarları bu sete göre seçtik. Sonuç geniş sette
doğrulanmalı (aşağıdaki komut).

## Geniş doğrulama (Kübra'nın bilgisayarında, kod 52211a4)

85 örnek (5 000 / 10 000 / 20 000 lokasyon × 3 koridor yapısı × 50/100/200
sipariş × 3 set + 4 Kübler örneği), 5 tohum, sipariş başına 0,05 sn.

| Varyant | ALNS'ye göre | Özgün RBRS-AE'ye göre | Özgünden iyi | p |
|---|---|---|---|---|
| özgün RBRS-AE | %+4,72 | — | — | — |
| +destroy | %+2,64 | %−1,96 | 55/85 | < 0,001 |
| +repair | %+4,85 | %+0,12 | 22/85 | 0,301 |
| +accept | %+5,39 | %+0,63 (kötü) | 21/85 | 0,029 |
| +moves | %+4,99 | %+0,26 (kötü) | 23/85 | 0,014 |
| +final | %+4,71 | %−0,01 | 26/85 | 0,111 |
| +size | %+4,76 | %+0,03 | 5/85 | 0,095 |
| +ls | %+4,79 | %+0,06 | 11/85 | 0,017 |
| hepsi | %+2,71 | %−1,89 | 55/85 | < 0,001 |
| **RBRS-AE2** (destroy + repair) | **%+2,08** | **%−2,49** | **59/85** | **< 0,001** |

Kırılım (RBRS-AE2'nin özgüne göre farkı):

| | 50 sipariş | 100 sipariş | 200 sipariş |
|---|---|---|---|
| RBRS-AE2 − özgün | %−0,01 (1/27) | %−3,88 (27/27) | %−3,40 (27/27) |
| RBRS-AE2 − ALNS | %+3,25 | %+0,87 | %+2,56 |

Kübler örneklerinde: 10 satırlı siparişlerde (100_10_10, 200_10_10) RBRS-AE2
ALNS'den %2,3 ve %2,9 **daha iyi**.

Sonuç: küçük setteki %5'lik fark abartılıydı; geniş sette %2,5. Yine de
anlamlı ve 100–200 siparişte istisnasız. Regret yerleştirme tek başına
etkisiz, çeşitli yıkımla birlikte ek kazanç veriyor.

## 50 siparişte neden fark yok? (Paket 15'te düzeltildi)

50 siparişlik örnekler yalnızca 2 gruba sığıyor. Özgün eleme kuralı 2 ve daha
az grupta hiç çalışmıyor (`len(batches) <= 2` → atla); RBRS-AE2 de bu kuralı
devraldığı için küçük örneklerde arama yalnızca shift/swap'a kalıyordu.
RBRS-AE2'de sınır 2 gruba indirildi (sipariş düzeyinde yıkım 2 grupta da
anlamlı). Kontrol (9 örnek, k = 50, 2 tohum): RBRS-AE2 özgünden %2,9 kısa
(9/9), ALNS'ye fark %3,5'ten %0,5'e indi.

Özgün RBRS-AE'de bu davranış korunuyor (tanımı gereği).

## Sonraki adım

RBRS-AE2 dördüncü algoritma olarak bütün deneylere eklendi
(`core/experiment.py`, `run_dynamic.py`, site). Komutlar: docs/DENEY_PROTOKOLU.md.
