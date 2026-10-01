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

from core.experiment import METAHEURISTICS, fmt_p, wilcoxon

def tr(x: float, spec: str = ".2f") -> str:
    return format(x, spec).replace('.', ',')


ALL_PAIRS = [('ALNS', 'DEPSO'), ('ALNS', 'RBRS-AE'), ('RBRS-AE', 'DEPSO'),
             ('RBRS-AE2', 'RBRS-AE'), ('ALNS', 'RBRS-AE2'), ('RBRS-AE2', 'DEPSO')]
# Sonuç dosyasında hangi algoritmalar varsa onlar (load() ayarlar); eski
# üç algoritmalı koşumlar da okunur.
ALGS = [a for a in METAHEURISTICS if a != 'RBRS-AE2']
PAIRS = [p for p in ALL_PAIRS if all(x in ALGS for x in p)]


def _set_algorithms(present) -> None:
    global ALGS, PAIRS
    ALGS = [a for a in METAHEURISTICS if a in present]
    PAIRS = [p for p in ALL_PAIRS if all(x in ALGS for x in p)]


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
               'size': r['spec']['size'], 'blocks': r['spec']['blocks'],
               'fill': round(r['spec'].get('fill', 0) * 100) or None}
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
    first = json.loads(files[0].read_text(encoding='utf-8'))['results'][0]
    _set_algorithms(first['stats'] if 'stats' in first else first)
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


def summarize(inst: list[dict], meta: dict) -> dict:
    """Web sitesi için makine okunur özet (site_data.py kullanır)."""
    proto = meta.get('protocol') or {'depso_iter': meta.get('depso_iter'), 'n_seeds': 1,
                                     'time_budget': None, 'time_per_order': None}
    i_w = defaultdict(int)
    for r in inst:
        i_w[winners({a: r[a]['td'] for a in ALGS})] += 1
    tests = [wilcoxon([r[a]['td'] for r in inst], [r[b]['td'] for r in inst]) for a, b in PAIRS]
    adj = holm([t['p'] for t in tests])
    pairs = []
    for (a, b), t, p in zip(PAIRS, tests, adj):
        pairs.append({'a': a, 'b': b, 'p': p, 'a_better': t['x_better'], 'b_better': t['y_better'],
                      'diff_pct': round(statistics.fmean((r[a]['td'] - r[b]['td']) / r[b]['td'] * 100
                                                         for r in inst), 3)})

    def gaps(key):
        out = {}
        for v in sorted({r[key] for r in inst if r.get(key) is not None}):
            sub = [r for r in inst if r[key] == v]
            out[str(v)] = {a: round(statistics.fmean(
                (r[a]['td'] - min(r[x]['td'] for x in ALGS)) / min(r[x]['td'] for x in ALGS) * 100
                for r in sub), 3) for a in ALGS}
        return out
    return {'n': len(inst), 'groups': len({r['group'] for r in inst}),
            'seeds': max(len(r[ALGS[0]]['td_seeds']) for r in inst),
            'protocol': proto, 'git': meta.get('git'), 'jobs': meta.get('jobs'),
            'wins': {c: i_w[c] for c in ALGS + ['berabere']}, 'pairs': pairs,
            'gap_by': {k: g for k in ('k', 'n_maxol', 'size', 'blocks', 'fill') if len(g := gaps(k)) > 1},
            'runtime': {a: round(statistics.fmean(r[a]['rt'] for r in inst), 2) for a in ALGS}}


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
    L += breakdown('fill', "Doluluk (%)")

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
