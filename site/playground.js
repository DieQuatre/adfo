(function () {
'use strict';
const RA = window.RafArasi, lib = window.rafSolverLib && window.rafSolverLib();
if (!RA || !lib) return;
const {makeRacePlayer, fitCanvas, drawFloor, stopCell, css, nf, SERIES} = RA;
const $ = id => document.getElementById(id);

const state = {
  layout: {aisles: 8, blocks: 2, racks: 14, door: 'alt-sag'},
  mode: 'random', seed: 11, orders: [], manual: [], draft: new Set(),
  L: null, T: null, busy: false,
};

function segValue(el, v) { el.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', b.dataset.v === String(v) ? 'true' : 'false')); }
function bindRange(id, fmt, onChange) {
  const inp = $(id), out = $(id + 'Out');
  const show = () => { out.textContent = fmt ? fmt(+inp.value) : inp.value; };
  inp.addEventListener('input', () => { show(); onChange(+inp.value); });
  show();
}

function rebuild() {
  state.L = lib.buildLayout(state.layout);
  if (state.mode === 'random') makeRandom();
  else { const ok = new Set(state.L.locs.map(l => l.id)); state.manual = state.manual.map(o => ({...o, locs: o.locs.filter(l => ok.has(l))})).filter(o => o.locs.length); state.draft.clear(); }
  draw();
}
function makeRandom() {
  state.orders = lib.makeOrders(state.L, +$('pgOrders').value, +$('pgLines').value, $('pgPopular').checked, state.seed);
}
function currentOrders() {
  return state.mode === 'random' ? state.orders : state.manual.map((o, i) => ({...o, id: i}));
}

function draw() {
  const c = $('pgCanvas'), L = state.L;
  state.T = fitCanvas(c, L.geometry, 420);
  const ctx = c.getContext('2d');
  drawFloor(ctx, L.geometry, state.T);
  const count = new Map();
  currentOrders().forEach(o => o.locs.forEach(l => count.set(l, (count.get(l) || 0) + 1)));
  const ink = css('--ink'), accent = css('--accent');
  count.forEach((n, id) => {
    const l = L.locs[id]; const [x, y, s] = stopCell(state.T, [l.x, l.y, l.side]);
    ctx.fillStyle = ink; ctx.globalAlpha = Math.min(1, .45 + .15 * n); ctx.fillRect(x + 1, y + 1, s - 2, s - 2);
  });
  ctx.globalAlpha = 1;
  state.draft.forEach(id => {
    const l = L.locs[id]; const [x, y, s] = stopCell(state.T, [l.x, l.y, l.side]);
    ctx.fillStyle = accent; ctx.fillRect(x, y, s, s);
    ctx.strokeStyle = ink; ctx.lineWidth = 1.5; ctx.strokeRect(x + .5, y + .5, s - 1, s - 1);
  });
  const orders = currentOrders();
  const w = orders.reduce((s, o) => s + o.w, 0);
  $('pgInfo').textContent = `${nf(L.locs.length)} raf gözü · ${nf(orders.length)} sipariş · ${nf(count.size)} farklı ürün · toplam ağırlık ${nf(w, 1)}` +
    (state.mode === 'manual' ? ` · hazırlanan siparişte ${state.draft.size} ürün` : '') +
    (orders.length ? ` · en az ${Math.ceil(w / +$('pgCap').value)} tur gerekir` : '');
  $('pgRun').disabled = !orders.length || state.busy;
}

function pickLoc(ev) {
  const c = $('pgCanvas'), r = c.getBoundingClientRect();
  const px = (ev.clientX - r.left) * (c.width / r.width), py = (ev.clientY - r.top) * (c.height / r.height);
  let best = null, bd = Infinity;
  state.L.locs.forEach(l => {
    const [x, y, s] = stopCell(state.T, [l.x, l.y, l.side]);
    const dx = px - (x + s / 2), dy = py - (y + s / 2), d = dx * dx + dy * dy;
    if (d < bd) { bd = d; best = l; }
  });
  const [, , s] = stopCell(state.T, [0, 0, 0]);
  return bd <= (s * 1.2) ** 2 ? best : null;
}

let worker = null;
function getWorker() {
  if (worker !== null) return worker;
  try {
    const src = window.rafSolverLib.toString() +
      ';const lib=rafSolverLib();onmessage=e=>{const r=lib.solveAll(e.data,(a,x)=>postMessage({type:"p",a,x}));postMessage({type:"done",r});};';
    worker = new Worker(URL.createObjectURL(new Blob([src], {type: 'text/javascript'})));
  } catch (e) { worker = false; }
  return worker;
}

let player = null;
function run() {
  const orders = currentOrders();
  if (!orders.length || state.busy) return;
  state.busy = true; $('pgRun').disabled = true; $('pgRun').textContent = 'Hesaplanıyor…';
  const prog = $('pgProgress'); prog.hidden = false;
  prog.innerHTML = ['DEPSO', 'RBRS-AE', 'RBRS-AE2', 'ALNS'].map(a =>
    `<div class="pbar" style="--c:var(${SERIES[a]})"><span>${a}</span><span class="track"><span class="fill" data-a="${a}"></span></span><span class="mono" data-p="${a}">%0</span></div>`).join('');
  const input = {layout: state.layout, orders, capacity: +$('pgCap').value, seed: state.seed};
  const onP = (a, x) => {
    const f = prog.querySelector(`[data-a="${a}"]`), p = prog.querySelector(`[data-p="${a}"]`);
    if (f) f.style.width = Math.round(x * 100) + '%'; if (p) p.textContent = '%' + Math.round(x * 100);
  };
  const done = r => {
    state.busy = false; $('pgRun').textContent = 'Çöz ve yarıştır'; draw();
    showResult(r);
  };
  const w = getWorker();
  if (w) { w.onmessage = e => e.data.type === 'p' ? onP(e.data.a, e.data.x) : done(e.data.r); w.postMessage(input); }
  else setTimeout(() => done(lib.solveAll(input, onP)), 30);
}

function showResult(r) {
  $('pgResult').hidden = false;
  if (!player) player = makeRacePlayer({lanes: $('pgLanes'), clock: $('pgClock'), play: $('pgPlay'),
                                        speed: $('pgSpeed'), speedOut: $('pgSpeedOut')});
  player.load(r);
  $('pgReplay').onclick = () => player.load(r);
  const al = r.algorithms.slice().sort((a, b) => a.total - b.total);
  const best = al[0], worst = al[al.length - 1];
  const tie = al.filter(a => a.total === best.total).map(a => a.name);
  $('pgHeadline').textContent = (tie.length > 1 ? `${tie.join(' ve ')} aynı uzunlukta plan buldu (${nf(best.total)} LU)` :
    `En kısa planı ${best.name} buldu: ${nf(best.total)} LU`) +
    (worst.total > best.total ? `, en uzundan %${nf((worst.total - best.total) / worst.total * 100, 1)} daha kısa.` : '.') +
    ` Planı bulma süreleri: ${r.algorithms.map(a => `${a.name} ${nf(a.runtime_ms)} ms`).join(', ')}.`;
  $('pgResult').scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'});
}

function init() {
  bindRange('pgAisles', null, v => { state.layout.aisles = v; rebuild(); });
  bindRange('pgRacks', null, v => { state.layout.racks = v; rebuild(); });
  bindRange('pgOrders', null, () => { makeRandom(); draw(); });
  bindRange('pgLines', null, () => { makeRandom(); draw(); });
  bindRange('pgCap', null, () => draw());
  $('pgPopular').addEventListener('change', () => { makeRandom(); draw(); });
  $('pgBlocks').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; state.layout.blocks = +b.dataset.v; segValue($('pgBlocks'), b.dataset.v); rebuild(); });
  $('pgDoor').addEventListener('change', e => { state.layout.door = e.target.value; rebuild(); });
  $('pgMode').addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    state.mode = b.dataset.v; segValue($('pgMode'), state.mode);
    $('pgRandomBox').hidden = state.mode !== 'random'; $('pgManualBox').hidden = state.mode !== 'manual';
    draw();
  });
  $('pgNew').addEventListener('click', () => { state.seed = (state.seed * 7919 + 13) % 100000; makeRandom(); draw(); });
  $('pgCanvas').addEventListener('click', ev => {
    if (state.mode !== 'manual') return;
    const l = pickLoc(ev); if (!l) return;
    if (state.draft.has(l.id)) state.draft.delete(l.id); else state.draft.add(l.id);
    draw();
  });
  $('pgAdd').addEventListener('click', () => {
    if (!state.draft.size) return;
    state.manual.push(lib.manualOrder(state.manual.length, [...state.draft]));
    state.draft.clear(); draw();
  });
  $('pgClear').addEventListener('click', () => { state.manual = []; state.draft.clear(); draw(); });
  $('pgRun').addEventListener('click', run);
  RA.onTheme(draw);
  let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(draw, 120); });
  rebuild();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
