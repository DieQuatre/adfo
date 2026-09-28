# ALNS: Adaptive Large Neighborhood Search

> Kod: `algorithms/alns.py`. Parametreler: `config.py` → `ALNS`.
> Bu belgede sayısal değeri verilmeyen parametreler (iterasyon sayısı, q aralığı,
> worst/related belirlilik üsleri) `config.py` içinde açıklamasıyla birlikte durur.

ALNS, Ropke ve Pisinger (2006) tarafından önerilen genel çerçeveye dayanır ve tek bir komşuluk yapısı yerine birden fazla yıkma (destroy) ve kurma (repair) operatörünü, bu operatörlerin geçmiş performansına göre güncellenen adaptif ağırlıklarla bir arada kullanır.

## 1. Problem Gösterimi

O = {o₁, o₂, ..., oₙ} sipariş kümesi olsun. Her sipariş oᵢ için L(oᵢ) lokasyon kümesini ve w(oᵢ) toplam ağırlığını (WU) tanımlayalım. Bir çözüm, siparişlerin ayrık batch'lere bölünmesidir:

**(1)**  S = {B₁, B₂, ..., Bₘ},  Bᵢ ∩ Bⱼ = ∅ (i ≠ j),  ⋃ᵢ Bᵢ = O

Her batch için kapasite kısıtı:

**(2)**  Σ_{o ∈ Bₖ} w(o) ≤ Q,  ∀k

Bir batch Bₖ'nin rota maliyeti TD(Bₖ), Bₖ'deki tüm siparişlerin lokasyonları üzerinde NN + 2-opt sezgiseli ile hesaplanır. Amaç fonksiyonu:

**(3)**  f(S) = Σₖ TD(Bₖ)

## 2. Genel Algoritma Akışı

Her iterasyonda bir yıkma operatörü d ∈ D ve bir kurma operatörü r ∈ R, ağırlıklarına orantılı olasılıkla seçilir; d ile bozulan çözüm r ile onarılır; elde edilen aday çözüm bir kabul kriteriyle değerlendirilir; belirli aralıklarla operatör ağırlıkları güncellenir.

## 3. Yıkma (Destroy) Operatörleri

### 3.1 Rastgele Kaldırma (Random Removal)

Mevcut çözümdeki tüm (sipariş, batch) eşleşmelerinden q tanesi düzgün rastgele seçilip kaldırılır:

**(4)**  R ⊂ {(o, Bₖ) : o ∈ Bₖ},  |R| = q, düzgün rastgele

### 3.2 En Kötüyü Kaldırma (Worst Removal)

Her sipariş o ∈ Bₖ için kaldırma kazancı:

**(5)**  g(o, Bₖ) = TD(Bₖ) − TD(Bₖ \ {o})

Adaylar g'ye göre azalan sıraya konur; rastgele bir y ~ U(0,1) ve sabit bir p parametresi ile

**(6)**  seçilen_indeks = ⌊yᵖ · |aday listesi|⌋

biçiminde biased-random seçim yapılır (p büyüdükçe seçim determinizme yaklaşır). Bu, saf açgözlü seçimin yol açacağı çeşitlilik kaybını önler.

### 3.3 İlişkili Kaldırma (Related / Shaw Removal)

Rastgele bir "tohum" sipariş seçilip kaldırılan kümeye eklenir. Kalan her aday sipariş o için, o'nun lokasyonlarının şu ana kadar kaldırılmış küme R'ye olan yakınlığı:

**(7)**  rel(o, R) = (1 / |L(o)|) · Σ_{l ∈ L(o)} min_{r ∈ R} d(l, r)

En düşük rel değerine sahip adaylar (yine (6)'daki gibi biased-random ile) sırayla kaldırılan kümeye eklenir, ta ki q siparişe ulaşılana kadar. Amaç, mekânsal olarak birbirine yakın siparişleri birlikte söküp farklı bir batch kombinasyonuna izin vermektir.

## 4. Kurma (Repair) Operatörleri

Bir siparişin o bir batch'e Bₖ eklenmesinin marjinal maliyeti:

**(8)**  Δ(o, Bₖ) = TD(Bₖ ∪ {o}) − TD(Bₖ),  eğer w(Bₖ) + w(o) ≤ Q
     Δ(o, ∅) = TD({o})  (yeni batch açma maliyeti)

### 4.1 Açgözlü Kurma (Greedy Insertion)

Atanmamış her sipariş için tüm uygun hedefler arasında en düşük Δ bulunur; global en düşük Δ değerine sahip (sipariş, hedef) çifti yerleştirilir. Tüm siparişler atanana kadar tekrarlanır:

**(9)**  (o*, B*) = argmin_{o, Bₖ} Δ(o, Bₖ)

### 4.2 Regret-2 Kurma (Regret-2 Insertion)

Atanmamış her sipariş o için, uygun hedeflere göre sıralanmış maliyetler Δ₍₁₎ ≤ Δ₍₂₎ ≤ ... olsun. Regret değeri:

**(10)**  regret(o) = Δ₍₂₎ − Δ₍₁₎

En yüksek regret değerine sahip sipariş, kendi en iyi hedefine (Δ₍₁₎) yerleştirilir. Bu, "ileride pahalıya patlayacak" siparişleri önce güvenceye alır.

## 5. Adaptif Ağırlıklandırma

Her operatör φ (yıkma veya kurma kümesinden) bir ağırlık wᵩ taşır. Seçim olasılığı, aynı gruptaki operatörler arasında ağırlıkla orantılıdır (rulet çarkı seçimi):

**(11)**  p(φ) = wᵩ / Σ_{φ' ∈ grup} w_{φ'}

Bir segment (Δ_seg iterasyon) boyunca kullanılan her operatör, sonucuna göre puan biriktirir:

**(12)**
- σ₁ : yeni küresel en iyi çözüm bulunduysa
- σ₂ : mevcut çözümden iyi (ama en iyi değil) bir çözüm bulunduysa
- σ₃ : iyileştirmeyen ama kabul edilen bir çözüm bulunduysa
- 0  : reddedildiyse

Segment sonunda ağırlıklar güncellenir (r = reaksiyon katsayısı, nᵩ = o segmentte φ'nin kullanım sayısı):

**(13)**  wᵩ ← (1 − r) · wᵩ + r · (πᵩ / nᵩ),  eğer nᵩ > 0

Bu çalışmada kullanılan parametre değerleri: σ₁ = 33, σ₂ = 20, σ₃ = 8, r = 0.15, Δ_seg = 40 iterasyon.

## 6. Kabul Kriteri (Simulated Annealing)

Aday çözüm S′, mevcut çözüm S_cur'dan iyiyse doğrudan kabul edilir. Değilse, azalan bir olasılıkla yine de kabul edilir:

**(14)**  P(kabul) = exp( −(f(S′) − f(S_cur)) / T )

Sıcaklık her iterasyonda geometrik olarak azaltılır:

**(15)**  T ← T · c,  0 < c < 1

Başlangıç sıcaklığı T₀, ilk çözümden w₀ oranında kötü bir çözümün %50 olasılıkla kabul edilmesini sağlayacak şekilde belirlenir:

**(16)**  T₀ = − (w₀ · f(S₀)) / ln(0.5)

Bu çalışmada w₀ = 0.05, c = 0.9975 kullanılmıştır.

## 7. Sözde Kod (Pseudocode)

```
Algoritma: ALNS (Adaptive Large Neighborhood Search)
Girdi: O (sipariş kümesi), Q (kapasite), max_iter, segment_uzunluğu
Çıktı: en iyi çözüm S_best

1:  S ← RegretKurma(∅, O)                      // başlangıç çözümü
2:  S_best ← S; S_cur ← S
3:  T ← BaşlangıçSıcaklığı(S)
4:  w_d[1..3] ← 1, w_r[1..2] ← 1               // operatör ağırlıkları
5:  π_d, π_r, n_d, n_r ← 0

6:  for it = 1 to max_iter do
7:      d ← RuletSeç(w_d)                       // yıkma operatörü
8:      r ← RuletSeç(w_r)                       // kurma operatörü
9:      q ← RastgeleTamsayı(q_min, q_max)
10:     S' ← r( d(S_cur, q) )                    // yık, kur
11:     Δf ← f(S') − f(S_cur)

12:     if f(S') < f(S_best) then
13:         S_best ← S'; S_cur ← S'; puan ← σ1
14:     else if f(S') < f(S_cur) then
15:         S_cur ← S'; puan ← σ2
16:     else if RastgeleSayı() < exp(−Δf / T) then
17:         S_cur ← S'; puan ← σ3
18:     else
19:         puan ← 0

20:     π_d[d] += puan; π_r[r] += puan
21:     n_d[d] += 1; n_r[r] += 1
22:     T ← T · c

23:     if it mod segment_uzunluğu == 0 then
24:         w_d ← AğırlıkGüncelle(w_d, π_d, n_d)
25:         w_r ← AğırlıkGüncelle(w_r, π_r, n_r)
26:         π_d, π_r, n_d, n_r ← 0

27: return S_best
```

## 8. Uygulama notları (kodda verilen kararlar)

- **Worst removal:** Kazançlar (5) iterasyon başında bir kez hesaplanır; q sipariş, sıralı listeden (6) ile tekrar yerine konmadan seçilir. (Ropke ve Pisinger her kaldırmadan sonra yeniden hesaplar; maliyet nedeniyle bir kez hesaplanıyor.)
- **Regret-2:** Yalnızca yeni grup seçeneği olan siparişin regret'i sonsuz kabul edilir, yani önce yerleştirilir. Eşitlikte düşük Δ₍₁₎ kazanır.
- **q aralığı:** q_min = max(2, ⌈0,05·n⌉), q_max = min(30, max(q_min, ⌈0,15·n⌉)).
- **Rota:** TD, DEPSO ve RBRS-AE ile aynı ortak rota servisinden (`RouteCache`, NN + 2-opt) okunur.

---

**Notlar:**

- (13)'teki wᵩ güncelleme formülü ile (11)'deki seçim olasılığı, ALNS'in "öğrenen" tarafını oluşturur — RBRS-AE'nin sabit %20→%10 lineer azalan elimination oranıyla karşılaştırma yapılacaksa bu fark vurgulanabilir.
- Kapasite kısıtı (2) ve rota hesaplama yöntemi (NN+2-opt), DEPSO ve RBRS-AE bölümleriyle birebir aynı tutuldu; bu, üç algoritmanın karşılaştırmasının adil olduğunu (tek değişkenin arama stratejisi olduğunu) matematiksel olarak da gösteriyor.
