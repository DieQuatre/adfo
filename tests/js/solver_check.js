// "Kendin dene" çözücüsünün tutarlılık kontrolü (tests/test_site_solver.py çağırır).
const fs=require('fs'); const path=require('path');
eval(fs.readFileSync(path.join(__dirname,'..','..','site','solver.js'),'utf8')+';global.lib=rafSolverLib();');
let bad=0;
for (const door of ['alt-sag','alt-orta','alt-sol','sag-orta']) for (const blocks of [1,2,3]) {
  const layout={aisles:8,blocks,racks:12,door};
  const L=lib.buildLayout(layout);
  // triangle inequality & symmetry spot checks
  for (let t=0;t<300;t++){const a=Math.floor(Math.random()*L.locs.length),b=Math.floor(Math.random()*L.locs.length),c=Math.floor(Math.random()*L.locs.length);
    if (Math.abs(L.dist(a,b)-L.dist(b,a))>1e-9) bad++;
    if (L.dist(a,c)>L.dist(a,b)+L.dist(b,c)+1e-9) bad++;
    const w=[[L.locs[a].x,L.locs[a].y],...L.walk(a,b)]; let s=0; for(let i=1;i<w.length;i++) s+=Math.abs(w[i][0]-w[i-1][0])+Math.abs(w[i][1]-w[i-1][1]);
    if (Math.abs(s-L.dist(a,b))>1e-6) {bad++; if(bad<3) console.log('walk mismatch',door,blocks,s,L.dist(a,b));}
  }
  const orders=lib.makeOrders(L,30,3,true,7);
  const t0=Date.now(); const res=lib.solveAll({layout,orders,capacity:40,seed:7});
  for (const a of res.algorithms){
    const seen=[]; let tot=0;
    for (const b of a.batches){ let s=0; for(let i=1;i<b.path.length;i++) s+=Math.abs(b.path[i][0]-b.path[i-1][0])+Math.abs(b.path[i][1]-b.path[i-1][1]); if(Math.abs(s-b.dist)>0.06){bad++;console.log('path len',s,b.dist);} tot+=b.dist;}
  }
  console.log(door,blocks, res.algorithms.map(a=>`${a.name}=${a.total} (${a.runtime_ms}ms, ${a.batches.length}b)`).join(' '), Date.now()-t0+'ms');
}
console.log('bad',bad);
process.exit(bad?1:0);
