# -*- coding: utf-8 -*-
"""共享的 CSS/JS 内核 —— 三个版式 demo 只有布局层不同,交互内核与数据完全一致。"""

import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(HERE, 'assets/data_slim.json'), encoding='utf-8'))
DATA_JS = json.dumps(DATA, ensure_ascii=False, separators=(',', ':'))

# ---------------------------------------------------------------- tokens & base
BASE_CSS = """
:root{
  --ground:#eef1f4; --surface:#ffffff; --surface-2:#f6f8fa; --ink:#16232e; --muted:#5f7285;
  --line:#dce3ea; --line-strong:#c8d2dc;
  --accent:#0e6f8f; --accent-soft:#e3f1f7; --accent-ink:#0a5470;
  --ok:#0c7a4d; --ok-soft:#e0f2e9; --bad:#b3382c; --bad-soft:#fbe9e6; --warn:#a8680a; --warn-soft:#fdf1dc;
  --missing:#6b7c8c; --missing-soft:#eceff2;
  --cat-geo:#4a7fb5; --cat-solid:#2e8b74; --cat-elyte:#a86f2e; --cat-kin:#b04a3c; --cat-init:#7a68b8; --cat-op:#5d7a3a;
  --hl:#ef9d12;
  --r-s:6px; --r-m:9px;
  --sans:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  --shadow-float:0 10px 34px rgba(13,34,48,.18),0 2px 8px rgba(13,34,48,.10);
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --ground:#10161c; --surface:#161e26; --surface-2:#1b242e; --ink:#dbe4ec; --muted:#8496a5;
  --line:#27333e; --line-strong:#39485a;
  --accent:#41a5c9; --accent-soft:#123240; --accent-ink:#7cc3de;
  --ok:#3ba877; --ok-soft:#11301f; --bad:#d26257; --bad-soft:#381512; --warn:#cf9138; --warn-soft:#33260e;
  --missing:#7e8f9e; --missing-soft:#202a33;
  --hl:#f0a52c;
}}
:root[data-theme="dark"]{
  --ground:#10161c; --surface:#161e26; --surface-2:#1b242e; --ink:#dbe4ec; --muted:#8496a5;
  --line:#27333e; --line-strong:#39485a;
  --accent:#41a5c9; --accent-soft:#123240; --accent-ink:#7cc3de;
  --ok:#3ba877; --ok-soft:#11301f; --bad:#d26257; --bad-soft:#381512; --warn:#cf9138; --warn-soft:#33260e;
  --missing:#7e8f9e; --missing-soft:#202a33;
  --hl:#f0a52c;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;font:13.5px/1.5 var(--sans);color:var(--ink);background:var(--ground);overflow:hidden}
button,input,select,textarea{font:inherit;color:inherit}
button{cursor:pointer}
:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
@media (prefers-reduced-motion: reduce){*{animation:none!important;transition:none!important}}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.num{font-variant-numeric:tabular-nums}

/* ---- 顶栏 ---- */
.top{display:flex;align-items:center;gap:14px;padding:0 16px;height:52px;background:var(--surface);border-bottom:1px solid var(--line);flex:0 0 auto}
.brand{display:flex;align-items:baseline;gap:9px;min-width:0}
.brand b{font-size:14.5px;font-weight:700;letter-spacing:.2px;white-space:nowrap}
.brand span{font-size:11.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.demo-switch{display:flex;border:1px solid var(--line);border-radius:var(--r-s);overflow:hidden;flex:0 0 auto}
.demo-switch a{display:block;padding:4px 10px;font-size:11.5px;font-weight:600;color:var(--muted);text-decoration:none;border-right:1px solid var(--line)}
.demo-switch a:last-child{border-right:0}
.demo-switch a.on{background:var(--accent);color:#fff}
.demo-switch a:not(.on):hover{background:var(--surface-2);color:var(--ink)}
.stats{margin-left:auto;display:flex;align-items:center;gap:10px}
.stat{display:flex;align-items:baseline;gap:5px;font-size:11px;color:var(--muted)}
.stat b{font-size:15px;font-weight:650;color:var(--ink);font-variant-numeric:tabular-nums}
.stat.ok b{color:var(--ok)} .stat.bad b{color:var(--bad)} .stat.pend b{color:var(--warn)}
.progress{width:130px;height:6px;border-radius:99px;background:var(--line);overflow:hidden}
.progress>div{height:100%;width:0%;background:var(--accent);border-radius:99px;transition:width .25s}
.theme-btn{border:1px solid var(--line);background:var(--surface);border-radius:var(--r-s);padding:5px 9px;font-size:11.5px;font-weight:600;color:var(--muted)}
.theme-btn:hover{color:var(--ink);background:var(--surface-2)}

/* ---- 通用部件 ---- */
.chip{display:inline-flex;align-items:center;gap:5px;border-radius:99px;padding:2px 9px;font-size:10.5px;font-weight:650;letter-spacing:.2px;white-space:nowrap}
.chip.pending{background:var(--warn-soft);color:var(--warn)}
.chip.verified{background:var(--ok-soft);color:var(--ok)}
.chip.conflict{background:var(--bad-soft);color:var(--bad)}
.chip.missing{background:var(--missing-soft);color:var(--missing)}
.chip.derived{background:var(--accent-soft);color:var(--accent-ink)}
.dot{width:8px;height:8px;border-radius:99px;flex:0 0 auto}
.btn{border:1px solid var(--line-strong);background:var(--surface);border-radius:var(--r-s);padding:7px 12px;font-weight:650;font-size:12.5px;color:var(--ink)}
.btn:hover{background:var(--surface-2)}
.btn.ok{background:var(--ok);border-color:var(--ok);color:#fff}
.btn.ok:hover{filter:brightness(1.06)}
.btn.bad{background:var(--bad);border-color:var(--bad);color:#fff}
.btn.bad:hover{filter:brightness(1.06)}
.btn.ghost{border-color:var(--line);color:var(--muted)}
.btn.icon{padding:5px 9px}
.kbd{display:inline-block;min-width:15px;text-align:center;border:1px solid var(--line-strong);border-bottom-width:2px;border-radius:4px;padding:0 4px;font-family:var(--mono);font-size:10px;color:var(--muted);background:var(--surface-2)}
.label{font-size:10px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:var(--muted)}

/* ---- 参数列表轨 ---- */
.rail{display:flex;flex-direction:column;min-height:0;background:var(--surface)}
.rail-head{padding:10px 12px 8px;border-bottom:1px solid var(--line);flex:0 0 auto}
.rail-title{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.rail-title b{font-size:12.5px;font-weight:700}
.rail-title span{font-size:10.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.search{width:100%;border:1px solid var(--line);border-radius:var(--r-s);padding:6px 9px;font-size:12px;background:var(--surface-2)}
.search:focus{outline:none;border-color:var(--accent);background:var(--surface)}
.cat-row{display:flex;flex-wrap:wrap;gap:4px;margin-top:7px}
.cat-pill{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--line);border-radius:99px;padding:2px 8px;font-size:10.5px;font-weight:600;color:var(--muted);background:transparent}
.cat-pill.on{border-color:var(--ink);color:var(--ink);background:var(--surface-2)}
.plist{flex:1;overflow-y:auto;min-height:0}
.pitem{width:100%;text-align:left;display:block;border:0;border-left:3px solid transparent;background:transparent;padding:7px 10px 7px 9px;border-bottom:1px solid var(--line)}
.pitem:hover{background:var(--surface-2)}
.pitem.active{background:var(--accent-soft);border-left-color:var(--accent)}
.pitem .l1{display:flex;align-items:center;gap:6px}
.pitem .name{font-size:12.5px;font-weight:650;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;min-width:0}
.pitem .pg{font-family:var(--mono);font-size:10px;color:var(--muted);flex:0 0 auto}
.pitem .l2{display:flex;align-items:center;gap:6px;margin-top:2px}
.pitem .val{font-family:var(--mono);font-size:11px;color:var(--ink);opacity:.82;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;min-width:0}
.pitem .st{flex:0 0 auto;display:flex;align-items:center;gap:4px;font-size:9.5px;font-weight:700;letter-spacing:.3px;color:var(--muted)}
.pitem .st i{width:7px;height:7px;border-radius:99px;background:var(--missing)}
.pitem[data-status="PENDING"] .st i{background:var(--warn)}
.pitem[data-status="VERIFIED"] .st i{background:var(--ok)}
.pitem[data-status="CONFLICT"] .st i{background:var(--bad)}
.pitem[data-status="VERIFIED"] .name,.pitem[data-status="CONFLICT"] .name{opacity:.62}

/* ---- 证据舞台 ---- */
.stage{display:flex;flex-direction:column;min-width:0;min-height:0}
.stage-head{display:flex;align-items:center;gap:8px;padding:7px 12px;background:var(--surface);border-bottom:1px solid var(--line);flex:0 0 auto;flex-wrap:nowrap}
.stage-head .grow{flex:1;min-width:0}
.page-nav{display:flex;align-items:center;gap:5px}
.page-input{width:44px;text-align:center;border:1px solid var(--line);border-radius:var(--r-s);padding:4px 2px;font-family:var(--mono);font-size:12px;background:var(--surface-2)}
.page-total{font-family:var(--mono);font-size:11px;color:var(--muted)}
.viewer{flex:1;min-height:0;overflow:auto;background:var(--ground);padding:18px}
.sheet{position:relative;width:max-content;margin:0 auto;box-shadow:0 3px 18px rgba(13,34,48,.14)}
.sheet img{display:block;max-width:none}
.hl{position:absolute;border:2px solid var(--hl);background:rgba(240,165,44,.20);border-radius:2px;pointer-events:none;display:none}
.hl.pulse{animation:hlpulse 1.1s ease-out 1}
@keyframes hlpulse{0%{box-shadow:0 0 0 0 rgba(240,165,44,.55)}100%{box-shadow:0 0 0 14px rgba(240,165,44,0)}}
.hl-m{position:absolute;border:2px dashed var(--hl);background:rgba(240,165,44,.10);border-radius:2px;cursor:pointer}
.hl-m:hover{background:rgba(240,165,44,.24)}
.hl-m b{position:absolute;top:-9px;left:-9px;width:17px;height:17px;border-radius:99px;background:var(--hl);color:#fff;font-family:var(--mono);font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center}
#hls{position:absolute;inset:0;pointer-events:none}
#hls .hl-m{pointer-events:auto}
.page-label{position:sticky;top:0;display:flex;justify-content:center;pointer-events:none;margin-bottom:-14px}
.page-label span{font-family:var(--mono);font-size:10px;color:var(--muted);background:var(--surface);border:1px solid var(--line);border-radius:99px;padding:1px 9px;opacity:.9}

/* ---- 声称卡 ---- */
.claim{display:flex;flex-direction:column;min-height:0;background:var(--surface)}
#claim-body{flex:1;min-height:0;overflow-y:auto}
.c-sec{padding:11px 14px;border-bottom:1px solid var(--line)}
.c-top{display:flex;align-items:center;gap:6px;margin-bottom:6px}
.c-name{font-size:15px;font-weight:700;line-height:1.3;text-wrap:balance}
.c-pb{font-family:var(--mono);font-size:10.5px;color:var(--muted);margin-top:2px;overflow-wrap:anywhere}
.vrow{display:flex;align-items:baseline;gap:8px;margin-top:2px}
.v-big{font-family:var(--mono);font-size:21px;font-weight:600;letter-spacing:-.2px;border:0;border-bottom:1px dashed transparent;background:transparent;padding:0;width:100%;min-width:0;color:var(--ink)}
.v-big:hover{border-bottom-color:var(--line-strong)}
.v-big:focus{outline:none;border-bottom-color:var(--accent)}
.v-unit{font-family:var(--mono);font-size:12px;color:var(--muted);flex:0 0 auto}
.v-kind{font-size:10px;font-weight:700;color:var(--accent-ink);background:var(--accent-soft);border-radius:4px;padding:1px 6px;flex:0 0 auto}
.mgrid{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;font-size:11.5px}
.mgrid dt{color:var(--muted);white-space:nowrap}
.mgrid dd{margin:0;font-family:var(--mono);font-size:11px;color:var(--ink);overflow-wrap:anywhere}
.mgrid a{color:var(--accent);text-decoration:none;font-weight:650}
.quote{font-size:12px;line-height:1.55;color:var(--ink);background:var(--surface-2);border-left:3px solid var(--line-strong);padding:7px 10px;border-radius:0 var(--r-s) var(--r-s) 0;overflow-wrap:anywhere}
.ev-img{display:block;max-width:100%;border:1px solid var(--line);border-radius:var(--r-s);cursor:zoom-in;background:#fff}
.ev-note{font-size:10.5px;color:var(--muted);margin-top:5px}
.warnline{display:flex;gap:7px;align-items:flex-start;font-size:11.5px;color:var(--warn);background:var(--warn-soft);border-radius:var(--r-s);padding:7px 10px;line-height:1.45}
.actions{display:flex;gap:7px;padding:10px 14px;border-top:1px solid var(--line);background:var(--surface);flex:0 0 auto}
.actions .btn{flex:1;padding:9px 6px;font-size:12.5px}
.actions .btn .kbd{margin-left:4px}
.nota{width:100%;border:1px solid var(--line);border-radius:var(--r-s);padding:6px 9px;font-size:11.5px;resize:none;background:var(--surface-2);min-height:38px}
.nota:focus{outline:none;border-color:var(--accent);background:var(--surface)}

/* ---- toast ---- */
.toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(8px);background:var(--ink);color:var(--ground);border-radius:var(--r-s);padding:8px 15px;font-size:12px;font-weight:600;opacity:0;pointer-events:none;transition:opacity .18s,transform .18s;z-index:90}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}

/* ---- 布局说明浮签 ---- */
.spec{position:fixed;left:14px;bottom:14px;z-index:60;max-width:250px;background:var(--surface);border:1px solid var(--line);border-radius:var(--r-m);box-shadow:var(--shadow-float);font-size:11px;line-height:1.55;color:var(--muted);padding:10px 12px}
.spec b{display:block;font-size:12px;color:var(--ink);margin-bottom:3px}
.spec .x{position:absolute;top:4px;right:7px;border:0;background:none;color:var(--muted);font-size:13px;padding:2px}
"""

# ---------------------------------------------------------------- shared JS
COMMON_JS = r"""
/* ================= 数据与状态 ================= */
const CATS = {
  geometry_structure:{zh:'几何结构', c:'var(--cat-geo)'},
  solid_transport:{zh:'固相输运', c:'var(--cat-solid)'},
  electrolyte:{zh:'电解液', c:'var(--cat-elyte)'},
  kinetics_ocp:{zh:'动力学 / OCP', c:'var(--cat-kin)'},
  initial_conditions:{zh:'初始条件', c:'var(--cat-init)'},
  operating_conditions:{zh:'工况', c:'var(--cat-op)'}
};
const ST = {
  PENDING:{zh:'待审核', cls:'pending', dot:'var(--warn)'},
  VERIFIED:{zh:'已确认', cls:'verified', dot:'var(--ok)'},
  CONFLICT:{zh:'有冲突', cls:'conflict', dot:'var(--bad)'},
  MISSING:{zh:'未找到', cls:'missing', dot:'var(--missing)'}
};
const LOC = {table:'表格单元格', text:'正文文本', formula:'公式', figure:'曲线图', none:'无定位'};

const state = {
  cur: 0,
  page: 1,
  zoom: 1,            // 1 = fit-width
  filter: {q:'', cat:'all', status:'all'},
  items: DATA.params.map(p => Object.assign({}, p, {status:'PENDING', note:''}))
};

/* ================= 值格式化 ================= */
function fmtVal(p){
  const v = p.v;
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number'){
    if (v === 0) return '0';
    const a = Math.abs(v);
    if (a < 0.01 || a >= 1e6){
      const exp = Math.floor(Math.log10(a));
      const m = v / Math.pow(10, exp);
      return m.toFixed(2).replace(/\.?0+$/,'') + 'e' + exp;
    }
    return String(parseFloat(v.toPrecision(5)));
  }
  let s = String(v);
  if (s.startsWith('expr://sym:')) s = s.slice(11);
  return s;
}
function isExpr(p){ return typeof p.v === 'string' && p.v.startsWith('expr://'); }
function isCurve(p){ return typeof p.v === 'string' && p.v.startsWith('data://curve:'); }

/* ================= 过滤后的清单 ================= */
function visible(){
  const q = state.filter.q.trim().toLowerCase();
  return state.items
    .map((p,i)=>({p,i}))
    .filter(({p})=>{
      if (state.filter.cat !== 'all' && p.cat !== state.filter.cat) return false;
      if (state.filter.status !== 'all' && p.status !== state.filter.status) return false;
      if (q && !(p.id+' '+p.en+' '+(p.pb||'')).toLowerCase().includes(q)) return false;
      return true;
    });
}
function curIdx(){ return state.cur; }

/* ================= 列表渲染 ================= */
function renderList(){
  const ul = document.getElementById('plist');
  const vis = visible();
  ul.innerHTML = vis.map(({p,i})=>{
    const cat = CATS[p.cat] || {zh:p.cat, c:'#888'};
    const st = ST[p.status];
    return `<button class="pitem ${i===state.cur?'active':''}" data-i="${i}" data-status="${p.status}">
      <span class="l1"><span class="dot" style="background:${cat.c}"></span>
        <span class="name">${p.en}</span><span class="pg">p${p.pg??'—'}</span></span>
      <span class="l2"><span class="val">${esc(fmtVal(p))} ${p.u?esc(p.u):''}</span>
        <span class="st"><i></i>${st.zh}</span></span>
    </button>`;
  }).join('') || '<div style="padding:18px;color:var(--muted);font-size:12px">无匹配参数</div>';
  document.getElementById('count-info').textContent = `${vis.length} / ${state.items.length} 项`;
  ul.querySelectorAll('.pitem').forEach(el=>el.addEventListener('click',()=>select(+el.dataset.i)));
}
function esc(s){ return String(s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

function syncActive(){
  document.querySelectorAll('.pitem').forEach(el=>{
    const on = +el.dataset.i === state.cur;
    el.classList.toggle('active', on);
    if (on) el.scrollIntoView({block:'nearest'});
  });
}

/* ================= 统计 ================= */
function renderStats(){
  const it = state.items;
  const ok = it.filter(p=>p.status==='VERIFIED').length;
  const bad = it.filter(p=>p.status==='CONFLICT').length;
  const miss = it.filter(p=>p.status==='MISSING').length;
  const pend = it.length - ok - bad - miss;
  set('st-total', it.length); set('st-ok', ok); set('st-bad', bad); set('st-pend', pend);
  document.querySelector('#progress>div').style.width = ((ok+bad+miss)/it.length*100)+'%';
}
function set(id,v){ document.getElementById(id).textContent = v; }

/* ================= 声称卡 ================= */
function renderClaim(){
  const p = state.items[state.cur];
  const st = ST[p.status], cat = CATS[p.cat]||{zh:p.cat,c:'#888'};
  document.getElementById('claim-body').innerHTML = `
    <div class="c-sec" data-zone="id">
      <div class="c-top">
        <span class="chip ${st.cls}">${st.zh}</span>
        <span class="chip derived" style="background:transparent;border:1px solid var(--line);color:var(--muted)">
          <span class="dot" style="background:${cat.c};width:7px;height:7px"></span>${cat.zh}</span>
        ${p.src!=='PAPER'?`<span class="chip derived">${p.src}</span>`:''}
      </div>
      <div class="c-name">${esc(p.en)}</div>
      <div class="c-pb">${esc(p.pb||'')}</div>
    </div>
    <div class="c-sec" data-zone="value">
      <div class="label" style="margin-bottom:5px">提取值（可直接修正）</div>
      <div class="vrow">
        <input class="v-big" id="edit-val" value="${esc(fmtVal(p))}" spellcheck="false">
        <span class="v-unit">${esc(p.u||'')}</span>
        ${isExpr(p)?'<span class="v-kind">表达式</span>':''}
        ${isCurve(p)?'<span class="v-kind">曲线数据</span>':''}
      </div>
    </div>
    <div class="c-sec" data-zone="meta">
      <dl class="mgrid">
        <dt>证据类型</dt><dd>${LOC[p.loc]||p.loc}</dd>
        <dt>证据页</dt><dd>${p.pg?`<a href="javascript:void(0)" id="goto-page">第 ${p.pg} 页</a>`:'—'}</dd>
        <dt>定位置信</dt><dd>${locTrust(p)}</dd>
      </dl>
    </div>
    <div class="c-sec" data-zone="quote">
      <div class="label" style="margin-bottom:5px">原文引用</div>
      <div class="quote">${p.q?esc(p.q):'<span style="color:var(--muted)">（无引用文本）</span>'}</div>
      ${p.ncand>1?`<div class="warnline" style="margin-top:8px">ⓘ 文本搜索命中 ${p.ncand} 处 —— 候选位置已用虚线框编号标在页面上，点击正确的即采纳为定位。</div>`:''}
    </div>
    ${evidenceCard(p)}
    <div class="c-sec" data-zone="note" style="border-bottom:0">
      <div class="label" style="margin-bottom:5px">审核备注</div>
      <textarea class="nota" id="edit-note" placeholder="修订原因 / 疑点 / 适用范围……">${esc(p.note)}</textarea>
    </div>`;
  const g = document.getElementById('goto-page');
  if (g) g.addEventListener('click', ()=>gotoPage(p.pg, true));
  document.getElementById('edit-note').addEventListener('input', e=>{ state.items[state.cur].note = e.target.value; });
  document.getElementById('edit-val').addEventListener('change', e=>{
    const raw = e.target.value.trim();
    const num = Number(raw);
    state.items[state.cur].v = (raw!=='' && !isNaN(num)) ? num : raw;
    renderList();
  });
}
function locTrust(p){
  if (p.loc==='none') return '<span style="color:var(--bad)">未定位</span>';
  if (p.ncand>1) return `<span style="color:var(--warn)">多义 ×${p.ncand}</span>`;
  if (p.loc==='table') return '表格解析';
  return '精确匹配';
}
function evidenceCard(p){
  if (p.loc==='table') return `
    <div class="c-sec" data-zone="evidence">
      <div class="label" style="margin-bottom:6px">表格裁片证据</div>
      <a href="assets/table_p19.png" target="_blank"><img class="ev-img" src="assets/table_p19.png" alt="表格裁片"></a>
      <div class="ev-note">Docling 结构化表格裁片 · 点击放大核对行列</div>
    </div>`;
  if (p.loc==='formula') return `
    <div class="c-sec" data-zone="evidence">
      <div class="label" style="margin-bottom:6px">公式截片证据</div>
      <a href="assets/formula_p18.png" target="_blank"><img class="ev-img" src="assets/formula_p18.png" alt="公式截片"></a>
      <div class="ev-note">PDF 矢量截片 · 与 SymPy 重建表达式核对</div>
    </div>`;
  if (p.loc==='figure') return `
    <div class="c-sec" data-zone="evidence">
      <div class="label" style="margin-bottom:6px">曲线图证据</div>
      <a href="assets/curve_p12.jpg" target="_blank"><img class="ev-img" src="assets/curve_p12.jpg" alt="曲线图"></a>
      <div class="ev-note">Fig.12 数字化曲线 · 数据引用 ${esc(String(p.v).replace('data://curve:',''))}</div>
    </div>`;
  return '';
}

/* ================= PDF 视图 ================= */
const NPAGES = DATA.doc.pages;
function pageImgUrl(n){ return 'assets/p' + String(n).padStart(2,'0') + '.jpg'; }

function renderViewer(){
  const sheet = document.getElementById('sheet');
  document.getElementById('pageimg').src = pageImgUrl(state.page);
  document.getElementById('page-cur').value = state.page;
  document.getElementById('page-total').textContent = '/ ' + NPAGES;
  const pl = document.getElementById('plabel');
  if (pl) pl.textContent = DATA.doc.id + ' · 第 ' + state.page + ' 页';
  const p = state.items[state.cur];
  /* 高亮:已定位 bbox → 实心单框;多义未定 → 虚线候选框编号,点选采纳 */
  const hls = document.getElementById('hls');
  hls.innerHTML = '';
  const hl = document.getElementById('hl');
  hl.style.display = 'none';
  if (p.pg === state.page && p.bbox){
    hl.style.display = 'block';
    hl.style.left  = (p.bbox[0]*100)+'%';
    hl.style.top   = (p.bbox[1]*100)+'%';
    hl.style.width = ((p.bbox[2]-p.bbox[0])*100)+'%';
    hl.style.height= ((p.bbox[3]-p.bbox[1])*100)+'%';
    hl.classList.remove('pulse'); void hl.offsetWidth; hl.classList.add('pulse');
  } else if (p.pg === state.page && p.cands && p.cands.length){
    p.cands.forEach((c,k)=>{
      if (c[0] !== state.page) return;
      const b = c[1];
      const d = document.createElement('div');
      d.className = 'hl-m';
      d.style.left=(b[0]*100)+'%'; d.style.top=(b[1]*100)+'%';
      d.style.width=((b[2]-b[0])*100)+'%'; d.style.height=((b[3]-b[1])*100)+'%';
      d.title = '候选 ' + (k+1) + ' —— 点选采纳为定位';
      const n = document.createElement('b'); n.textContent = k+1; d.appendChild(n);
      d.addEventListener('click', ()=>{
        p.bbox = b; toast('已采纳候选 ' + (k+1) + ' 为定位框');
        renderViewer(); renderClaim();
      });
      hls.appendChild(d);
    });
  }
  applyZoom();
  requestAnimationFrame(scrollToHl);
}
function applyZoom(){
  const viewer = document.getElementById('viewer');
  const sheet = document.getElementById('sheet');
  const img = document.getElementById('pageimg');
  const w = viewer.clientWidth - 36;
  const target = Math.round(w * state.zoom);
  sheet.style.width = target + 'px';
  img.style.width = target + 'px';
  img.style.height = 'auto';
  document.getElementById('zoom-label').textContent = Math.round(state.zoom*100)+'%';
}
function scrollToHl(){
  const hl = document.getElementById('hl');
  const box = (hl.style.display!=='none') ? hl : document.querySelector('#hls .hl-m');
  if (!box) return;
  const viewer = document.getElementById('viewer');
  const r = box.getBoundingClientRect(), v = viewer.getBoundingClientRect();
  if (r.top < v.top+30 || r.bottom > v.bottom-30){
    const dTop = (r.top - v.top) - (v.height - r.height)/2;
    viewer.scrollTo({top: viewer.scrollTop + dTop, behavior:'smooth'});
  }
  if (r.left < v.left+10 || r.right > v.right-10){
    const dLeft = (r.left - v.left) - (v.width - r.width)/2;
    viewer.scrollTo({left: viewer.scrollLeft + dLeft, behavior:'smooth'});
  }
}
function gotoPage(n, pulse){
  state.page = Math.min(NPAGES, Math.max(1, n));
  renderViewer();
}

/* ================= 选择与判定 ================= */
function select(i, jumpPage=true){
  state.cur = i;
  const p = state.items[i];
  renderClaim(); renderList(); renderStats(); syncActive();
  if (jumpPage && p.pg){ state.page = p.pg; renderViewer(); }
  if (LAYOUT==='B') closeDrawer();
}
function verdict(status){
  const p = state.items[state.cur];
  p.status = status;
  const vis = visible();
  const pos = vis.findIndex(x=>x.i===state.cur);
  renderList(); renderStats(); renderClaim(); syncActive();
  let next = null;
  for (let k=1;k<=vis.length;k++){
    const cand = vis[(pos+k)%vis.length];
    if (cand && cand.p.status==='PENDING'){ next = cand; break; }
  }
  if (next){ select(next.i); } else { state.cur = state.cur; renderClaim(); }
  toast(({VERIFIED:'✓ 已确认',CONFLICT:'⚑ 已标记冲突',MISSING:'⊘ 已标记未找到'})[status] + '　' +
        state.items.filter(x=>x.status!=='PENDING').length + '/' + state.items.length);
}
let toastTimer=null;
function toast(msg){
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(()=>t.classList.remove('show'), 1600);
}

/* ================= 工具栏 ================= */
function bindToolbar(){
  document.getElementById('prev-page').addEventListener('click', ()=>gotoPage(state.page-1));
  document.getElementById('next-page').addEventListener('click', ()=>gotoPage(state.page+1));
  document.getElementById('page-cur').addEventListener('change', e=>gotoPage(+e.target.value||1));
  document.getElementById('zoom-in').addEventListener('click', ()=>{ state.zoom=Math.min(3, state.zoom*1.25); applyZoom(); });
  document.getElementById('zoom-out').addEventListener('click', ()=>{ state.zoom=Math.max(.4, state.zoom/1.25); applyZoom(); });
  document.getElementById('zoom-fit').addEventListener('click', ()=>{ state.zoom=1; applyZoom(); });
  document.getElementById('locate').addEventListener('click', ()=>{
    const p = state.items[state.cur];
    if (p.pg){ state.page=p.pg; renderViewer(); }
  });
  document.getElementById('verify').addEventListener('click', ()=>verdict('VERIFIED'));
  document.getElementById('flag').addEventListener('click', ()=>verdict('CONFLICT'));
  document.getElementById('missing').addEventListener('click', ()=>verdict('MISSING'));
  const search = document.getElementById('search');
  search.addEventListener('input', e=>{ state.filter.q=e.target.value; renderList(); syncActive(); });
  const statusSel = document.getElementById('status-filter');
  statusSel.addEventListener('change', e=>{ state.filter.status=e.target.value; renderList(); syncActive(); });
  const catRow = document.getElementById('cat-row');
  Object.entries(CATS).forEach(([k,c])=>{
    const b = document.createElement('button');
    b.className='cat-pill'; b.dataset.cat=k;
    b.innerHTML = `<span class="dot" style="background:${c.c};width:7px;height:7px"></span>${c.zh}`;
    b.addEventListener('click', ()=>{
      state.filter.cat = state.filter.cat===k ? 'all' : k;
      catRow.querySelectorAll('.cat-pill').forEach(x=>x.classList.toggle('on', x.dataset.cat===state.filter.cat));
      renderList(); syncActive();
    });
    catRow.appendChild(b);
  });
  const theme = document.getElementById('theme-btn');
  theme.addEventListener('click', ()=>{
    const cur = document.documentElement.dataset.theme ||
      (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark':'light');
    const nx = cur==='dark' ? 'light':'dark';
    document.documentElement.dataset.theme = nx;
    try{ localStorage.setItem('demo-theme', nx); }catch(e){}
  });
  try{
    const saved = localStorage.getItem('demo-theme');
    if (saved) document.documentElement.dataset.theme = saved;
  }catch(e){}
}

/* ================= 键盘 ================= */
document.addEventListener('keydown', e=>{
  const tag = (e.target.tagName||'').toLowerCase();
  if (tag==='input'||tag==='textarea'||tag==='select') return;
  const vis = visible();
  const pos = vis.findIndex(x=>x.i===state.cur);
  if (e.key==='ArrowDown'||e.key==='j'){ if(pos<vis.length-1) select(vis[pos+1].i); e.preventDefault(); }
  else if (e.key==='ArrowUp'||e.key==='k'){ if(pos>0) select(vis[pos-1].i); e.preventDefault(); }
  else if (e.key==='Enter'){ verdict('VERIFIED'); e.preventDefault(); }
  else if (e.key==='c'||e.key==='C'){ verdict('CONFLICT'); e.preventDefault(); }
  else if (e.key==='['){ gotoPage(state.page-1); e.preventDefault(); }
  else if (e.key===']'){ gotoPage(state.page+1); e.preventDefault(); }
  else if (LAYOUT==='B' && (e.key==='l'||e.key==='L')){ toggleDrawer(); e.preventDefault(); }
});
window.addEventListener('resize', applyZoom);
"""

TOPBAR = """
<header class="top">
  <div class="brand"><b>⚗ 证据审核台</b><span id="layout-tag"></span></div>
  <nav class="demo-switch" aria-label="方案切换">
    <a href="demoA.html" data-k="A">A 三栏主审</a>
    <a href="demoB.html" data-k="B">B 沉浸聚焦</a>
    <a href="demoC.html" data-k="C">C 双轨对照</a>
  </nav>
  <div class="stats">
    <span class="stat pend">待审 <b id="st-pend">0</b></span>
    <span class="stat ok">确认 <b id="st-ok">0</b></span>
    <span class="stat bad">冲突 <b id="st-bad">0</b></span>
    <span class="stat">/ <b id="st-total">0</b></span>
    <div class="progress" id="progress"><div></div></div>
    <button class="theme-btn" id="theme-btn">◐ 主题</button>
  </div>
</header>
"""

LIST_RAIL = """
<aside class="rail" id="rail">
  <div class="rail-head">
    <div class="rail-title"><b>参数审核清单</b><span id="count-info"></span></div>
    <input class="search" id="search" placeholder="搜索 名称 / 标识符 / 单位…">
    <div class="cat-row" id="cat-row"></div>
    <div class="cat-row">
      <select id="status-filter" class="cat-pill" style="padding:2px 6px">
        <option value="all">全部状态</option><option value="PENDING">待审核</option>
        <option value="VERIFIED">已确认</option><option value="CONFLICT">有冲突</option>
        <option value="MISSING">未找到</option>
      </select>
    </div>
  </div>
  <div class="plist" id="plist"></div>
</aside>
"""

STAGE = """
<section class="stage" id="stage">
  <div class="stage-head">
    <div class="page-nav">
      <button class="btn icon ghost" id="prev-page">‹</button>
      <input class="page-input" id="page-cur" type="number" min="1" value="1">
      <span class="page-total" id="page-total">/ —</span>
      <button class="btn icon ghost" id="next-page">›</button>
    </div>
    <div class="page-nav">
      <button class="btn icon ghost" id="zoom-out">−</button>
      <span class="page-total" id="zoom-label">100%</span>
      <button class="btn icon ghost" id="zoom-in">＋</button>
      <button class="btn ghost" id="zoom-fit" style="font-size:11px;padding:5px 8px">适宽</button>
    </div>
    <div class="grow"></div>
    <button class="btn ghost" id="locate" style="font-size:11px;padding:5px 10px">◎ 定位证据</button>
    <span class="page-total" id="kbd-hint">↑↓ 切换 · Enter 确认 · C 冲突</span>
  </div>
  <div class="viewer" id="viewer">
    <div class="page-label"><span id="plabel"></span></div>
    <div class="sheet" id="sheet"><img id="pageimg" alt="论文页"><div id="hls"></div><div class="hl" id="hl"></div></div>
  </div>
</section>
"""

CLAIM_COL = """
<aside class="claim" id="claimcol">
  <div id="claim-body"></div>
  <div class="actions">
    <button class="btn ok" id="verify">✓ 确认<span class="kbd">⏎</span></button>
    <button class="btn bad" id="flag">⚑ 冲突<span class="kbd">C</span></button>
    <button class="btn ghost" id="missing">⊘ 未找到</button>
  </div>
</aside>
"""

TOAST = '<div class="toast" id="toast"></div>'


def html(title, layout_tag, body, css, js, spec):
    switch_on = layout_tag[0]
    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<style>{BASE_CSS}
{css}</style>
</head>
<body>
{TOPBAR}
{body}
{spec}
{TOAST}
<script>
const LAYOUT = '{switch_on}';
const DATA = {DATA_JS};
</script>
<script>
{COMMON_JS}
{js}
</script>
</body>
</html>"""
    return page


if __name__ == '__main__':
    print('common module — run build_demos.py')
