(function () {
'use strict';
const C = window.CATALOG || {records: [], reference: [], dynamic: [], races: [], dimensions: [], algorithms: [], comparisons: []};
const ALGOS = C.algorithms && C.algorithms.length ? C.algorithms : ['DEPSO', 'RBRS-AE', 'ALNS'];
const SERIES = {'DEPSO': '--s1', 'RBRS-AE': '--s2', 'ALNS': '--s3', 'RBRS-AE2': '--s4'};
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const nf = (v, d = 0) => Number(v).toLocaleString('tr-TR', {minimumFractionDigits: d, maximumFractionDigits: d});
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const DIM = Object.fromEntries((C.dimensions || []).map(d => [d.key, d]));
function dimValueLabel(key, v) {
  const d = DIM[key];
  if (d && d.names && d.names[String(v)]) return d.names[String(v)];
  if (key === 'fill') return '%' + v;
  if (key === 'locations') return nf(v) + ' lok.';
  if (key === 'k') return nf(v) + ' sipariş';
  return String(v);
}
const redrawers = [];
function onTheme(fn) { redrawers.push(fn); }
window.matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', () => redrawers.forEach(f => f()));
new MutationObserver(() => redrawers.forEach(f => f())).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});

// ════════════════════════════════════════════════════════════════════
// DEPO ÇİZİMİ
// ════════════════════════════════════════════════════════════════════
const PAD = 1.2;
function view(geom) {
  const x0 = -PAD, x1 = geom.w + PAD, y0 = -PAD, y1 = geom.h + PAD;
  return {x0, x1, y0, y1, aspect: (x1 - x0) / (y1 - y0)};
}
function fitCanvas(canvas, geom, maxH) {
  const v = view(geom), dpr = window.devicePixelRatio || 1;
  let w = canvas.clientWidth || canvas.parentElement.clientWidth;
  let h = Math.round(w / v.aspect);
  if (maxH && h > maxH) { h = maxH; }
  canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
  canvas.style.height = h + 'px';
  const s = Math.min(canvas.width / (v.x1 - v.x0), canvas.height / (v.y1 - v.y0));
  const ox = (canvas.width - s * (v.x1 - v.x0)) / 2, oy = (canvas.height - s * (v.y1 - v.y0)) / 2;
  return {s, P: (x, y) => [ox + (x - v.x0) * s, oy + (v.y1 - y) * s]};
}
function drawFloor(ctx, geom, T, rackColor) {
  const {s, P} = T;
  ctx.fillStyle = css('--floor'); ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
  ctx.fillStyle = css('--cross'); ctx.globalAlpha = 0.4;
  if (geom.bands) geom.bands.forEach(r => { const [px, py] = P(r[0], r[1] + r[3]); ctx.fillRect(px, py, r[2] * s, r[3] * s); });
  else geom.cross.forEach((x, i) => {
    const w = i === 0 ? 0.6 : geom.crossW;
    const [px, py] = P(i === 0 ? x - 0.6 : x, geom.h);
    ctx.fillRect(px, py, w * s, geom.h * s);
  });
  ctx.globalAlpha = 1;
  geom.racks.forEach(r => {
    const [px, py] = P(r[0], r[1] + r[3]);
    ctx.fillStyle = rackColor ? rackColor(r) : css('--rack');
    ctx.fillRect(px, py, r[2] * s, r[3] * s);
  });
  const [dx, dy] = P(geom.depot[0], geom.depot[1]);
  const z = Math.max(5, s * 1.1);
  ctx.fillStyle = css('--ink');
  ctx.beginPath(); ctx.moveTo(dx, dy - z); ctx.lineTo(dx - z * 0.85, dy + z * 0.45); ctx.lineTo(dx + z * 0.85, dy + z * 0.45); ctx.closePath(); ctx.fill();
}
function stopCell(T, st) {
  const yc = st[1] + (st[2] === 0 ? -1 : 1);
  const [x, y] = T.P(st[0] - 0.5, yc + 0.5);
  return [x, y, T.s];
}

// ════════════════════════════════════════════════════════════════════
// PROBLEM ÇİZİMLERİ
// ════════════════════════════════════════════════════════════════════
function drawIllustrations() {
  const race = C.races[0];
  if (!race) return;
  const g = race.geometry;
  const sol = race.algorithms[race.algorithms.length - 1];
  // 1: kapıya uzaklığa göre bölgeler (ilk %5 A, sonraki %15 B)
  const c1 = document.getElementById('ill1');
  const T1 = fitCanvas(c1, g), x1 = c1.getContext('2d');
  const cells = [];
  g.racks.forEach(r => { for (let x = r[0]; x < r[0] + r[2]; x += 1) cells.push([x, r[1], 1, r[3]]); });
  const dist = c => Math.abs(g.depot[0] - (c[0] + .5)) + Math.abs(g.depot[1] - (c[1] + .5));
  const sorted = cells.map(dist).sort((a, b) => a - b);
  const tA = sorted[Math.floor(sorted.length * 0.05)], tB = sorted[Math.floor(sorted.length * 0.20)];
  drawFloor(x1, g, T1, () => 'transparent');
  cells.forEach(c => {
    const d = dist(c);
    x1.fillStyle = css('--rack');
    x1.globalAlpha = d <= tA ? 1 : d <= tB ? 0.62 : 0.28;
    const [px, py] = T1.P(c[0], c[1] + c[3]); x1.fillRect(px, py, T1.s + .5, c[3] * T1.s);
  });
  x1.globalAlpha = 1;
  // 2: gruplar
  const c2 = document.getElementById('ill2');
  const T2 = fitCanvas(c2, g), x2 = c2.getContext('2d');
  drawFloor(x2, g, T2);
  const groupCols = [css('--accent'), css('--ink'), css('--muted'), css('--page')];
  sol.batches.forEach((b, k) => b.stops.forEach(st => {
    const [x, y, s] = stopCell(T2, st);
    x2.fillStyle = groupCols[k % groupCols.length]; x2.fillRect(x, y, s, s);
    x2.strokeStyle = css('--panel'); x2.lineWidth = 1; x2.strokeRect(x, y, s, s);
  }));
  // 3: bir turun rotası
  const c3 = document.getElementById('ill3');
  const T3 = fitCanvas(c3, g), x3 = c3.getContext('2d');
  drawFloor(x3, g, T3);
  const b0 = sol.batches[0];
  x3.strokeStyle = css('--ink'); x3.lineWidth = Math.max(1.5, T3.s * .28); x3.lineJoin = 'round';
  x3.beginPath(); b0.path.forEach((p, i) => { const [x, y] = T3.P(p[0], p[1]); i ? x3.lineTo(x, y) : x3.moveTo(x, y); }); x3.stroke();
  b0.stops.forEach(st => { const [x, y, s] = stopCell(T3, st); x3.fillStyle = css('--accent'); x3.fillRect(x, y, s, s); });
}

// ════════════════════════════════════════════════════════════════════
// YARIŞ
// ════════════════════════════════════════════════════════════════════
/**
 * Yarış oynatıcısı. data: {geometry, algorithms:[{name,total,runtime,batches:[{path,stops}]}]}
 * el: {lanes, clock, play, reset, speed, speedOut}
 */
function makeRacePlayer(el) {
  const st = {t: 0, playing: !reduceMotion, speed: +(el.speed?.value || 3), last: null, lanes: [], geom: null};
  function prep(r) {
    return r.algorithms.map(a => {
      let offset = 0;
      const tours = a.batches.map(b => {
        const cum = [0];
        for (let i = 1; i < b.path.length; i++)
          cum.push(cum[i - 1] + Math.abs(b.path[i][0] - b.path[i - 1][0]) + Math.abs(b.path[i][1] - b.path[i - 1][1]));
        const stopAt = []; let s = 0;
        for (let i = 0; i < b.path.length && s < b.stops.length; i++)
          while (s < b.stops.length && Math.abs(b.path[i][0] - b.stops[s][0]) < 1e-6 && Math.abs(b.path[i][1] - b.stops[s][1]) < 1e-6) { stopAt.push(cum[i]); s++; }
        while (stopAt.length < b.stops.length) stopAt.push(cum[cum.length - 1]);
        const t = {b, cum, len: cum[cum.length - 1], start: offset, stopAt};
        offset += t.len; return t;
      });
      return {a, tours, total: offset};
    });
  }
  const maxT = () => Math.max(0, ...st.lanes.map(L => L.p.total));
  function load(r) {
    el.lanes.innerHTML = '';
    st.geom = r.geometry;
    st.lanes = prep(r).map(p => {
      const lane = document.createElement('div');
      lane.className = 'lane'; lane.style.setProperty('--c', `var(${SERIES[p.a.name] || '--ink'})`);
      lane.innerHTML = `<div class="lane-head"><div class="tag"><span class="dot"></span>${esc(p.a.name)}</div>
        <div class="stats mono"><div><span>mesafe </span><b data-k="d">0</b> LU</div><div><span>tur </span><b data-k="t">1/${p.tours.length}</b></div><div><span>ürün </span><b data-k="p">0</b></div></div></div>
        <canvas role="img" aria-label="${esc(p.a.name)} toplayıcısının rotası"></canvas>`;
      el.lanes.appendChild(lane);
      return {p, el: lane, canvas: lane.querySelector('canvas'), q: k => lane.querySelector(`[data-k="${k}"]`), done: false};
    });
    st.t = 0; st.last = null; st.playing = !reduceMotion;
    size(); draw(); setPlay();
  }
  function size() { st.lanes.forEach(L => { L.T = fitCanvas(L.canvas, st.geom, 300); }); }
  function pointAt(tr, d) {
    const {b, cum} = tr;
    if (d <= 0) return b.path[0];
    if (d >= tr.len) return b.path[b.path.length - 1];
    let i = 1; while (cum[i] < d) i++;
    const f = (d - cum[i - 1]) / Math.max(1e-9, cum[i] - cum[i - 1]);
    const a = b.path[i - 1], c = b.path[i];
    return [a[0] + (c[0] - a[0]) * f, a[1] + (c[1] - a[1]) * f];
  }
  function drawLane(L) {
    const ctx = L.canvas.getContext('2d'), T = L.T, P = L.p;
    const col = css(SERIES[P.a.name] || '--ink'), muted = css('--muted');
    drawFloor(ctx, st.geom, T);
    const local = Math.min(st.t, P.total);
    let cur = P.tours.findIndex(tr => local < tr.start + tr.len);
    if (cur < 0) cur = P.tours.length - 1;
    let picked = 0;
    P.tours.forEach((tr, k) => {
      const d = local - tr.start, isCur = k === cur;
      ctx.lineJoin = 'round'; ctx.lineCap = 'round';
      ctx.strokeStyle = col; ctx.globalAlpha = isCur ? .22 : .1; ctx.lineWidth = Math.max(1, T.s * .18);
      ctx.beginPath(); tr.b.path.forEach((p, i) => { const [x, y] = T.P(p[0], p[1]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.stroke();
      if (d > 0) {
        ctx.globalAlpha = isCur ? .95 : .35; ctx.lineWidth = Math.max(1.5, T.s * (isCur ? .32 : .2));
        ctx.beginPath(); const [x0, y0] = T.P(tr.b.path[0][0], tr.b.path[0][1]); ctx.moveTo(x0, y0);
        for (let i = 1; i < tr.b.path.length && tr.cum[i - 1] < d; i++) {
          const p = tr.cum[i] <= d ? tr.b.path[i] : pointAt(tr, d); const [x, y] = T.P(p[0], p[1]); ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      if (k <= cur) tr.b.stops.forEach((s, j) => {
        const got = d >= tr.stopAt[j]; if (got) picked++;
        const [x, y, w] = stopCell(T, s);
        if (got) { ctx.fillStyle = isCur ? col : muted; ctx.globalAlpha = isCur ? 1 : .5; ctx.fillRect(x, y, w, w); ctx.globalAlpha = 1; }
        else if (isCur) { ctx.strokeStyle = col; ctx.lineWidth = Math.max(1, w * .14); ctx.strokeRect(x + 1, y + 1, w - 2, w - 2); }
      });
    });
    const tr = P.tours[cur];
    if (tr) {
      const [px, py] = T.P(...pointAt(tr, local - tr.start));
      ctx.fillStyle = col; ctx.strokeStyle = css('--panel'); ctx.lineWidth = Math.max(2, T.s * .2);
      ctx.beginPath(); ctx.arc(px, py, Math.max(5, T.s * .8), 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    }
    L.q('d').textContent = nf(local); L.q('t').textContent = `${Math.min(cur + 1, P.tours.length)}/${P.tours.length}`; L.q('p').textContent = picked;
    if (st.t >= P.total && !L.done) {
      L.done = true;
      const rt = P.a.runtime_ms != null ? `plan ${nf(P.a.runtime_ms)} ms` : `plan ${nf(P.a.runtime, 1)} sn`;
      L.el.querySelector('.lane-head').insertAdjacentHTML('beforeend', `<span class="done">bitti · ${nf(P.total)} LU · ${rt}</span>`);
    }
  }
  function draw() {
    if (!st.geom) return;
    st.lanes.forEach(drawLane);
    if (el.clock) el.clock.textContent = `${nf(Math.min(st.t, maxT()))} / ${nf(maxT())} LU`;
  }
  function setPlay() { if (el.play) el.play.textContent = st.playing ? 'Durdur' : (st.t >= maxT() ? 'Tekrar' : 'Oynat'); }
  function frame(ts) {
    if (st.playing && st.lanes.length) {
      if (st.last != null) st.t += (ts - st.last) / 1000 * 28 * st.speed;
      st.last = ts;
      if (st.t >= maxT()) { st.t = maxT(); st.playing = false; setPlay(); }
      draw();
    } else st.last = null;
    requestAnimationFrame(frame);
  }
  el.play?.addEventListener('click', () => {
    if (st.t >= maxT()) { st.lanes.forEach(L => { L.done = false; L.el.querySelectorAll('.done').forEach(n => n.remove()); }); st.t = 0; }
    st.playing = !st.playing; setPlay();
  });
  el.speed?.addEventListener('input', () => { st.speed = +el.speed.value; if (el.speedOut) el.speedOut.textContent = nf(st.speed, st.speed % 1 ? 1 : 0) + '×'; });
  requestAnimationFrame(frame);
  onTheme(draw);
  let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { if (st.geom) { size(); draw(); } }, 120); });
  return {load, restart: () => { st.lanes.forEach(L => { L.done = false; L.el.querySelectorAll('.done').forEach(n => n.remove()); }); st.t = 0; st.playing = !reduceMotion; setPlay(); }};
}
function raceTitle(r) {
  const d = r.dims;
  return `${dimValueLabel('locations', d.locations)} · ${dimValueLabel('blocks', d.blocks)} · doluluk %${d.fill} · ${nf(d.k)} sipariş`;
}
function initRace() {
  const sel = document.getElementById('raceSel');
  if (!C.races.length) { document.getElementById('lanes').innerHTML = '<div class="empty">Yarış verisi yok.</div>'; return; }
  const player = makeRacePlayer({lanes: document.getElementById('lanes'), clock: document.getElementById('clock'),
    play: document.getElementById('playBtn'), speed: document.getElementById('speed'), speedOut: document.getElementById('speedOut')});
  C.races.forEach((r, i) => sel.insertAdjacentHTML('beforeend', `<option value="${i}">${esc(raceTitle(r))}</option>`));
  sel.addEventListener('change', () => player.load(C.races[+sel.value]));
  document.getElementById('resetBtn').addEventListener('click', () => player.load(C.races[+sel.value || 0]));
  player.load(C.races[0]);
}

// ════════════════════════════════════════════════════════════════════
// SVG GRAFİK YARDIMCILARI
// ════════════════════════════════════════════════════════════════════
function niceMax(v) {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v))), m = v / p;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
}
function ticks(lo, hi, n = 4) {
  const step = niceMax((hi - lo) / n);
  const out = []; for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}
/** groups: [{label, values:{series: number}, n}] ; series: [{key,label,color}] */
function groupedBars(box, groups, series, opt) {
  box.innerHTML = '';
  if (!groups.length) { box.innerHTML = '<div class="empty">Seçili filtrelerle eşleşen deney yok.</div>'; return; }
  const legend = document.createElement('div'); legend.className = 'chart-legend';
  legend.innerHTML = series.map(s => `<span><span class="dot" style="--c:${s.color}"></span>${esc(s.label)}</span>`).join('');
  box.appendChild(legend);
  const W = 900, H = 320, m = {l: 56, r: 12, t: 12, b: 46};
  const vals = groups.flatMap(g => series.map(s => g.values[s.key])).filter(v => v != null && isFinite(v));
  let lo = Math.min(0, ...vals), hi = Math.max(0, ...vals);
  hi = hi > 0 ? niceMax(hi * 1.08) : 0; lo = lo < 0 ? -niceMax(-lo * 1.08) : 0;
  if (hi === lo) hi = lo + 1;
  const y = v => m.t + (hi - v) / (hi - lo) * (H - m.t - m.b);
  const gw = (W - m.l - m.r) / groups.length, bw = Math.min(34, (gw * .72) / series.length);
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opt.aria || '')}">`;
  ticks(lo, hi).forEach(t => {
    svg += `<line x1="${m.l}" x2="${W - m.r}" y1="${y(t)}" y2="${y(t)}" stroke="var(--grid)" stroke-width="1"/>`;
    svg += `<text x="${m.l - 8}" y="${y(t) + 4}" text-anchor="end" font-size="12" fill="var(--muted)" font-family="IBM Plex Mono,monospace">${esc(opt.fmt(t))}</text>`;
  });
  svg += `<line x1="${m.l}" x2="${W - m.r}" y1="${y(0)}" y2="${y(0)}" stroke="var(--ink-2)" stroke-width="1"/>`;
  groups.forEach((g, gi) => {
    const cx = m.l + gw * gi + gw / 2, x0 = cx - bw * series.length / 2;
    series.forEach((s, si) => {
      const v = g.values[s.key]; if (v == null || !isFinite(v)) return;
      const x = x0 + si * bw + 1, w = bw - 2, y0 = y(0), y1 = y(v);
      const top = Math.min(y0, y1), h = Math.max(1, Math.abs(y1 - y0));
      const r = Math.min(4, w / 2, h);
      const path = v >= 0
        ? `M${x},${y0}V${top + r}Q${x},${top} ${x + r},${top}H${x + w - r}Q${x + w},${top} ${x + w},${top + r}V${y0}Z`
        : `M${x},${y0}V${top + h - r}Q${x},${top + h} ${x + r},${top + h}H${x + w - r}Q${x + w},${top + h} ${x + w},${top + h - r}V${y0}Z`;
      svg += `<path d="${path}" fill="${s.color}" data-tip="${esc(`${g.label} · ${s.label}: ${opt.fmt(v)}${g.n ? ` · ${g.n} örnek` : ''}`)}"/>`;
      svg += `<rect x="${x0 + si * bw}" y="${m.t}" width="${bw}" height="${H - m.t - m.b}" fill="transparent" data-tip="${esc(`${g.label} · ${s.label}: ${opt.fmt(v)}${g.n ? ` · ${g.n} örnek` : ''}`)}"/>`;
    });
    svg += `<text x="${cx}" y="${H - m.b + 18}" text-anchor="middle" font-size="13" fill="var(--ink-2)">${esc(g.label)}</text>`;
    if (g.n) svg += `<text x="${cx}" y="${H - m.b + 34}" text-anchor="middle" font-size="11" fill="var(--muted)" font-family="IBM Plex Mono,monospace">n=${g.n}</text>`;
  });
  if (opt.yLabel) svg += `<text x="${m.l}" y="${m.t - 2}" font-size="12" fill="var(--muted)">${esc(opt.yLabel)}</text>`;
  svg += '</svg>';
  box.insertAdjacentHTML('beforeend', svg);
  attachTips(box);
}
function attachTips(box) {
  const tip = document.createElement('div'); tip.className = 'tip'; box.appendChild(tip);
  box.querySelectorAll('[data-tip]').forEach(el => {
    el.addEventListener('mousemove', e => {
      const r = box.getBoundingClientRect();
      tip.textContent = el.getAttribute('data-tip');
      tip.style.left = (e.clientX - r.left) + 'px'; tip.style.top = (e.clientY - r.top) + 'px';
      tip.classList.add('on');
    });
    el.addEventListener('mouseleave', () => tip.classList.remove('on'));
  });
}

// ════════════════════════════════════════════════════════════════════
// DENEY KATALOĞU
// ════════════════════════════════════════════════════════════════════
const METRICS = {
  gap: {label: 'En kısa plana göre fark (%)', fmt: v => '%' + nf(v, 1), better: 'low',
        of: r => { const best = Math.min(...ALGOS.map(a => r.res[a].td)); return Object.fromEntries(ALGOS.map(a => [a, (r.res[a].td - best) / best * 100])); }},
  sop: {label: 'Her siparişi ayrı toplamaya göre kazanç (%)', fmt: v => '%' + nf(v, 1), better: 'high',
        of: r => Object.fromEntries(ALGOS.map(a => [a, r.res.SOP ? (r.res.SOP.td - r.res[a].td) / r.res.SOP.td * 100 : NaN]))},
  rt: {label: 'Planı bulma süresi (sn)', fmt: v => nf(v, v < 10 ? 1 : 0) + ' sn', better: 'low',
       of: r => Object.fromEntries(ALGOS.map(a => [a, r.res[a].rt]))},
  wins: {label: 'En kısa planı bulma sayısı', fmt: v => nf(v), better: 'high', sum: true,
         of: r => { const best = Math.min(...ALGOS.map(a => r.res[a].td)); const w = ALGOS.filter(a => r.res[a].td <= best + 1e-6); return Object.fromEntries(ALGOS.map(a => [a, w.length === 1 && w[0] === a ? 1 : 0])); }},
};
const ex = {filters: {}, metric: 'gap', group: null};
function recDims() { return (C.dimensions || []).map(d => d.key).filter(k => C.records.some(r => r[k] != null)); }
function distinct(key, rows) { return [...new Set(rows.map(r => r[key]))].sort((a, b) => (typeof a === 'number' ? a - b : String(a).localeCompare(String(b)))); }
function filtered() { return C.records.filter(r => Object.entries(ex.filters).every(([k, set]) => set.has(r[k]))); }
function initExplorer() {
  const box = document.getElementById('filters');
  if (!C.records.length) {
    box.innerHTML = '<div class="empty">Henüz deney sonucu eklenmedi. <span class="mono">python run_generated.py</span> ve <span class="mono">python site_data.py</span> çalıştırıldığında burada görünür.</div>';
    return;
  }
  recDims().forEach(key => {
    const vals = distinct(key, C.records);
    ex.filters[key] = new Set(vals);
    const row = document.createElement('div'); row.className = 'frow';
    row.innerHTML = `<span class="flabel">${esc(DIM[key]?.label || key)}</span><div class="chips"></div>`;
    const chips = row.querySelector('.chips');
    vals.forEach(v => {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'chip';
      b.textContent = dimValueLabel(key, v); b.setAttribute('aria-pressed', 'true');
      if (vals.length < 2) b.disabled = true;
      b.addEventListener('click', () => {
        const set = ex.filters[key];
        if (set.has(v)) { if (set.size > 1) set.delete(v); } else set.add(v);
        chips.querySelectorAll('.chip').forEach((c, i) => c.setAttribute('aria-pressed', set.has(vals[i]) ? 'true' : 'false'));
        renderExplorer();
      });
      chips.appendChild(b);
    });
    box.appendChild(row);
  });
  const ms = document.getElementById('metricSel');
  Object.entries(METRICS).forEach(([k, m]) => ms.insertAdjacentHTML('beforeend', `<option value="${k}">${esc(m.label)}</option>`));
  ms.addEventListener('change', () => { ex.metric = ms.value; renderExplorer(); });
  document.getElementById('groupSel').addEventListener('change', e => { ex.group = e.target.value; renderExplorer(); });
  renderExplorer();
  onTheme(renderExplorer);
}
function renderExplorer() {
  const rows = filtered();
  const gs = document.getElementById('groupSel');
  const groupable = recDims().filter(k => distinct(k, rows).length > 1);
  const opts = ['_all', ...groupable];
  if (!ex.group || !opts.includes(ex.group)) ex.group = groupable.includes('locations') ? 'locations' : (groupable[0] || '_all');
  gs.innerHTML = opts.map(k => `<option value="${k}" ${k === ex.group ? 'selected' : ''}>${k === '_all' ? 'Hepsi birlikte' : esc(DIM[k]?.label || k)}</option>`).join('');
  const M = METRICS[ex.metric];
  const buckets = new Map();
  rows.forEach(r => { const key = ex.group === '_all' ? 'Tüm seçili örnekler' : r[ex.group]; if (!buckets.has(key)) buckets.set(key, []); buckets.get(key).push(r); });
  const keys = [...buckets.keys()].sort((a, b) => (typeof a === 'number' ? a - b : 0));
  const groups = keys.map(k => {
    const list = buckets.get(k), acc = Object.fromEntries(ALGOS.map(a => [a, 0])), cnt = Object.fromEntries(ALGOS.map(a => [a, 0]));
    list.forEach(r => { const v = M.of(r); ALGOS.forEach(a => { if (isFinite(v[a])) { acc[a] += v[a]; cnt[a]++; } }); });
    const values = Object.fromEntries(ALGOS.map(a => [a, cnt[a] ? (M.sum ? acc[a] : acc[a] / cnt[a]) : null]));
    return {label: ex.group === '_all' ? k : dimValueLabel(ex.group, k), values, n: list.length};
  });
  const series = ALGOS.map(a => ({key: a, label: a, color: `var(${SERIES[a]})`}));
  groupedBars(document.getElementById('chartbox'), groups, series, {fmt: M.fmt, yLabel: M.label, aria: M.label});
  // başlık cümlesi
  const tot = Object.fromEntries(ALGOS.map(a => [a, 0])); let ties = 0;
  rows.forEach(r => { const best = Math.min(...ALGOS.map(a => r.res[a].td)); const w = ALGOS.filter(a => r.res[a].td <= best + 1e-6); if (w.length === 1) tot[w[0]]++; else ties++; });
  const leader = ALGOS.slice().sort((a, b) => tot[b] - tot[a])[0];
  const rtMean = a => rows.reduce((s, r) => s + r.res[a].rt, 0) / Math.max(1, rows.length);
  const fastest = ALGOS.slice().sort((a, b) => rtMean(a) - rtMean(b))[0];
  document.getElementById('headline').textContent = rows.length
    ? `Seçili ${nf(rows.length)} örneğin ${nf(tot[leader])} tanesinde en kısa planı ${leader} buldu` +
      (ties ? `, ${nf(ties)} örnekte birden fazla algoritma aynı sonuca ulaştı` : '') +
      `. Planı en hızlı bulan ${fastest} (ortalama ${nf(rtMean(fastest), 1)} sn).`
    : '';
  // tablo
  const head = `<tr><th>${ex.group === '_all' ? '' : esc(DIM[ex.group]?.label || '')}</th><th>n</th>${ALGOS.map(a => `<th>${esc(a)}</th>`).join('')}</tr>`;
  const body = groups.map(g => `<tr><td>${esc(g.label)}</td><td class="num">${g.n}</td>${ALGOS.map(a => `<td class="num">${g.values[a] == null ? '–' : esc(M.fmt(g.values[a]))}</td>`).join('')}</tr>`).join('');
  document.getElementById('tablewrap').innerHTML = `<table><caption class="small muted" style="text-align:left;padding-bottom:6px">${esc(M.label)}</caption>${head}${body}</table>`;
}

// ════════════════════════════════════════════════════════════════════
// DİNAMİK YER ATAMASI
// ════════════════════════════════════════════════════════════════════
function dynName(d) {
  const ev = {full: ' · makaledeki ölçüm yöntemiyle', algo: ' · sabit gruplarla ölçüm'}[d.summary && d.summary.tdr_eval] || '';
  return dynBase(d) + ev;
}
function dynBase(d) {
  let m0 = d.problem.match(/^kubler_fig10_s(\d)/);
  if (m0) return `Kübler yöntemiyle üretilen veri, senaryo ${m0[1]} (${m0[1] === '1' ? 'yüksek' : 'düşük'} dinamik) · ${d.algorithm}`;
  if (d.problem.startsWith('kubler_s')) return `Eski Kübler veri seti, senaryo ${d.problem.slice(8)} · ${d.algorithm}`;
  const m = d.problem.match(/^S(\d+)_B(\d)_F(\d+)_(\w+?)_s(\d+)$/);
  if (m) return `Üretilmiş depo: ${nf(+m[1])} lok., ${dimValueLabel('blocks', m[2])}, %${m[3]}, ${dimValueLabel('dynamics', m[4])} dinamiklik · ${d.algorithm}`;
  return `${d.problem} · ${d.algorithm}`;
}
function initDynamic() {
  const sel = document.getElementById('dynSel'), box = document.getElementById('dynbox');
  if (!C.dynamic.length) { box.innerHTML = '<div class="empty">Henüz dinamik deney sonucu yok.</div>'; return; }
  C.dynamic.forEach((d, i) => sel.insertAdjacentHTML('beforeend', `<option value="${i}">${esc(dynName(d))}</option>`));
  const render = () => {
    const d = C.dynamic[+sel.value || 0];
    const groups = d.periods.map(p => ({label: `${p.period}. dönem`, values: {red: p.reduction_pct, eff: p.effort_pct}}));
    groupedBars(box, groups, [{key: 'red', label: 'Yürüme mesafesindeki azalma', color: 'var(--ink)'},
                              {key: 'eff', label: 'Taşıma emeği', color: 'var(--muted)'}],
                {fmt: v => '%' + nf(v, 2), yLabel: 'Taşıma yapılmayan depoya göre (%)', aria: 'Dönem başına azalma ve emek'});
    const s = d.summary;
    document.getElementById('dynHeadline').textContent =
      `Toplamda yürüme mesafesi %${nf(s.reduction_pct, 2)} azaldı, taşımaya %${nf(s.effort_pct, 2)} emek harcandı; net etki %${nf(s.net_pct, 2)}. ` +
      (s.td_static ? `9 dönemde taşımasız ${nf(s.td_static)} LU, taşımalı ${nf(s.td_dynamic)} LU yürüme. ` : '') +
      (d.paper ? `Makalede (DEPSO): azalma %${nf(d.paper.reduction_pct, 2)}, emek %${nf(d.paper.effort_pct, 2)}, net %${nf(d.paper.net_pct, 2)}. ` : '') +
      `Taşımalar dönem sonunda yapıldığı için kazanç bir sonraki dönemden itibaren görünür.`;
  };
  sel.addEventListener('change', render); render(); onTheme(render);
  initDynamicCompare();
}

// Kendi depolarımızda üç algoritmanın taşımalı mesafesi (aynı taşıma kararları)
function initDynamicCompare() {
  const algs = ['DEPSO', 'RBRS-AE', 'RBRS-AE2', 'ALNS'].filter(a => a !== 'RBRS-AE2' || C.dynamic.some(d => d.algorithm === a));
  const by = {};
  C.dynamic.forEach(d => {
    const m = d.problem.match(/^S(\d+)_B(\d)_F(\d+)_(\w+?)_s(\d+)$/);
    if (!m || !algs.includes(d.algorithm) || !d.summary.td_dynamic) return;
    (by[d.problem] = by[d.problem] || {m, res: {}}).res[d.algorithm] = d.summary;
  });
  const rows = Object.values(by).filter(g => algs.every(a => g.res[a])).sort((a, b) => (+a.m[1]) - (+b.m[1]));
  if (!rows.length) return;
  document.getElementById('dynCmp').hidden = false;
  const label = g => `${nf(+g.m[1])} lok.`;
  const render = () => {
    const groups = rows.map(g => {
      const best = Math.min(...algs.map(a => g.res[a].td_dynamic));
      const values = {};
      algs.forEach(a => { values[a] = 100 * (g.res[a].td_dynamic - best) / best; });
      return {label: label(g), values};
    });
    groupedBars(document.getElementById('dynCmpBox'), groups, algs.map(a => ({key: a, label: a, color: `var(${SERIES[a]})`})),
                {fmt: v => '%' + nf(v, 1), yLabel: 'Taşımalı toplam mesafe, en kısasına göre fark (%) · düşük daha iyi', aria: 'Taşımalı mesafe karşılaştırması'});
  };
  let html = '<table class="dyntable"><thead><tr><th>Depo</th>' +
    algs.map(a => `<th>${esc(a)}<br>net kazanç</th>`).join('') +
    algs.map(a => `<th>${esc(a)}<br>taşımalı mesafe (LU)</th>`).join('') + '</tr></thead><tbody>';
  rows.forEach(g => {
    const bestNet = Math.max(...algs.map(a => g.res[a].net_pct)), bestTd = Math.min(...algs.map(a => g.res[a].td_dynamic));
    html += `<tr><td>${label(g)}</td>` +
      algs.map(a => `<td class="${g.res[a].net_pct === bestNet ? 'best' : ''}">%${nf(g.res[a].net_pct, 1)}</td>`).join('') +
      algs.map(a => `<td class="${g.res[a].td_dynamic === bestTd ? 'best' : ''}">${nf(g.res[a].td_dynamic)}</td>`).join('') + '</tr>';
  });
  document.getElementById('dynCmpTable').innerHTML = html + '</tbody></table>';
  const tdWin = {}, netWin = {};
  rows.forEach(g => {
    const t = algs.reduce((x, y) => g.res[x].td_dynamic <= g.res[y].td_dynamic ? x : y);
    const n = algs.reduce((x, y) => g.res[x].net_pct >= g.res[y].net_pct ? x : y);
    tdWin[t] = (tdWin[t] || 0) + 1; netWin[n] = (netWin[n] || 0) + 1;
  });
  const top = o => Object.entries(o).sort((a, b) => b[1] - a[1])[0];
  const [tA, tN] = top(tdWin), [nA, nN] = top(netWin);
  document.getElementById('dynCmpHeadline').textContent =
    `${rows.length} deponun ${tN} tanesinde taşımadan sonraki en kısa mesafeyi ${tA} buldu; en büyük yüzde kazanç ise ${nN} depoda ${nA} algoritmasında. ` +
    `Yer değişimi her algoritmanın planını iyileştiriyor, ama iyi bir toplama planının yerini tutmuyor.`;
  render(); onTheme(render);
}

// ════════════════════════════════════════════════════════════════════
// ADİL KARŞILAŞTIRMA (eşit süre, çok tohum)
// ════════════════════════════════════════════════════════════════════
const CMP_BY = {
  k: {label: 'Sipariş sayısı', fmt: v => `${v} sipariş`},
  n_maxol: {label: 'Siparişteki en fazla satır', fmt: v => `en çok ${v} satır`},
  size: {label: 'Depo boyutu', fmt: v => `${nf(+v)} lok.`},
  blocks: {label: 'Koridor yapısı', fmt: v => dimValueLabel('blocks', v)},
  fill: {label: 'Doluluk', fmt: v => `%${v}`},
};
function cmpName(c) {
  const src = c.kind === 'kubler' ? "Kübler'in 35 senaryosu" : 'Kendi ürettiğimiz depolar';
  return `${src} · ${nf(c.n)} örnek × ${c.seeds} tohum`;
}
function cmpBudget(c) {
  const p = c.protocol || {};
  if (p.time_per_order) return `sipariş başına ${nf(p.time_per_order, 2)} sn`;
  if (p.time_budget) return `örnek başına ${nf(p.time_budget, 0)} sn`;
  return 'iterasyon sınırıyla (süre eşit değil)';
}
function initComparison() {
  const sel = document.getElementById('cmpSel'), bySel = document.getElementById('cmpBy'), box = document.getElementById('cmpBox');
  const list = C.comparisons || [];
  if (!list.length) { box.innerHTML = '<div class="empty">Henüz eşit süreli karşılaştırma sonucu yok.</div>'; return; }
  list.forEach((c, i) => sel.insertAdjacentHTML('beforeend', `<option value="${i}">${esc(cmpName(c))}</option>`));
  const fillBy = c => {
    const keep = bySel.value;
    bySel.innerHTML = Object.keys(c.gap_by || {}).filter(k => CMP_BY[k])
      .map(k => `<option value="${k}">${esc(CMP_BY[k].label)}</option>`).join('');
    if ([...bySel.options].some(o => o.value === keep)) bySel.value = keep;
  };
  const render = () => {
    const c = list[+sel.value || 0];
    // en iyi algoritma payları
    const algs = ['DEPSO', 'RBRS-AE', 'RBRS-AE2', 'ALNS'].filter(a => a in c.wins), tot = c.n || 1;
    document.getElementById('cmpWinsLabel').innerHTML = `${nf(c.n)} örneğin kaçında en kısa yolu hangi algoritma buldu: ` +
      algs.map(a => `<span class="dot" style="--c:var(${SERIES[a]})"></span>${esc(a)} ${nf(c.wins[a] || 0)}`).join(' &nbsp; ');
    document.getElementById('cmpWins').innerHTML = algs.map(a => {
      const w = c.wins[a] || 0, pct = 100 * w / tot;
      const txt = pct >= 22 ? `${esc(a)} %${nf(pct, 0)}` : pct >= 8 ? `%${nf(pct, 0)}` : '';
      return pct > 0 ? `<span style="width:${pct}%;background:var(${SERIES[a]})" title="${esc(`${a}: ${w} örnek`)}">${txt}</span>` : '';
    }).join('');
    // ikili karşılaştırmalar
    document.getElementById('cmpPairs').innerHTML = c.pairs.map(p => {
      const better = p.diff_pct < 0, d = nf(Math.abs(p.diff_pct), 2);
      const sig = p.p != null && p.p < 0.05;
      const pTxt = p.p == null ? '' : p.p < 0.001 ? 'p < 0,001' : `p = ${nf(p.p, 3)}`;
      return `<li><b>${esc(p.a)} – ${esc(p.b)}:</b> ${esc(p.a)} ortalama <b>%${d} daha ${better ? 'kısa' : 'uzun'}</b> yol buldu; ` +
        `${nf(p.a_better + p.b_better)} örneğin ${nf(p.a_better)} tanesinde ${esc(p.a)}, ${nf(p.b_better)} tanesinde ${esc(p.b)} önde.` +
        `<span class="sig ${sig ? 'yes' : ''}">${sig ? 'fark anlamlı' : 'şans eseri olabilir'}${pTxt ? ' · ' + pTxt : ''}</span></li>`;
    }).join('');
    // kırılım
    const key = bySel.value, g = (c.gap_by || {})[key];
    if (g) {
      const groups = Object.keys(g).sort((a, b) => (+a) - (+b)).map(v => ({label: CMP_BY[key].fmt(v), values: g[v]}));
      groupedBars(box, groups, algs.map(a => ({key: a, label: a, color: `var(${SERIES[a]})`})),
                  {fmt: v => '%' + nf(v, 1), yLabel: 'Örnekteki en iyi sonuca göre ortalama fark (%) · düşük daha iyi', aria: 'Kırılıma göre algoritmalar'});
    } else box.innerHTML = '';
    const rt = c.runtime || {};
    document.getElementById('cmpHeadline').textContent =
      `Her algoritmaya ${cmpBudget(c)} süre verildi. ` +
      `"Anlamlı" etiketi, farkın bu kadar örnekte şansla ortaya çıkma olasılığının %5'in altında olduğunu söyler (Wilcoxon testi). ` +
      (c.protocol && (c.protocol.time_per_order || c.protocol.time_budget) ? '' :
        `Ortalama süreler: ${algs.map(a => `${a} ${nf(rt[a] || 0, 1)} sn`).join(', ')}.`);
  };
  sel.addEventListener('change', () => { fillBy(list[+sel.value || 0]); render(); });
  bySel.addEventListener('change', render);
  fillBy(list[0]); render(); onTheme(render);
}

// ════════════════════════════════════════════════════════════════════
// REFERANS DOĞRULAMA
// ════════════════════════════════════════════════════════════════════
function initReference() {
  const box = document.getElementById('refbox'), ref = (C.reference || []).filter(r => typeof r.paper === 'number' && r.ours.DEPSO != null);
  if (!ref.length) { box.innerHTML = '<div class="empty">Referans sonuçları yok.</div>'; return; }
  const render = () => {
    const W = 900, H = 340, m = {l: 60, r: 16, t: 14, b: 44};
    const xs = ref.map(r => -r.paper), ys = ref.map(r => -r.ours.DEPSO);
    const lo = Math.floor(Math.min(...xs, ...ys) / 5) * 5, hi = Math.ceil(Math.max(...xs, ...ys) / 5) * 5;
    const X = v => m.l + (v - lo) / (hi - lo) * (W - m.l - m.r), Y = v => m.t + (hi - v) / (hi - lo) * (H - m.t - m.b);
    let svg = `<div class="chart-legend"><span><span class="dot" style="--c:var(--s1)"></span>DEPSO, bir nokta = bir senaryo</span><span>Kesikli çizgi: makaleyle birebir aynı</span></div>`;
    svg += `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Makale ve bizim DEPSO sonuçlarımız">`;
    for (let v = lo; v <= hi; v += 5) {
      svg += `<line x1="${X(lo)}" x2="${X(hi)}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--grid)"/><text x="${m.l - 8}" y="${Y(v) + 4}" text-anchor="end" font-size="12" fill="var(--muted)" font-family="IBM Plex Mono,monospace">%${v}</text>`;
      svg += `<text x="${X(v)}" y="${H - m.b + 18}" text-anchor="middle" font-size="12" fill="var(--muted)" font-family="IBM Plex Mono,monospace">%${v}</text>`;
    }
    svg += `<line x1="${X(lo)}" y1="${Y(lo)}" x2="${X(hi)}" y2="${Y(hi)}" stroke="var(--ink-2)" stroke-dasharray="5 5"/>`;
    ref.forEach((r, i) => {
      const tip = `${r.scenario}: makale %${nf(-r.paper, 1)}, bizde %${nf(-r.ours.DEPSO, 1)}`;
      svg += `<circle cx="${X(xs[i])}" cy="${Y(ys[i])}" r="5" fill="var(--s1)" stroke="var(--panel)" stroke-width="2"/><circle cx="${X(xs[i])}" cy="${Y(ys[i])}" r="12" fill="transparent" data-tip="${esc(tip)}"/>`;
    });
    svg += `<text x="${(W + m.l) / 2}" y="${H - 6}" text-anchor="middle" font-size="12" fill="var(--muted)">Makalede raporlanan azalma</text>`;
    svg += `<text x="${m.l}" y="${m.t - 2}" font-size="12" fill="var(--muted)">Bizim ölçtüğümüz azalma</text></svg>`;
    box.innerHTML = svg; attachTips(box);
    const dev = ref.map(r => Math.abs(r.ours.DEPSO - r.paper));
    document.getElementById('refHeadline').textContent =
      `${ref.length} senaryonun ${dev.filter(d => d <= 5).length} tanesinde fark 5 puanın altında; ortalama mutlak fark ${nf(dev.reduce((a, b) => a + b, 0) / dev.length, 2)} puan. ` +
      `Bu karşılaştırma yalnızca başlangıç algoritmasının doğru kurulduğunu göstermek için yapıldı; asıl deneyler yukarıdaki üretilmiş depolarla yürütülüyor.`;
  };
  render(); onTheme(render);
}

// ════════════════════════════════════════════════════════════════════
function init() {
  drawIllustrations(); onTheme(drawIllustrations);
  initRace(); initExplorer(); initComparison(); initDynamic(); initReference();
  document.getElementById('stamp').textContent =
    `Veriler ${C.generated_at || '—'} tarihinde, kod sürümü ${C.git_commit || '—'} ile üretildi · ${nf(C.records.length)} deney örneği.`;
  let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(drawIllustrations, 120); });
}
window.RafArasi = {makeRacePlayer, fitCanvas, drawFloor, stopCell, css, nf, esc, groupedBars, SERIES, onTheme};
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
