"""
regen_35.py
============
`results/batch_1..7.json` dosyalarından 35 senaryo raporunu üretir.

Bu betik ARTIK HİÇBİR ALGORİTMA KOŞMAZ. Tek işi, `run_batch.py`'ın ürettiği
canlı ölçümleri okuyup tabloya dökmek.

NEDEN DEĞİŞTİ
-------------
Önceki sürüm iki farklı deneyi tek tabloda yan yana koyuyordu:
  - DEPSO sütunu: canlı, ama yalnızca 2 instance / 20 iterasyon.
  - RBRS-AE sütunu: 35 satırın 27'si `batch_*.json`'dan KOPYA, üstelik farklı
    veriden (sentetik siparişler, farklı instance ve iterasyon sayısı).
Kopyalama yüzünden tabloda birebir tekrar eden değerler oluşuyordu; örneğin
100_6_10, 150_6_10 ve 200_6_10 satırlarının üçü de -77.06% gösteriyordu.

Artık `run_batch.py` her senaryo için SOP, FCFS, DEPSO ve RBRS-AE'yi aynı
instance'lar üzerinde canlı ölçüyor (ve k parametresi düzeltildiği için 35
senaryo gerçekten 35 farklı deney). Doğru davranış: tek kaynaktan okuyup
raporlamak.

Çalıştır:
    python run_batch.py --batch 1   # ... --batch 7 (önce)
    python regen_35.py              # sonra
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Paper Appendix H referans değerleri: DEPSO vs SOP (Ø %)
PAPER = {
    '50_2_6':    -88.52, '50_2_10':   -87.13, '50_6_2':    -87.36,
    '50_6_6':    -81.54, '50_6_10':   -77.49, '50_10_2':   -84.83,
    '50_10_6':   -76.61, '50_10_10':  -70.60,
    '100_2_2':   -92.74, '100_2_6':   -90.79, '100_2_10':  -88.63,
    '100_6_2':   -89.20, '100_6_6':   -82.77, '100_6_10':  -78.51,
    '100_10_2':  -86.23, '100_10_6':  -77.36, '100_10_10': -71.25,
    '150_2_2':   -94.22, '150_2_6':   -91.23, '150_2_10':  -89.25,
    '150_6_2':   -89.34, '150_6_6':   -82.89, '150_6_10':  -78.45,
    '150_10_2':  -86.22, '150_10_6':  -77.32, '150_10_10': -71.41,
    '200_2_2':   -94.26, '200_2_6':   -91.54, '200_2_10':  -89.26,
    '200_6_2':   -89.61, '200_6_6':   -82.58, '200_6_10':  -78.35,
    '200_10_2':  -86.11, '200_10_6':  -77.21, '200_10_10': -71.57,
}

TOLERANCE_POINTS = 5.0   # |sapma| bu değerin altındaysa ✅


def _mean(v):
    return sum(v) / len(v) if v else 0.0


def _git_commit() -> str:
    """Sonuçların hangi kod sürümünden geldiğini kayda geç."""
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        rev = out.stdout.strip() or "unknown"
        dirty = subprocess.run(["git", "status", "--porcelain"],
                               capture_output=True, text=True, timeout=5)
        return rev + ("-dirty" if dirty.stdout.strip() else "")
    except Exception:
        return "unknown"


def load_batches() -> tuple[list, dict, list]:
    """
    batch_*.json dosyalarını oku.

    Döndürür: (satırlar, ilk batch'in ayarları, uyarı listesi).
    Uyarılar hem ekrana hem RAPORUN İÇİNE yazılır: rapor tek başına dolaşıma
    girdiğinde "5 instance / 500 iterasyon" başlığı, aslında 100 iterasyonla
    veya sentetik siparişle koşulmuş batch'leri gizlememeli.
    """
    rows, meta, warnings = [], {}, []
    for i in range(1, 8):
        path = Path("results") / f"batch_{i}.json"
        if not path.exists():
            msg = f"{path.name} yok — `python run_batch.py --batch {i}` çalıştırılmamış"
            print(f"  ⚠ {msg}")
            warnings.append(msg)
            continue

        data = json.loads(path.read_text())
        meta.setdefault("n_instances", data.get("n_instances"))
        meta.setdefault("depso_iter", data.get("depso_iter"))

        if (data.get("n_instances") != meta["n_instances"]
                or data.get("depso_iter") != meta["depso_iter"]):
            msg = (f"{path.name} farklı ayarla koşulmuş "
                   f"(n={data.get('n_instances')}, iter={data.get('depso_iter')}); "
                   f"beklenen n={meta['n_instances']}, iter={meta['depso_iter']}")
            print(f"  ⚠ {msg}")
            warnings.append(msg)

        # Sentetik sipariş kaynağı paper karşılaştırmasını geçersiz kılar.
        synthetic = sorted({r['scenario'] for r in data.get("results", [])
                            if r.get('order_source') not in (None, 'data_pool')})
        if synthetic:
            msg = f"{path.name} sentetik sipariş kaynağı kullanmış: {', '.join(synthetic)}"
            print(f"  ⚠ {msg}")
            warnings.append(msg)

        rows.extend(data.get("results", []))
    return rows, meta, warnings


def check_independence(rows: list) -> list[str]:
    """
    Aynı (n_maxol, a_maxol) kombinasyonunda farklı k değerleri AYNI sonucu
    vermemeli. Verirse sipariş üreticisi k'yı yok sayıyor demektir.
    """
    seen, dupes = {}, []
    for r in rows:
        sig = (r['n_maxol'], r['a_maxol'],
               r['stats']['DEPSO']['mean_td'], r['stats']['SOP']['mean_td'])
        if sig in seen:
            dupes.append(f"{r['scenario']} == {seen[sig]}")
        else:
            seen[sig] = r['scenario']
    return dupes


def write_report(rows: list, meta: dict, dupes: list, warnings: list) -> str:
    n_inst = meta.get("n_instances", "?")
    d_iter = meta.get("depso_iter", "?")

    lines = ["# Paper Appendix H — 35 Senaryo Karşılaştırması", ""]
    lines.append(f"**{n_inst} instance / senaryo, DEPSO {d_iter} iterasyon** — "
                 f"tüm sütunlar aynı instance'lar üzerinde CANLI ölçüldü.")
    lines.append("")
    lines.append(f"Kod sürümü: `{_git_commit()}`  ")
    lines.append("Kaynak: `results/batch_1..7.json`")
    lines.append("")

    # Başlıktaki konfigürasyon tüm satırlar için geçerli değilse, raporu
    # okuyan kişi bunu tablodan önce görmeli.
    if warnings:
        lines.append("> ⚠️ **BU TABLO TEK TİP DEĞİL** — başlıktaki "
                     "konfigürasyon bütün satırlar için geçerli değil:")
        lines.append("")
        lines += [f">   - {w}" for w in warnings]
        lines.append(">")
        lines.append("> Etkilenen batch'leri aynı ayarla yeniden koşmadan bu "
                     "tabloyu yayımlamayın.")
        lines.append("")
    lines.append("| Senaryo | DEPSO vs SOP | Paper | Fark | RBRS-AE vs SOP "
                 "| DEPSO vs FCFS | Durum |")
    lines.append("|---|---|---|---|---|---|---|")

    devs, ok_count = [], 0
    for r in sorted(rows, key=lambda x: (x['k'], x['n_maxol'], x['a_maxol'])):
        name = r['scenario']
        paper = PAPER.get(name)
        if paper is None:
            continue
        d_sop = r['stats']['DEPSO']['vs_sop_mean']
        d_fcfs = r['stats']['DEPSO']['vs_fcfs_mean']
        rb_sop = r['stats']['RBRS-AE']['vs_sop_mean']
        diff = d_sop - paper
        devs.append(abs(diff))
        ok = abs(diff) < TOLERANCE_POINTS
        ok_count += ok
        lines.append(f"| {name} | {d_sop:.2f}% | {paper:.2f}% | {diff:+.2f}% "
                     f"| {rb_sop:.2f}% | {d_fcfs:.2f}% | {'✅' if ok else '⚠️'} |")

    signed = _mean([r['stats']['DEPSO']['vs_sop_mean'] - PAPER[r['scenario']]
                    for r in rows if r['scenario'] in PAPER])

    lines += [
        "",
        f"**Ortalama mutlak sapma: ±{_mean(devs):.2f} puan**  ",
        f"**Ortalama işaretli sapma: {signed:+.2f} puan** "
        f"(0'a yakın olması sistematik yanlılık olmadığını gösterir)  ",
        f"**Maks sapma: ±{max(devs):.2f} puan**  ",
        f"**±{TOLERANCE_POINTS:.0f} puan içinde: {ok_count}/{len(devs)}**",
        "",
    ]

    if dupes:
        lines += ["> ⚠️ **BAĞIMSIZLIK UYARISI** — aşağıdaki senaryolar birebir "
                  "aynı sonucu verdi, yani aynı deney tekrar raporlanıyor:", ""]
        lines += [f">   - {d}" for d in dupes]
        lines.append("")
    else:
        lines.append("> Bağımsızlık kontrolü: 35 senaryonun tamamı farklı "
                     "sonuç üretti — kopya satır yok. ✅")
        lines.append("")

    return "\n".join(lines)


def main():
    rows, meta, warnings = load_batches()
    if not rows:
        print("Sonuç yok. Önce: python run_batch.py --batch 1 ... --batch 7")
        sys.exit(1)

    print(f"Okunan senaryo: {len(rows)}/35")
    dupes = check_independence(rows)
    if dupes:
        print(f"⚠ {len(dupes)} kopya senaryo bulundu:")
        for d in dupes:
            print(f"    {d}")
    else:
        print("✓ Bağımsızlık kontrolü geçti — kopya satır yok")

    Path("results").mkdir(exist_ok=True)
    Path("results/paper_35_scenarios.md").write_text(
        write_report(rows, meta, dupes, warnings))

    Path("results/paper_35_scenarios.json").write_text(json.dumps({
        "meta": {
            "source": "results/batch_1..7.json (tümü canlı ölçüm)",
            "n_instances": meta.get("n_instances"),
            "depso_iter": meta.get("depso_iter"),
            "git_commit": _git_commit(),
            "duplicate_scenarios": dupes,
            "config_warnings": warnings,
        },
        "results": rows,
        "paper_reference": PAPER,
    }, indent=2, ensure_ascii=False))

    print("✓ results/paper_35_scenarios.md")
    print("✓ results/paper_35_scenarios.json")


if __name__ == "__main__":
    main()
