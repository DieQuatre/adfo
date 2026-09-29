"""
compare_algorithms.py
=====================
DEPSO, RBRS-AE ve ALNS'nin istatistiksel karşılaştırması.

    python compare_algorithms.py results/compare__s5__t60          # run_batch.py çıktısı
    python compare_algorithms.py results/generated/results__s5__t60.json   # run_generated.py
    python compare_algorithms.py results                            # eski tek tohumlu koşum
    python compare_algorithms.py results/only.json                  # --only koşumu

Rapor (<kaynak>/karsilastirma.md):
  - kod sürümü, protokol ve uyarılar (temiz olmayan kod, paralel süre ölçümü,
    eşit olmayan bütçe, tek tohum)
  - senaryo ve örnek bazında en iyi algoritma
  - ikili ortalama fark ve Wilcoxon işaretli sıralar testi (Holm düzeltmeli)
  - tohumlar arası değişkenlik
  - süre
Ölçüler örnek bazında: bir örneğin mesafesi, o örnekteki tohumların ortalaması.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.experiment import METAHEURISTICS as ALGS, fmt_p, wilcoxon

def tr(x: float, spec: str = ".2f") -> str:
    return format(x, spec).replace('.', ',')


PAIRS = [('ALNS', 'DEPSO'), ('ALNS', 'RBRS-AE'), ('RBRS-AE', 'DEPSO')]


# ── Okuma ──────────────────────────────────────────────────────────────

def _batch_rows(d: dict) -> list[dict]:
    rows = []
    for r in d['results']:
        st = r['stats']
        for i in range(r['n_instances']):
            row = {'group': r['scenario'], 'k': r['k'], 'n_maxol': r['n_maxol']}
            for a in ALGS:
                seeds = st[a].get('td_seeds')
                row[a] = {'td': st[a]['td'][i], 'rt': st[a]['rt'][i],
                          'td_seeds': seeds[i] if seeds else [st[a]['td'][i]]}
            rows.append(row)
    return rows


def _generated_rows(d: dict) -> list[dict]:
    rows = []
    for r in d['results']:
        row = {'group': r['name'], 'k': r['k'], 'n_maxol': None,
               'size': r['spec']['size'], 'blocks': r['spec']['blocks']}
        for a in ALGS:
            row[a] = {'td': r[a]['td'], 'rt': r[a]['rt'],
                      'td_seeds': r[a].get('td_seeds', [r[a]['td']])}
        rows.append(row)
    return rows


def load(source: Path) -> tuple[list[dict], dict]:
    """
    source: run_batch çıktı klasörü (batch_*.json), tek bir run_batch dosyası
    (ör. only.json) ya da run_generated results*.json.
    → (örnekler, meta). Örnek: {'group', 'k', 'n_maxol', ALG: {'td','rt','td_seeds'}}.
    """
    if not source.exists():
        sys.exit(f"{source} bulunamadı")
    files = sorted(source.glob("batch_*.json")) if source.is_dir() else [source]
    if not files:
        sys.exit(f"{source} içinde batch_*.json yok")
    meta, inst = {}, []
    for f in files:
        d = json.loads(f.read_text(encoding='utf-8'))
        meta = meta or {k: v for k, v in d.items() if k != 'results'}
        if d.get('git', {}).get('dirty'):
            meta.setdefault('_dirty_files', []).append(f.name)
        batch_format = bool(d['results']) and 'stats' in d['results'][0]
        inst += _batch_rows(d) if batch_format else _generated_rows(d)
    return inst, meta


# ── Hesaplar ───────────────────────────────────────────────────────────

def winners(values: dict) -> str:
    best = min(values.values())
    w = [a for a, v in values.items() if v <= best + 1e-6]
    return w[0] if len(w) == 1 else 'berabere'


def holm(pvals: list) -> list:
    """Holm-Bonferroni düzeltmesi (None'lar atlanır)."""
    idx = sorted((p, i) for i, p in enumerate(pvals) if p is not None)
    m, out, running = len(idx), [None] * len(pvals), 0.0
    for rank, (p, i) in enumerate(idx):
        running = max(running, min(1.0, (m - rank) * p))
        out[i] = running
    return out


def report(inst: list[dict], meta: dict, source: Path) -> str:
    proto = meta.get('protocol') or {'depso_iter': meta.get('depso_iter'), 'n_seeds': 1,
                                     'time_budget': None}
    git = meta.get('git') or {'commit': meta.get('git_commit', '?'), 'dirty': None}
    jobs = meta.get('jobs')
    n_seeds = max(len(r[ALGS[0]]['td_seeds']) for r in inst)
    L = ["# Algoritma karşılaştırması", "",
         f"Kaynak: `{source}`  ",
         f"Kod sürümü: `{git.get('commit')}`"
         + (" (commit'lenmemiş değişikliklerle)" if git.get('dirty') else "") + "  ",
         f"Protokol: " + (f"örnek başına {proto['time_budget']:g} sn eşit süre bütçesi"
                          if proto.get('time_budget') else
                          f"sipariş başına {proto['time_per_order']:g} sn eşit süre bütçesi"
                          if proto.get('time_per_order') else
                          f"iterasyon sınırlı (DEPSO {proto.get('depso_iter')}, RBRS-AE ve ALNS config.py)")
         + f", örnek başına {n_seeds} tohum, {len(inst)} örnek, "
         f"{len({r['group'] for r in inst})} grup  ",
         f"Paralel işlem: {jobs if jobs else 'kayıtlı değil'}", ""]

    warn = []
    if git.get('dirty') or meta.get('_dirty_files'):
        warn.append("Sonuçlar commit'lenmemiş kodla alınmış; birebir tekrarlanamaz.")
    if git.get('dirty') is None and 'git' not in meta:
        warn.append("Kod durumu kayıtlı değil (eski koşum).")
    if not (proto.get('time_budget') or proto.get('time_per_order')):
        warn.append("Algoritmaların iş bütçesi eşit değil (iterasyon sınırları farklı); "
                    "kalite farkının bir kısmı arama süresinden gelebilir.")
    if n_seeds == 1:
        warn.append("Örnek başına tek tohum: algoritmanın kendi rastgeleliği ölçülmüyor.")
    if jobs is None or jobs > 1:
        warn.append("Süreler paralel koşumda ölçüldü; hız karşılaştırması için "
                    "`--jobs 1` ile ayrı ölçüm gerekir.")
    if warn:
        L += ["> **Uyarılar**", ">"] + [f"> - {w}" for w in warn] + [""]

    # En iyi algoritma
    groups = defaultdict(list)
    for r in inst:
        groups[r['group']].append(r)
    g_w = defaultdict(int)
    for g in groups.values():
        g_w[winners({a: statistics.fmean(r[a]['td'] for r in g) for a in ALGS})] += 1
    i_w = defaultdict(int)
    for r in inst:
        i_w[winners({a: r[a]['td'] for a in ALGS})] += 1
    cols = ALGS + ['berabere']
    L += ["## En iyi algoritma", "",
          "| | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols),
          f"| Grup (ortalama mesafe) | " + " | ".join(f"{g_w[c]}/{len(groups)}" for c in cols) + " |",
          f"| Örnek | " + " | ".join(f"{i_w[c]}/{len(inst)}" for c in cols) + " |", ""]

    # İkili karşılaştırma
    tests = [wilcoxon([r[a]['td'] for r in inst], [r[b]['td'] for r in inst]) for a, b in PAIRS]
    adj = holm([t['p'] for t in tests])
    L += ["## İkili karşılaştırma", "",
          "Ortalama fark: örnek bazında (A − B) / B. Negatif: A daha kısa mesafe.  ",
          "p: Wilcoxon işaretli sıralar testi (iki yönlü), Holm düzeltmeli; "
          "< 0,05 fark anlamlı.", "",
          "| A | B | ortalama fark | A daha iyi | B daha iyi | eşit | p (Holm) |",
          "|---|---|---|---|---|---|---|"]
    for (a, b), t, p in zip(PAIRS, tests, adj):
        diff = statistics.fmean((r[a]['td'] - r[b]['td']) / r[b]['td'] * 100 for r in inst)
        L.append(f"| {a} | {b} | %{tr(diff, '+.2f')} | {t['x_better']} | {t['y_better']} | "
                 f"{t['ties']} | {fmt_p(p)} |")
    L.append("")

    # Kırılımlar
    def breakdown(key, title):
        vals = sorted({r[key] for r in inst if r.get(key) is not None})
        if len(vals) < 2:
            return []
        out = [f"### {title}", "",
               "Her algoritmanın, örnekteki en iyi sonuca göre ortalama sapması (%):", "",
               f"| {title} | n | " + " | ".join(ALGS) + " |", "|---|---|" + "---|" * len(ALGS)]
        for v in vals:
            sub = [r for r in inst if r[key] == v]
            gaps = []
            for a in ALGS:
                gaps.append(statistics.fmean(
                    (r[a]['td'] - min(r[x]['td'] for x in ALGS)) / min(r[x]['td'] for x in ALGS) * 100
                    for r in sub))
            out.append(f"| {v} | {len(sub)} | " + " | ".join(tr(g) for g in gaps) + " |")
        return out + [""]
    L += ["## Kırılımlar", ""]
    L += breakdown('k', "Sipariş sayısı")
    L += breakdown('n_maxol', "Sipariş başına en fazla satır")
    L += breakdown('size', "Depo boyutu")
    L += breakdown('blocks', "Blok sayısı")

    # Tohum değişkenliği
    if n_seeds > 1:
        L += ["## Tohumlar arası değişkenlik", "",
              "Aynı örnekte farklı tohumlarla mesafenin değişim katsayısı "
              "(std / ortalama, %) ve en iyi–en kötü tohum farkı:", "",
              "| Algoritma | ort. değişim katsayısı | ort. en iyi–en kötü fark |", "|---|---|---|"]
        for a in ALGS:
            cv, rng = [], []
            for r in inst:
                s = r[a]['td_seeds']
                if len(s) > 1:
                    m = statistics.fmean(s)
                    cv.append(statistics.stdev(s) / m * 100)
                    rng.append((max(s) - min(s)) / m * 100)
            L.append(f"| {a} | %{tr(statistics.fmean(cv))} | %{tr(statistics.fmean(rng))} |")
        L.append("")

    # Süre
    L += ["## Süre", "",
          "| Algoritma | ortalama süre (sn) |", "|---|---|"]
    for a in ALGS:
        L.append(f"| {a} | {tr(statistics.fmean(r[a]['rt'] for r in inst), '.1f')} |")
    L += ["", "Süre bütçeli koşumda süreler bütçeye yakın olmalı; paralel ölçümde "
          "süreler karşılaştırma için kullanılmamalı.", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source', type=Path, help="run_batch çıktı klasörü ya da run_generated results*.json")
    args = ap.parse_args()
    inst, meta = load(args.source)
    text = report(inst, meta, args.source)
    out = (args.source if args.source.is_dir() else args.source.parent) / (
        "karsilastirma.md" if args.source.is_dir() else f"karsilastirma_{args.source.stem}.md")
    out.write_text(text, encoding='utf-8')
    print(text)
    print(f"\nKayıt: {out}")


if __name__ == '__main__':
    main()
