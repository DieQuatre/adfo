# Warehouse Optimization — Paper-2 + RBRS-AE

Kübler, Glock, Bauernhansl (2020) reproduksiyonu + RBRS-AE algoritması.

## Durum

| Modül | Durum |
|---|---|
| `config.py` | ✅ |
| `core/warehouse.py` | ✅ |
| `core/data_loader.py` | ✅ |
| `algorithms/base.py` | ✅ |
| `algorithms/routing/*` | ✅ NN, 2-opt, S-Shape |
| `algorithms/batching/*` | ✅ First-fit, Savings |
| `algorithms/depso.py` | ✅ **Paper algoritması — test edildi** |
| `algorithms/rbrs_ae.py` | 🟡 İskelet, parametre kararı bekliyor |
| `benchmarks/{sop,fcfs}.py` | ✅ |
| `ui/app.py` + sayfalar | ✅ Streamlit hazır |
| `core/forecasting.py` | ⏳ Holt-Winters (sonra) |
| `algorithms/relocation.py` | ⏳ Sonra |

## Doğrulanmış DEPSO Sonuçları

50 sipariş, S1 P1, 500 iter:

| Algoritma | TD | vs SOP | vs FCFS |
|---|---|---|---|
| SOP | 1384 LU | — | — |
| FCFS | 187 LU | — | — |
| **DEPSO** | **139 LU** | **-89.96%** | **-25.67%** |

**Paper hedefleri:** -88% (SOP), -39% (FCFS) → DEPSO vs SOP **birebir tutuyor**.

## Kurulum & Kullanım

```bash
pip install -r requirements.txt
streamlit run ui/app.py
```

Her modül kendi başına da çalıştırılabilir:
```bash
python core/warehouse.py
python algorithms/depso.py
python algorithms/rbrs_ae.py
```

## RBRS-AE Parametreleri (varsayılan)

`config.py` içinde `RBRS_AE` dict'inde. Grup karar verince güncellenir.

## Sıradaki

1. RBRS-AE optimize edilmesi (grup kararı)
2. Holt-Winters forecasting
3. Dinamik relokasyon
4. Çoklu instance / ortalama rapor
