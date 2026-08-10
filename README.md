# Warehouse Optimization — Paper-2 + RBRS-AE

Kübler, Glock, Bauernhansl (2020) reproduksiyonu + RBRS-AE algoritması.

**Bağımsız denetim ile doğrulanmış.** Rapor: 6 kritik kusur bulundu ve düzeltildi,
35 senaryonun tamamı paper veri setiyle sıfırdan koşuldu.

## Durum

| Modül | Durum |
|---|---|
| `config.py` | ✅ |
| `core/warehouse.py` | ✅ Depo + numpy mesafe matrisi |
| `core/data_loader.py` | ✅ |
| `core/forecasting.py` | ✅ Holt-Winters (α=0.19, β=0.053, γ=0.10) |
| `algorithms/base.py` | ✅ Interface |
| `algorithms/routing/*` | ✅ NN, 2-opt, **gerçek S-Shape traversal** |
| `algorithms/batching/*` | ✅ First-fit, Savings |
| `algorithms/depso.py` | ✅ Paper algoritması — 35 senaryoda doğrulandı |
| `algorithms/rbrs_ae.py` | ✅ Regret tabanı düzeltildi — DEPSO'dan üstün |
| `algorithms/relocation.py` | ✅ Çalışıyor (önceden ölüydü, düzeltildi) |
| `benchmarks/{sop,fcfs}.py` | ✅ Gerçek S-Shape ile |
| `ui/app.py` + 4 sayfa | ✅ Streamlit hazır |
| `run_batch.py` | ✅ 35 senaryo koşucu |
| `tests/` | ✅ **78 test**, tamamı geçiyor |

---

## Doğrulanmış DEPSO Sonuçları — 35 Senaryo (Paper Appendix H)

**Bağımsız denetim, paper veri setiyle, 5 instance × DEPSO 500 iterasyon:**

| Metrik | Değer |
|---|---|
| Toplam senaryo | 35 |
| Bağımsız ölçüm | **35/35** (kopya deney yok) |
| Tolerans içinde (±5 puan) | **35/35 ✅** |
| Ortalama mutlak sapma | **±1.40 puan** |
| Ortalama işaretli sapma | **+0.48** (sistematik yanlılık yok) |
| Maksimum sapma | ±3.47 puan |
| DEPSO vs FCFS ortalama | %48.93 (paper: %40.80) |

Sapma sipariş sayısıyla değil, **sipariş başına maksimum satır sayısıyla (N_maxol)**
ilişkilidir — N_maxol=2'de ortalama +2.60 (paper altı), N_maxol=10'da ortalama
−1.28 (paper üstü). Bu örüntünün nedeni henüz açıklanmadı, iki hipotez var
(DEPSO implementasyon farkı veya S-shape baseline tepkisi); ayırt etmek için
ek deney gerekiyor.

---

## RBRS-AE — DEPSO Karşılaştırması

**35 senaryonun 33'ünde RBRS-AE, DEPSO'dan daha kısa toplam mesafe üretti**
— ortalama **%5.82** daha kısa, ve bunu DEPSO'nun 500 iterasyonuna karşı
sadece **100 iterasyonla** başarıyor.

### Hız (dikkat: her boyutta değil)

| Boyut | DEPSO ort. süre | RBRS-AE ort. süre | Sonuç |
|---|---|---|---|
| k = 50  | 55 s  | 12 s  | 5× hızlı |
| k = 100 | 104 s | 52 s  | 2× hızlı |
| k = 150 | 157 s | 156 s | eşit |
| k = 200 | 217 s | 339 s | **1.56× yavaş** |

**"RBRS-AE her zaman daha hızlı" iddiası yanlıştır.** Doğru ifade: RBRS-AE,
DEPSO'dan tutarlı biçimde daha iyi çözüm üretir; hız avantajı küçük
instance'larda (k≤100) belirgindir, büyük instance'larda kaybolur. Sebep,
final local search'ün O(B²·n²) taraması — bilinen, düzeltilebilir bir darboğaz.

---

## Bulunan ve Düzeltilen Kritik Kusurlar

| # | Kusur | Etki |
|---|---|---|
| 1 | Dynamic relocation'da iki sayaç birbirini sıfırlıyordu | Modül 3 periyot boyunca 0 öneri üretiyordu — **paper'ın ana katkısı hiç çalışmıyordu** |
| 2 | 35 senaryonun 21'i aynı deneyin kopyasıydı | Sipariş sayısı üreticiye geçmiyordu, k=50/100/150/200 aynı listeyi alıyordu |
| 3 | Karşılaştırma paper veri setini kullanmıyordu | Kendi sentetik siparişleri SOP tabanını yapay düşürüyor, kazancı şişiriyordu |
| 4 | DEPSO durağanlık sayacı hiç sıfırlanmıyordu | Appendix G'deki yerel arama tasarlandığından çok daha sık tetikleniyordu |
| 5 | RBRS-AE regret adımı yanlış taban kullanıyordu | 50 siparişte 22 batch açıyordu (alt sınır 2) — regret adımı fiilen devre dışıydı |
| 6 | "S-Shape" gerçek S-shape değildi | Koridoru baştan sona geçmiyor, en kısa yol hesaplıyordu — SOP/FCFS baseline'ını olduğundan iyi gösteriyordu |

Her kusur için regresyon testi yazıldı (`tests/test_audit_regressions.py`,
`tests/test_s_shape_traversal.py`).

---

## Kurulum & Kullanım

```bash
pip install -r requirements.txt
streamlit run ui/app.py
```

**UI Sayfaları:**

| Sayfa | İçerik |
|---|---|
| 📦 Ana Sayfa | Depo görselleştirme |
| 🎯 Tek Koşu | Algoritma çalıştır, rota görselleştir |
| ⚖️ Karşılaştırma | 4 algoritmayı yan yana koştur |
| 🔄 Dynamic Relocation | 9 periyot Holt-Winters + relocation (artık çalışıyor) |
| 📊 35 Senaryo | Paper Appendix H tam karşılaştırma |

---

## 35 Senaryo Koşumu

```bash
python run_batch.py --batch 1   # senaryo 1-5
...
python run_batch.py --batch 7   # senaryo 31-35
python run_batch.py --summary   # özet tablo
```

Sonuçlar `results/` klasörüne kaydedilir, UI otomatik yükler.

**Not:** Sürekli entegrasyon artık her push'ta otomatik tetiklenmiyor — eskiden
algoritma dosyalarına yapılan her push, senaryoları zayıf varsayılanlarla
yeniden koşup sonuçların üzerine yazıyordu.

---

## Testler

```bash
python -m pytest tests/ -v
```

**78 test, tamamı geçiyor** (önceki: 53, +25 denetim sonrası eklendi).

| Dosya | Kapsam |
|---|---|
| `test_audit_regressions.py` | Denetimde bulunan 6 kusur için regresyon |
| `test_s_shape_traversal.py` | Gerçek S-shape traversal doğrulaması |
| `test_relocation.py` | Sayaç bağımsızlığı, öneri üretimi |
| `test_depso.py`, `test_batching.py`, `test_warehouse.py`, `test_smoke.py` | Temel modül testleri |

---

## Proje Yapısı

```
warehouse_optimization/
├── config.py
├── core/
│   ├── warehouse.py
│   ├── data_loader.py
│   └── forecasting.py
├── algorithms/
│   ├── depso.py          # Paper algoritması
│   ├── rbrs_ae.py         # Yeni algoritma — regret düzeltildi
│   ├── relocation.py      # Düzeltildi — artık çalışıyor
│   ├── routing/
│   │   └── s_shape.py     # Gerçek traversal
│   └── batching/
├── benchmarks/
├── ui/
│   └── pages/
├── tests/                 # 78 test
├── run_batch.py
├── data/                  # 370 JSON dataset (paper parametreleriyle)
└── results/                # batch_1..7.json — bağımsız doğrulanmış
```

## Kaynaklar

Rapor kaynakları: `results/batch_1..7.json`, `results/paper_35_scenarios.json`,
`tests/` (78 test). Denetim `fix/audit-blockers` branch'inde yapıldı,
`master`'a birleştirildi.
