"""
config.py
=========
Tüm sabitler ve paper parametreleri tek dosyada.
Hiç bir yerde sihirli sayı bulunmamalı — her şey buradan import edilir.

Kaynak: Kübler, Glock, Bauernhansl (2020), Comp. & Ind. Eng. 147, 106645
"""

from pathlib import Path

# ════════════════════════════════════════════════════════════════════════════
# DOSYA YOLLARI
# ════════════════════════════════════════════════════════════════════════════
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)


# ════════════════════════════════════════════════════════════════════════════
# DEPO PARAMETRELERİ (Paper Fig.7, Section 6)
# ════════════════════════════════════════════════════════════════════════════
WAREHOUSE = {
    'num_aisles': 10,                    # picking aisle sayısı
    'num_cross_aisles': 4,               # cross aisle sayısı
    'num_blocks': 3,                     # blok sayısı (= num_cross_aisles - 1)
    'racks_per_side_per_block': 30,      # her blokta aisle kenarı başına rack
    'locs_per_rack': 4,                  # rack başına lokasyon
    'total_locations': 7200,             # 10 × 2 × 90 × 4

    # Boyutlar (LU = Length Unit)
    'rack_width_LU': 1.0,
    'aisle_width_LU': 1.0,
    'cross_aisle_width_LU': 2.0,         # Fig.7'de "2 LU"
    'aisle_spacing_LU': 3.0,             # 2 rack + 1 koridor

    # Sınıf bölümleri (turnover bazlı)
    'class_A_pct': 0.05,                 # %5 (depot'a en yakın)
    'class_B_pct': 0.15,                 # %15
    'class_C_pct': 0.80,                 # %80
}


# ════════════════════════════════════════════════════════════════════════════
# ÜRÜN VE SİPARİŞ PARAMETRELERİ (Table 2)
# ════════════════════════════════════════════════════════════════════════════
ITEMS = {
    'num_items': 6000,                   # toplam ürün
    'weight_range_WU': (0.1, 1.0),       # ağırlık aralığı [min, max]
    'access_frequency_AF': 0.6,          # %20 en çok çekilen ürünlerin erişim payı
    'max_orderlines_per_order': 2,       # N_maxol
    'max_parts_per_orderline': 6,        # A_maxol
    'orders_period1': 5000,              # N^ord_1
    'picker_capacity_WU': 100.0,         # picker kapasitesi
    'walking_speed_LU_per_sec': 1.0,     # v_pick
    'physical_effort_min': 3.0,          # t_phy (dakika)
    'admin_effort_min': 1.0,             # t_adm (dakika)
}

# Efor değerlerinin LU eşdeğeri
ITEMS['physical_effort_LU'] = (
    ITEMS['physical_effort_min'] * 60 * ITEMS['walking_speed_LU_per_sec']
)  # 180 LU
ITEMS['admin_effort_LU'] = (
    ITEMS['admin_effort_min'] * 60 * ITEMS['walking_speed_LU_per_sec']
)  # 60 LU


# ════════════════════════════════════════════════════════════════════════════
# ZAMAN SERİSİ PARAMETRELERİ (Table 2)
# ════════════════════════════════════════════════════════════════════════════
TIME_SERIES = {
    'num_warmup_periods': 12,            # forecast parametrelendirme
    'num_test_periods': 9,               # U - asıl test periyotları
    'total_periods': 21,                 # 12 + 9
    'num_subperiods': 20,                # her periyot içinde alt-bölüm
    'seasonal_cycle_L': 12,              # periyot
    'max_fluctuation_M': 2.0,            # max/min talep oranı sınırı
    'irregular_factor_Irf': 0.025,

    # Senaryo 1: Yüksek dinamik
    'scenario1_trend_Tf': 0.300,
    'scenario1_seasonality_Sf': 0.150,

    # Senaryo 2: Düşük dinamik
    'scenario2_trend_Tf': 0.150,
    'scenario2_seasonality_Sf': 0.075,
}


# ════════════════════════════════════════════════════════════════════════════
# DEPSO PARAMETRELERİ (Paper Section 6.2)
# ════════════════════════════════════════════════════════════════════════════
DEPSO = {
    'num_particles': 5,                  # A_particle
    'num_iterations': 500,               # It_max
    'sgbest_threshold': 0.5,             # S_Gbest
    'max_local_search_iterations': 100,  # It_maxLS
    'max_stagnation_bound': 20,          # S_maxStag

    # Mutation operator eşikleri (Appendix F)
    'swap_threshold': 0.5,               # Cl < 0.5 → swap
    'shift_threshold': 0.8,              # 0.5 ≤ Cl < 0.8 → shift, ≥0.8 → inverse
}


# ════════════════════════════════════════════════════════════════════════════
# RBRS-AE PARAMETRELERİ
# ════════════════════════════════════════════════════════════════════════════
RBRS_AE = {
    # Priority(o) = 0.5*AvgDist + 0.3*Var + 0.2*Weight ve
    # I(b) = 0.7*(dist/orderCount) + 0.3*(1-utilization) ağırlıkları,
    # adaptif eleme oranı (%20 → %10) şu an algorithms/rbrs_ae.py içinde sabit.

    # TEK KAYNAK: arayüz, run_batch.py ve testler bu değerleri kullanır.
    # Spec: 100 iterasyon, 15 iterasyon iyileşme yoksa dur.
    # Deneme sayıları yayınlanan 35 senaryo koşumundaki değerler.
    'shift_attempts': 150,
    'swap_attempts': 150,

    # Stopping criteria
    'max_iterations': 100,
    'max_no_improvement': 15,
}


# ════════════════════════════════════════════════════════════════════════════
# ALNS PARAMETRELERİ (docs/ALNS_formulasyon.md)
# ════════════════════════════════════════════════════════════════════════════
ALNS = {
    # Formülasyonda verilen değerler
    'sigma1': 33,              # yeni küresel en iyi
    'sigma2': 20,              # mevcuttan iyi
    'sigma3': 8,               # kötü ama kabul edilen
    'reaction': 0.15,          # r, ağırlık güncelleme katsayısı (13)
    'segment_length': 40,      # Δ_seg
    'init_worse_pct': 0.05,    # w0, başlangıç sıcaklığı (16)
    'cooling': 0.9975,         # c, T ← T·c (15)

    # Formülasyonda sayısal değeri verilmeyenler (Ropke ve Pisinger 2006
    # varsayılanlarına yakın seçildi; gerekirse burada değiştirilir)
    'max_iterations': 500,     # DEPSO ile aynı iterasyon bütçesi
    'q_min_frac': 0.05,        # yıkılacak sipariş sayısı q ∈ [q_min, q_max]
    'q_max_frac': 0.15,        #   q_min = max(2, ⌈q_min_frac·n⌉)
    'q_max_abs': 30,           #   q_max = min(q_max_abs, max(q_min, ⌈q_max_frac·n⌉))
    'p_worst': 3.0,            # worst removal belirlilik üssü p (6)
    'p_shaw': 6.0,             # related removal belirlilik üssü p (6)
}


# ════════════════════════════════════════════════════════════════════════════
# PARAMETRİK PROBLEM ÜRETİCİSİ (core/generator.py, docs/URETICI.md)
# ════════════════════════════════════════════════════════════════════════════
# Kübler veri setinden BAĞIMSIZ, kendi üreticimiz. "grup kararı" işaretli
# değerler henüz kesinleşmedi; değiştirmek için yalnızca burayı düzenleyin.
GENERATOR = {
    # ── Deney ızgarası (Emre Hoca toplantısı, 2026-08-17) ──────────────
    'grid_sizes': [5000, 10000, 15000, 20000],   # hedef lokasyon sayısı
    'grid_blocks': [1, 2, 3],                    # 1 geçişsiz, 2 tek geçişli, 3 iki geçişli
    'grid_fills': [0.9, 0.8, 0.7, 0.6, 0.5, 0.4],  # doluluk oranı (iki öneri birlikte)
    'order_sets_per_warehouse': 10,              # her depo için sipariş seti
    'order_set_size': 100,                       # tek boyut gerektiğinde (site yarışları)
    'order_set_sizes': [50, 100, 200],           # ızgarada koşulan set boyutları

    # ── Depo geometrisi ────────────────────────────────────────────────
    # Koridor derinliği sabit, depo büyüdükçe koridor sayısı artar.
    # 60 raf, 1/2/3 blok için tam bölünür.
    'racks_per_side_total': 60,
    'locs_per_rack': 4,

    # ── Ürünler ve siparişler ──────────────────────────────────────────
    'weight_range_WU': (0.1, 1.0),
    'top20_share': 0.70,          # en popüler %20 ürünün satır payı (grup kararı)
    'orders_per_item': 0.8,       # dönem başına sipariş = oran × ürün sayısı (grup kararı)
    'max_lines_per_order': 4,     # sipariş başına satır: 1..max (grup kararı)
    'max_qty_per_line': 4,        # satır başına adet: 1..max (grup kararı)

    # ── Zaman yapısı (Holt-Winters tahmini için bir tam sezon gerekir) ─
    'warmup_periods': 12,
    'test_periods': 9,
    'season_length': 12,
    'subperiods': 20,

    # Başlangıç yerleşimi hangi dönemin talebine göre (ABC). Kübler'deki gibi
    # 1. dönem (0): depo bir kez yerleştirilmiş, sonra 20 dönem boyunca talep
    # değişmiş. Eskiden ısınmanın son dönemiydi (11); o zaman ısınmadaki
    # değişimler yerleşime zaten yansıyor, test döneminde düzeltilecek az şey kalıyordu.
    'placement_period': 0,

    # ── Talep profilleri ───────────────────────────────────────────────
    'irregular_sigma': 0.10,      # çarpımsal gürültü (lognormal σ)
    'trend_total_change': (0.5, 1.5),   # ufuk boyunca göreli değişim aralığı
    'season_amplitude': (0.2, 0.5),
    'shock_up': (2.0, 4.0),
    'shock_down': (0.2, 0.5),
    # Dinamiklik seviyesine göre profil karışımı (oranlar toplamı 1)
    'dynamics': {
        'dusuk':  {'stable': 0.80, 'up': 0.05, 'down': 0.05, 'seasonal': 0.10, 'shock': 0.00},
        'orta':   {'stable': 0.55, 'up': 0.10, 'down': 0.10, 'seasonal': 0.15, 'shock': 0.10},
        'yuksek': {'stable': 0.30, 'up': 0.15, 'down': 0.15, 'seasonal': 0.20, 'shock': 0.20},
    },
    'default_dynamics': 'orta',
    # Çok satan ↔ az satan dönüşümü (Kübler 2020 §6.3'teki fikir): en popüler
    # %20'den seçilen ürünlerin talebi söner, her birinin yerine rastgele seçilen
    # az satan bir ürün benzer büyüklüğe çıkar. Oran: en popüler %20'nin kaçı.
    'swap_share': {'dusuk': 0.05, 'orta': 0.15, 'yuksek': 0.30},
    'swap_start': (2, 16),        # dönüşümün başladığı dönem (test dönemleri 12-20)
    'swap_duration': (3, 8),      # sönme / yükselme süresi (dönem)
    'swap_floor': 0.05,           # sönen ürünün kalan talep oranı
    'swap_level': (0.7, 1.3),     # yükselen ürünün hedefi: sönenin talebi × bu
}


# ════════════════════════════════════════════════════════════════════════════
# DİNAMİK STORAGE ASSIGNMENT (Paper Section 5.3, 6.4)
# ════════════════════════════════════════════════════════════════════════════
DYNAMIC_STORAGE = {
    'min_periods_in_wrong_class_o': 2,         # threshold o (Kübler §6.4)
    'min_periods_in_target_class_u': 1,        # threshold u (Kübler §6.4)
    'max_relocation_suggestions': 50,          # durdurma: test edilen öneri sayısı
    # Tahmin ufku U^for: makalede sayı verilmemiş, Şekil 4'teki örnek 4 dönem.
    'forecast_horizon': 4,
    'seed': 0,                                 # senaryo 2/3 arasındaki rastgele seçim
}


# ════════════════════════════════════════════════════════════════════════════
# HOLT-WINTERS FORECAST (Paper Section 6.4, Silver et al. 2016)
# ════════════════════════════════════════════════════════════════════════════
HOLT_WINTERS = {
    'alpha': 0.19,                             # level smoothing
    'beta': 0.053,                             # trend smoothing
    'gamma': 0.10,                             # seasonality smoothing
}


# ════════════════════════════════════════════════════════════════════════════
# DOĞRULAMA HEDEFLERİ (Paper Tab.1-10 ve Section 6.4)
# ════════════════════════════════════════════════════════════════════════════
VALIDATION_TARGETS = {
    # Section 6.4
    'scenario1_travel_distance_reduction_pct': 15.02,
    'scenario1_relocation_effort_pct': 2.79,
    'scenario1_net_improvement_pct': 12.23,

    'scenario2_travel_distance_reduction_pct': 7.45,
    'scenario2_relocation_effort_pct': 2.08,
    'scenario2_net_improvement_pct': 5.37,

    # Section 6.2 (Tab. 1, ortalama)
    'depso_vs_SOP_avg_pct': -83.78,
    'depso_vs_FCFS_avg_pct': -40.80,
    'depso_vs_savings_avg_pct': -31.64,

    # Kabul edilebilir sapma aralığı (deterministik olmayan çıktılar için)
    'acceptable_deviation_pct': 10.0,          # ±10 puan
}


# ════════════════════════════════════════════════════════════════════════════
# TOHUM (deterministik koşumlar için)
# ════════════════════════════════════════════════════════════════════════════
RANDOM_SEED = 42


# ════════════════════════════════════════════════════════════════════════════
# RUNTIME AYARLARI
# ════════════════════════════════════════════════════════════════════════════
RUNTIME = {
    'depot_location_id': -1,                   # özel değer
    'verbose': True,
    'progress_bar': True,
    'parallel_runs': False,                    # ileride multiprocessing
}


if __name__ == "__main__":
    # Hızlı doğrulama
    print("Config yüklendi:")
    print(f"  Depo: {WAREHOUSE['num_aisles']} aisle × {WAREHOUSE['num_blocks']} blok = "
          f"{WAREHOUSE['total_locations']} lokasyon")
    print(f"  Ürün: {ITEMS['num_items']} (A={int(ITEMS['num_items']*WAREHOUSE['class_A_pct'])}, "
          f"B={int(ITEMS['num_items']*WAREHOUSE['class_B_pct'])}, "
          f"C={int(ITEMS['num_items']*WAREHOUSE['class_C_pct'])})")
    print(f"  DEPSO: {DEPSO['num_particles']} parçacık × {DEPSO['num_iterations']} iterasyon")
    print(f"  Senaryo 1: Tf={TIME_SERIES['scenario1_trend_Tf']}, Sf={TIME_SERIES['scenario1_seasonality_Sf']}")
    print(f"  Senaryo 2: Tf={TIME_SERIES['scenario2_trend_Tf']}, Sf={TIME_SERIES['scenario2_seasonality_Sf']}")
    print(f"  Veri dizini: {DATA_DIR}")
