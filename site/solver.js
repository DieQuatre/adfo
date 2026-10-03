/*
 * Raf Arası — "Kendin dene" tarayıcı çözücüsü.
 *
 * Araştırmanın Python kodundaki dört algoritmanın (DEPSO, RBRS-AE, RBRS-AE2,
 * ALNS) aynı mantıkla ama hafifletilmiş ayarlarla JavaScript sürümü. Sonuçlar resmî
 * deneylerle birebir aynı olmak zorunda değildir.
 *
 * rafSolverLib() kendi içinde tamamdır: hem ana sayfada hem Web Worker içinde
 * (fonksiyon metni blob'a yazılarak) çalışır.
 */
function rafSolverLib() {
  'use strict';

  // ── tohumlu rastgele sayı ────────────────────────────────────────────
  function rng(seed) {
    let a = (seed >>> 0) || 1;
    const next = () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    return {
      next,
      int: (lo, hi) => lo + Math.floor(next() * (hi - lo + 1)),
      pick: arr => arr[Math.floor(next() * arr.length)],
      shuffle(arr) { for (let i = arr.length - 1; i > 0; i--) { const j = Math.floor(next() * (i + 1)); [arr[i], arr[j]] = [arr[j], arr[i]]; } return arr; },
    };
  }

  // ════════════════════════════════════════════════════════════════════
  // DEPO DÜZENİ VE YÜRÜME AĞI
  // ════════════════════════════════════════════════════════════════════
  /**
   * p: {aisles, blocks, racks (blok başına raf), door: 'alt-sag'|'alt-orta'|'alt-sol'|'sag-orta'}
   * Koridorlar x yönünde uzanır. Alt ve üst kenarda birer ana koridor,
   * blokların arasında ve iki uçta ara koridorlar var.
   */
  function buildLayout(p) {
    const A = p.aisles, B = p.blocks, R = p.racks, cw = 2;
    const rowsY = [0.5];
    for (let i = 0; i < A; i++) rowsY.push(2.5 + 3 * i);
    rowsY.push(3 * A + 1.5);
    const K = rowsY.length;                          // alt + A koridor + üst
    const xc = []; for (let j = 0; j <= B; j++) xc.push(cw / 2 + j * (cw + R));
    const W = (B + 1) * cw + B * R, H = 3 * A + 2;
    const node = (j, k) => j * K + k;
    const N = (B + 1) * K;
    const coord = n => [xc[Math.floor(n / K)], rowsY[n % K]];
    // Floyd–Warshall
    const D = new Float64Array(N * N).fill(Infinity), nxt = new Int32Array(N * N).fill(-1);
    for (let i = 0; i < N; i++) { D[i * N + i] = 0; nxt[i * N + i] = i; }
    const edge = (a, b, w) => { D[a * N + b] = D[b * N + a] = w; nxt[a * N + b] = b; nxt[b * N + a] = a; };
    for (let j = 0; j <= B; j++) for (let k = 0; k + 1 < K; k++) edge(node(j, k), node(j, k + 1), rowsY[k + 1] - rowsY[k]);
    for (let k = 0; k < K; k++) for (let j = 0; j < B; j++) edge(node(j, k), node(j + 1, k), xc[j + 1] - xc[j]);
    for (let m = 0; m < N; m++) for (let i = 0; i < N; i++) {
      const dim = D[i * N + m]; if (dim === Infinity) continue;
      for (let j = 0; j < N; j++) { const v = dim + D[m * N + j]; if (v < D[i * N + j]) { D[i * N + j] = v; nxt[i * N + j] = nxt[i * N + m]; } }
    }
    // Lokasyonlar: koridor i, blok b, taraf s, raf r
    const locs = [];
    for (let i = 0; i < A; i++) for (let b = 0; b < B; b++) for (let s = 0; s < 2; s++) for (let r = 0; r < R; r++) {
      const x = (b + 1) * cw + b * R + r + 0.5, y = rowsY[i + 1];
      locs.push({id: locs.length, x, y, side: s, a: node(b, i + 1), b: node(b + 1, i + 1), da: x - xc[b], db: xc[b + 1] - x});
    }
    // Kapı
    let door;
    const onRow = (k, x) => { let j = 0; while (j < B - 1 && x > xc[j + 1]) j++; return {x, y: rowsY[k], a: node(j, k), b: node(j + 1, k), da: x - xc[j], db: xc[j + 1] - x}; };
    if (p.door === 'sag-orta') {
      const kk = Math.floor((K - 1) / 2), y = (rowsY[kk] + rowsY[kk + 1]) / 2;
      door = {x: xc[B], y, a: node(B, kk), b: node(B, kk + 1), da: y - rowsY[kk], db: rowsY[kk + 1] - y};
    } else {
      const f = p.door === 'alt-sol' ? 0 : p.door === 'alt-orta' ? 0.5 : 1;
      const x = B === 0 ? xc[0] : xc[0] + f * (xc[B] - xc[0]);
      door = f === 1 ? {x, y: rowsY[0], a: node(B - 1, 0), b: node(B, 0), da: xc[B] - xc[B - 1], db: 0}
                     : onRow(0, x);
    }
    door.id = -1;
    const pt = id => id === -1 ? door : locs[id];
    function dist(i, j) {
      if (i === j) return 0;
      const P = pt(i), Q = pt(j);
      if ((P.a === Q.a && P.b === Q.b) || (P.a === Q.b && P.b === Q.a)) return Math.abs(P.x - Q.x) + Math.abs(P.y - Q.y);
      let best = Infinity;
      for (const [ea, dp] of [[P.a, P.da], [P.b, P.db]]) for (const [eb, dq] of [[Q.a, Q.da], [Q.b, Q.db]]) {
        const v = dp + D[ea * N + eb] + dq; if (v < best) best = v;
      }
      return best;
    }
    function walk(i, j) {
      const P = pt(i), Q = pt(j);
      if ((P.a === Q.a && P.b === Q.b) || (P.a === Q.b && P.b === Q.a)) return [[Q.x, Q.y]];
      let best = Infinity, be = null;
      for (const [ea, dp] of [[P.a, P.da], [P.b, P.db]]) for (const [eb, dq] of [[Q.a, Q.da], [Q.b, Q.db]]) {
        const v = dp + D[ea * N + eb] + dq; if (v < best) { best = v; be = [ea, eb]; }
      }
      const out = []; let u = be[0];
      out.push(coord(u));
      while (u !== be[1]) { u = nxt[u * N + be[1]]; out.push(coord(u)); }
      out.push([Q.x, Q.y]);
      return out;
    }
    // Çizim geometrisi (sitenin drawFloor biçimi, y yukarı)
    const racks = [], bands = [];
    for (let i = 0; i < A; i++) for (let b = 0; b < B; b++) {
      const x0 = (b + 1) * cw + b * R, yc = rowsY[i + 1];
      racks.push([x0, yc - 1.5, R, 1]); racks.push([x0, yc + 0.5, R, 1]);
    }
    for (let j = 0; j <= B; j++) bands.push([xc[j] - cw / 2, 0, cw, H]);
    bands.push([0, 0, W, 1]); bands.push([0, H - 1, W, 1]);
    const geometry = {w: W, h: H, depot: [door.x, door.y], racks, bands, cross: xc, crossW: cw};
    return {p, locs, door, dist, walk, geometry, W, H};
  }

  // ════════════════════════════════════════════════════════════════════
  // SİPARİŞLER
  // ════════════════════════════════════════════════════════════════════
  const itemWeight = id => 0.1 + 0.9 * (((id * 2654435761) >>> 0) % 1000) / 1000;

  /** Rastgele siparişler. popular: çok satanlar kapıya yakın (ABC). */
  function makeOrders(L, n, maxLines, popular, seed) {
    const R = rng(seed);
    const ids = L.locs.map(l => l.id);
    let pickLoc;
    if (popular) {
      const byD = ids.slice().sort((a, b) => L.dist(-1, a) - L.dist(-1, b));
      const nA = Math.max(1, Math.round(ids.length * .05)), nB = Math.max(1, Math.round(ids.length * .15));
      const zA = byD.slice(0, nA), zB = byD.slice(nA, nA + nB), zC = byD.slice(nA + nB);
      pickLoc = () => { const u = R.next(); return R.pick(u < .45 ? zA : u < .75 ? zB : zC); };
    } else pickLoc = () => R.pick(ids);
    const orders = [];
    for (let o = 0; o < n; o++) {
      const lines = R.int(1, maxLines), set = new Set();
      while (set.size < lines) set.add(pickLoc());
      const locs = [...set];
      const w = locs.reduce((s, l) => s + R.int(1, 4) * itemWeight(l), 0);
      orders.push({id: o, locs, w: Math.round(w * 100) / 100});
    }
    return orders;
  }
  function manualOrder(id, locs, R) {
    return {id, locs: locs.slice(), w: Math.round(locs.reduce((s, l) => s + 2 * itemWeight(l), 0) * 100) / 100};
  }

  // ════════════════════════════════════════════════════════════════════
  // ROTA SERVİSİ (NN + 2-opt, önbellekli) — Python'daki RouteCache karşılığı
  // ════════════════════════════════════════════════════════════════════
  function routeService(L) {
    const dcache = new Map(), rcache = new Map();
    const d = (i, j) => { if (i === j) return 0; const k = i < j ? i * 100003 + j : j * 100003 + i; let v = dcache.get(k); if (v === undefined) { v = L.dist(i, j); dcache.set(k, v); } return v; };
    function route(locSet) {
      const key = locSet.slice().sort((a, b) => a - b).join(',');
      let r = rcache.get(key);
      if (r) return r;
      const pts = [...new Set(locSet)];
      const tour = [-1]; const left = new Set(pts); let cur = -1, total = 0;
      while (left.size) { let bn = null, bd = Infinity; for (const q of left) { const v = d(cur, q); if (v < bd) { bd = v; bn = q; } } tour.push(bn); left.delete(bn); total += bd; cur = bn; }
      total += d(cur, -1); tour.push(-1);
      let noImp = 0;
      for (let it = 0; it < 30 && noImp < 2; it++) {
        let imp = false;
        for (let i = 1; i < tour.length - 2; i++) for (let j = i + 1; j < tour.length - 1; j++) {
          const delta = d(tour[i - 1], tour[j]) + d(tour[i], tour[j + 1]) - d(tour[i - 1], tour[i]) - d(tour[j], tour[j + 1]);
          if (delta < -1e-9) { tour.splice(i, j - i + 1, ...tour.slice(i, j + 1).reverse()); total += delta; imp = true; }
        }
        noImp = imp ? 0 : noImp + 1;
      }
      r = {tour, dist: total}; rcache.set(key, r); return r;
    }
    return {route, cost: locs => locs.length ? route(locs).dist : 0};
  }

  // ── ortak yardımcılar ────────────────────────────────────────────────
  const locsOf = (orders, idxs) => idxs.flatMap(i => orders[i].locs);
  function firstFit(orders, perm, Q) {
    const bs = [];
    for (const i of perm) {
      let placed = false;
      for (const b of bs) if (b.w + orders[i].w <= Q) { b.o.push(i); b.w += orders[i].w; placed = true; break; }
      if (!placed) bs.push({o: [i], w: orders[i].w});
    }
    return bs.map(b => b.o);
  }
  const total = (orders, batches, RS) => batches.reduce((s, b) => s + RS.cost(locsOf(orders, b)), 0);

  // ════════════════════════════════════════════════════════════════════
  // DEPSO (hafif): parçacıklar permütasyon; first-fit + rota
  // ════════════════════════════════════════════════════════════════════
  function depso(orders, Q, RS, R, cfg, progress) {
    const n = orders.length, P = 5, iters = cfg.depsoIter;
    const evalPerm = perm => total(orders, firstFit(orders, perm, Q), RS);
    const parts = [];
    for (let p = 0; p < P; p++) {
      let perm = [...Array(n).keys()];
      if (p === 0) { // "savings" yerine: kapıya uzaklığa göre sıralı başlangıç
        const c = i => orders[i].locs.reduce((s, l) => s + RS.cost([l]), 0) / orders[i].locs.length;
        perm.sort((a, b) => c(a) - c(b));
      } else R.shuffle(perm);
      const f = evalPerm(perm);
      parts.push({perm, f, bp: perm.slice(), bf: f, v: perm.map(() => R.int(-1, 1))});
    }
    let g = parts.reduce((a, b) => a.f < b.f ? a : b); let gp = g.perm.slice(), gf = g.f, stag = 0;
    const diff = (a, b) => a.reduce((s, x, i) => s + (x !== b[i]), 0) / a.length;
    for (let it = 1; it <= iters; it++) {
      const prev = gf;
      for (const p of parts) {
        const bg = diff(p.perm, gp), bpb = diff(p.perm, p.bp);
        for (let h = 0; h < n; h++) {
          let comp = null;
          if (p.v[h] === 1 && bg > .5 * R.next()) comp = gp; else if (p.v[h] === -1 && bpb > R.next()) comp = p.bp;
          if (comp) { const r = p.perm.indexOf(comp[h]); if (r !== h && (p.v[r] !== 0 || R.next() < .5)) [p.perm[h], p.perm[r]] = [p.perm[r], p.perm[h]]; }
          p.v[h] = R.int(-1, 1);
        }
        p.f = evalPerm(p.perm);
        if (p.f < p.bf) { p.bf = p.f; p.bp = p.perm.slice(); }
        if (p.f < gf) { gf = p.f; gp = p.perm.slice(); }
      }
      stag = gf < prev - 1e-9 ? 0 : stag + 1;
      // mutasyon
      const fmax = Math.max(...parts.map(p => p.f));
      for (const p of parts) {
        if (R.next() > .5) continue;
        const cl = fmax > gf ? (p.f - gf) / (fmax - gf) : 0;
        const i = R.int(0, n - 1), j = R.int(0, n - 1);
        if (cl < .5) [p.perm[i], p.perm[j]] = [p.perm[j], p.perm[i]];
        else if (cl < .8) { const x = p.perm.splice(i, 1)[0]; p.perm.splice(j, 0, x); }
        else { const [a, b] = i < j ? [i, j] : [j, i]; p.perm.splice(a, b - a + 1, ...p.perm.slice(a, b + 1).reverse()); }
      }
      // yerel arama
      const thr = Math.round(20 * (1 - it / iters)) + 1;
      if (stag > thr * R.next()) {
        for (let t = 0; t < 30; t++) {
          const trial = gp.slice(), i = R.int(0, n - 1), j = R.int(0, n - 1);
          [trial[i], trial[j]] = [trial[j], trial[i]];
          const f = evalPerm(trial);
          if (f < gf) { gf = f; gp = trial; stag = 0; parts[R.int(0, P - 1)].perm = trial.slice(); break; }
        }
      }
      if (it % 10 === 0) progress(it / iters);
    }
    return firstFit(orders, gp, Q);
  }

  // ════════════════════════════════════════════════════════════════════
  // RBRS-AE (hafif): öncelik + regret ataması, shift/swap, uyarlanır eleme
  // v2 = RBRS-AE2: eleme kuralı her adımda üçünden biri (en kötü turlar /
  // konumca yakın siparişler / rastgele), geri yerleştirme regret-2 ile,
  // eleme 2 turda da çalışır. xy: siparişlerin ağırlık merkezi [x, y].
  // ════════════════════════════════════════════════════════════════════
  function rbrsae(orders, Q, RS, R, cfg, progress, v2, xy) {
    const n = orders.length;
    const ad = [], vr = [], wt = [];
    orders.forEach(o => {
      ad.push(o.locs.reduce((s, l) => s + RS.cost([l]) / 2, 0) / o.locs.length);
      const ds = []; for (let i = 0; i < o.locs.length; i++) for (let j = i + 1; j < o.locs.length; j++) ds.push(RS.cost([o.locs[i], o.locs[j]]));
      const m = ds.length ? ds.reduce((a, b) => a + b, 0) / ds.length : 0;
      vr.push(ds.length ? ds.reduce((s, x) => s + (x - m) ** 2, 0) / ds.length : 0); wt.push(o.w);
    });
    const mx = a => Math.max(...a) || 1;
    const pri = orders.map((_, i) => .5 * ad[i] / mx(ad) + .3 * vr[i] / mx(vr) + .2 * wt[i] / mx(wt));
    const B = () => ({o: [], w: 0, d: 0});
    const cost = b => RS.cost(locsOf(orders, b.o));
    function insertOpts(i, bs) {
      const opts = [];
      bs.forEach((b, k) => { if (b.w + orders[i].w <= Q) opts.push([RS.cost(locsOf(orders, b.o.concat(i))) - b.d, k]); });
      opts.push([RS.cost(orders[i].locs), -1]);
      return opts.sort((a, b) => a[0] - b[0]);
    }
    const put = (bs, i, k) => { if (k === -1) { const b = B(); b.o.push(i); b.w = orders[i].w; b.d = cost(b); bs.push(b); } else { const b = bs[k]; b.o.push(i); b.w += orders[i].w; b.d = cost(b); } };
    // regret ataması
    let bs = []; const left = new Set([...Array(n).keys()]);
    while (left.size) {
      let best = null;
      for (const i of left) { const op = insertOpts(i, bs); const reg = op.length > 1 ? op[1][0] - op[0][0] : op[0][0]; const sc = reg * (1 + pri[i]); if (!best || sc > best[0]) best = [sc, i, op[0][1]]; }
      put(bs, best[1], best[2]); left.delete(best[1]);
    }
    const clone = x => x.map(b => ({o: b.o.slice(), w: b.w, d: b.d}));
    const sum = x => x.reduce((s, b) => s + b.d, 0);
    let bestB = clone(bs), bestF = sum(bs), noImp = 0;
    const iters = cfg.rbrsIter;
    for (let it = 1; it <= iters && noImp < 10; it++) {
      // shift
      for (let t = 0; t < 30 && bs.length > 1; t++) {
        const s = R.int(0, bs.length - 1); if (!bs[s].o.length) continue;
        const oi = R.int(0, bs[s].o.length - 1), i = bs[s].o[oi];
        const src = bs[s].o.filter(x => x !== i), sd = src.length ? RS.cost(locsOf(orders, src)) : 0;
        let bg = 1e-9, bk = -1, bdd = 0;
        bs.forEach((b, k) => { if (k === s || b.w + orders[i].w > Q) return; const dd = RS.cost(locsOf(orders, b.o.concat(i))); const g = bs[s].d + b.d - sd - dd; if (g > bg) { bg = g; bk = k; bdd = dd; } });
        if (bk >= 0) { bs[s].o = src; bs[s].w -= orders[i].w; bs[s].d = sd; bs[bk].o.push(i); bs[bk].w += orders[i].w; bs[bk].d = bdd; }
      }
      bs = bs.filter(b => b.o.length);
      // swap
      for (let t = 0; t < 30 && bs.length > 1; t++) {
        const a = R.int(0, bs.length - 1); let c = R.int(0, bs.length - 2); if (c >= a) c++;
        const i = R.pick(bs[a].o), j = R.pick(bs[c].o);
        const wa = bs[a].w - orders[i].w + orders[j].w, wc = bs[c].w - orders[j].w + orders[i].w;
        if (wa > Q || wc > Q) continue;
        const na = bs[a].o.filter(x => x !== i).concat(j), nc = bs[c].o.filter(x => x !== j).concat(i);
        const da = RS.cost(locsOf(orders, na)), dc = RS.cost(locsOf(orders, nc));
        if (da + dc < bs[a].d + bs[c].d - 1e-9) { Object.assign(bs[a], {o: na, w: wa, d: da}); Object.assign(bs[c], {o: nc, w: wc, d: dc}); }
      }
      // uyarlanır eleme (%20 → %10)
      if (v2 && bs.length >= 2) {
        const pct = .2 - .1 * it / iters;
        const mode = R.pick(['worst', 'related', 'random']);
        let freed;
        if (mode === 'worst') {
          const sc = b => .7 * b.d / b.o.length + .3 * (1 - b.w / Q);
          const kill = new Set(bs.slice().sort((x, y) => sc(y) - sc(x)).slice(0, Math.max(1, Math.floor(bs.length * pct))));
          freed = [...kill].flatMap(b => b.o);
          bs = bs.filter(b => !kill.has(b));
        } else {
          const all = bs.flatMap(b => b.o), q = Math.min(all.length, Math.max(2, Math.round(pct * all.length)));
          if (mode === 'related') {
            const s0 = xy[R.pick(all)];
            all.sort((a, b) => (Math.abs(xy[a][0] - s0[0]) + Math.abs(xy[a][1] - s0[1])) - (Math.abs(xy[b][0] - s0[0]) + Math.abs(xy[b][1] - s0[1])));
            freed = all.slice(0, q);
          } else freed = R.shuffle(all).slice(0, q);
          const out = new Set(freed);
          bs.forEach(b => { const rest = b.o.filter(i => !out.has(i)); if (rest.length !== b.o.length) { b.o = rest; b.w = rest.reduce((s, i) => s + orders[i].w, 0); b.d = rest.length ? cost(b) : 0; } });
          bs = bs.filter(b => b.o.length);
        }
        // regret-2, öncelik ağırlıklı
        const todo = new Set(freed);
        while (todo.size) {
          let best = null;
          for (const i of todo) { const op = insertOpts(i, bs); const reg = op.length > 1 ? op[1][0] - op[0][0] : Infinity; const sc = reg * (1 + pri[i]); if (!best || sc > best[0]) best = [sc, i, op[0][1]]; }
          put(bs, best[1], best[2]); todo.delete(best[1]);
        }
      } else if (!v2 && bs.length > 2) {
        const pct = .2 - .1 * it / iters;
        const sc = b => .7 * b.d / b.o.length + .3 * (1 - b.w / Q);
        const order = bs.slice().sort((x, y) => sc(y) - sc(x));
        const kill = new Set(order.slice(0, Math.max(1, Math.floor(bs.length * pct))));
        const freed = [...kill].flatMap(b => b.o).sort((x, y) => pri[y] - pri[x]);
        bs = bs.filter(b => !kill.has(b));
        freed.forEach(i => { const op = insertOpts(i, bs); put(bs, i, op[0][1]); });
      }
      const f = sum(bs);
      if (f < bestF - 1e-9) { bestF = f; bestB = clone(bs); noImp = 0; } else noImp++;
      if (it % 5 === 0) progress(it / iters);
    }
    // son rötuş: en iyi tek taşıma, iyileşme kalmayana kadar (en fazla 5 tur)
    bs = clone(bestB);
    for (let pass = 0; pass < 5; pass++) {
      let best = null;
      bs.forEach((s, si) => s.o.forEach(i => {
        const src = s.o.filter(x => x !== i), sd = src.length ? RS.cost(locsOf(orders, src)) : 0;
        bs.forEach((b, k) => { if (k === si || b.w + orders[i].w > Q) return; const dd = RS.cost(locsOf(orders, b.o.concat(i))); const g = s.d + b.d - sd - dd; if (g > 1e-9 && (!best || g > best[0])) best = [g, si, i, k, sd, dd]; });
      }));
      if (!best) break;
      const [, si, i, k, sd, dd] = best;
      bs[si].o = bs[si].o.filter(x => x !== i); bs[si].w -= orders[i].w; bs[si].d = sd;
      bs[k].o.push(i); bs[k].w += orders[i].w; bs[k].d = dd;
      bs = bs.filter(b => b.o.length);
    }
    return (sum(bs) < bestF ? bs : bestB).map(b => b.o);
  }

  // ════════════════════════════════════════════════════════════════════
  // ALNS (hafif): 3 yıkma, 2 kurma, uyarlanır ağırlık, benzetimli tavlama
  // ════════════════════════════════════════════════════════════════════
  function alns(orders, Q, RS, R, cfg, progress) {
    const n = orders.length;
    const td = o => o.length ? RS.cost(locsOf(orders, o)) : 0;
    const mk = bs => ({bs: bs.map(b => b.slice()), w: bs.map(b => b.reduce((s, i) => s + orders[i].w, 0)), d: bs.map(td)});
    const f = S => S.d.reduce((a, b) => a + b, 0);
    const copy = S => ({bs: S.bs.map(b => b.slice()), w: S.w.slice(), d: S.d.slice()});
    function opts(S, i) {
      const o = []; S.bs.forEach((b, k) => { if (S.w[k] + orders[i].w <= Q) o.push([td(b.concat(i)) - S.d[k], k]); });
      o.push([td([i]), -1]); return o.sort((a, b) => a[0] - b[0]);
    }
    function ins(S, i, k) { if (k === -1) { S.bs.push([i]); S.w.push(orders[i].w); S.d.push(td([i])); } else { S.bs[k].push(i); S.w[k] += orders[i].w; S.d[k] = td(S.bs[k]); } }
    function greedy(S, todo) { todo = todo.slice(); while (todo.length) { let b = null; for (const i of todo) { const o = opts(S, i)[0]; if (!b || o[0] < b[0]) b = [o[0], i, o[1]]; } ins(S, b[1], b[2]); todo.splice(todo.indexOf(b[1]), 1); } return S; }
    function regret(S, todo) { todo = todo.slice(); while (todo.length) { let b = null; for (const i of todo) { const o = opts(S, i); const r = o.length > 1 ? o[1][0] - o[0][0] : Infinity; if (!b || r > b[0] || (r === b[0] && -o[0][0] > -b[3])) b = [r, i, o[0][1], o[0][0]]; } ins(S, b[1], b[2]); todo.splice(todo.indexOf(b[1]), 1); } return S; }
    function remove(S, ids) {
      const set = new Set(ids);
      S.bs.forEach((b, k) => { const nb = b.filter(i => !set.has(i)); if (nb.length !== b.length) { S.bs[k] = nb; S.w[k] = nb.reduce((s, i) => s + orders[i].w, 0); S.d[k] = td(nb); } });
      const keep = S.bs.map((b, k) => b.length ? k : -1).filter(k => k >= 0);
      S.bs = keep.map(k => S.bs[k]); S.w = keep.map(k => S.w[k]); S.d = keep.map(k => S.d[k]);
    }
    const biased = (len, p) => Math.min(len - 1, Math.floor(R.next() ** p * len));
    function destroy(op, S, q) {
      const pairs = S.bs.flatMap((b, k) => b.map(i => [k, i]));
      let ch = [];
      if (op === 'random') ch = R.shuffle(pairs.slice()).slice(0, q).map(p => p[1]);
      else if (op === 'worst') {
        const sc = pairs.map(([k, i]) => [S.d[k] - td(S.bs[k].filter(x => x !== i)), i]).sort((a, b) => b[0] - a[0]).map(x => x[1]);
        for (let t = 0; t < q && sc.length; t++) ch.push(sc.splice(biased(sc.length, 3), 1)[0]);
      } else {
        const cand = pairs.map(p => p[1]); ch.push(cand.splice(R.int(0, cand.length - 1), 1)[0]);
        while (ch.length < q && cand.length) {
          const R2 = ch.flatMap(i => orders[i].locs);
          const rel = i => orders[i].locs.reduce((s, l) => s + Math.min(...R2.map(r => RS.cost([l, r]) / 2)), 0) / orders[i].locs.length;
          const ranked = cand.slice().sort((a, b) => rel(a) - rel(b));
          const pick = ranked[biased(ranked.length, 6)]; cand.splice(cand.indexOf(pick), 1); ch.push(pick);
        }
      }
      remove(S, ch); return ch;
    }
    let cur = regret(mk([]), [...Array(n).keys()]), best = copy(cur);
    let T = -(0.05 * f(cur)) / Math.log(0.5);
    const D = ['random', 'worst', 'related'], Rp = ['greedy', 'regret'];
    const wd = {random: 1, worst: 1, related: 1}, wr = {greedy: 1, regret: 1};
    let pd = {}, nd = {}, pr = {}, nr = {};
    const reset = () => { pd = {random: 0, worst: 0, related: 0}; nd = {...pd}; pr = {greedy: 0, regret: 0}; nr = {...pr}; }; reset();
    const roul = w => { const tot = Object.values(w).reduce((a, b) => a + b, 0); let x = R.next() * tot; for (const [k, v] of Object.entries(w)) { x -= v; if (x < 0) return k; } return Object.keys(w)[0]; };
    const qmin = Math.max(2, Math.ceil(.05 * n)), qmax = Math.min(12, Math.max(qmin, Math.ceil(.15 * n)));
    const iters = cfg.alnsIter;
    for (let it = 1; it <= iters; it++) {
      const d = roul(wd), r = roul(wr), q = R.int(qmin, Math.min(qmax, n));
      const S = copy(cur); const rem = destroy(d, S, q);
      (r === 'greedy' ? greedy : regret)(S, rem);
      const fs = f(S), fc = f(cur); let sc = 0;
      if (fs < f(best) - 1e-9) { best = copy(S); cur = S; sc = 33; }
      else if (fs < fc - 1e-9) { cur = S; sc = 20; }
      else if (T > 0 && R.next() < Math.exp(-(fs - fc) / T)) { cur = S; sc = 8; }
      pd[d] += sc; nd[d]++; pr[r] += sc; nr[r]++; T *= 0.9975;
      if (it % 40 === 0) {
        for (const k of D) if (nd[k]) wd[k] = .85 * wd[k] + .15 * pd[k] / nd[k];
        for (const k of Rp) if (nr[k]) wr[k] = .85 * wr[k] + .15 * pr[k] / nr[k];
        reset();
      }
      if (it % 10 === 0) progress(it / iters);
    }
    return best.bs;
  }

  // ════════════════════════════════════════════════════════════════════
  function solveAll(input, onProgress) {
    const L = buildLayout(input.layout);
    const orders = input.orders, Q = input.capacity;
    const cfg = Object.assign({depsoIter: 120, rbrsIter: 40, alnsIter: 250}, input.cfg || {});
    const out = [];
    const xy = orders.map(o => [o.locs.reduce((s, l) => s + L.locs[l].x, 0) / o.locs.length, o.locs.reduce((s, l) => s + L.locs[l].y, 0) / o.locs.length]);
    const rbrsae2 = (o, q, rs, r, c, p) => rbrsae(o, q, rs, r, c, p, true, xy);
    const algos = [['DEPSO', depso], ['RBRS-AE', rbrsae], ['RBRS-AE2', rbrsae2], ['ALNS', alns]];
    for (const [name, fn] of algos) {
      const RS = routeService(L);
      const t0 = Date.now();
      const batches = fn(orders, Q, RS, rng(input.seed + name.length), cfg, x => onProgress && onProgress(name, x));
      const ms = Date.now() - t0;
      onProgress && onProgress(name, 1);
      let tot = 0;
      const bOut = batches.filter(b => b.length).map(b => {
        const r = RS.route(locsOf(orders, b)); tot += r.dist;
        const path = [[L.door.x, L.door.y]], stops = [];
        for (let i = 0; i + 1 < r.tour.length; i++) {
          path.push(...L.walk(r.tour[i], r.tour[i + 1]));
          const id = r.tour[i + 1]; if (id !== -1) { const l = L.locs[id]; stops.push([l.x, l.y, l.side]); }
        }
        return {orders: b.length, dist: Math.round(r.dist * 10) / 10, path, stops};
      });
      out.push({name, total: Math.round(tot * 10) / 10, runtime_ms: ms, batches: bOut});
    }
    return {geometry: L.geometry, algorithms: out};
  }

  return {buildLayout, makeOrders, manualOrder, solveAll, rng, itemWeight};
}
if (typeof window !== 'undefined') window.rafSolverLib = rafSolverLib;
