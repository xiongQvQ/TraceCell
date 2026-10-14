#!/usr/bin/env python3
"""把 demoA 的三栏主审版式移植进 assets/review_template.html。

策略:整块替换 <style> 与 <body>,JS 只做定点补丁 —— 保住已跑通的
表格证据 / 公式证据 / 曲线标定 / 导出闸门 逻辑原样不动。

原文件备份为 review_template.html.bak(仅首次)。
用法:python3 scripts/port_review_template.py [--dry-run]
"""
import re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / 'assets' / 'review_template.html'
BAK = ROOT / 'assets' / 'review_template.html.bak'

# ------------------------------------------------------------------ 新样式
STYLE = r"""
:root{
  --ground:#eef1f4; --surface:#fff; --surface-2:#f6f8fa; --ink:#16232e; --muted:#5f7285;
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
  --missing:#7e8f9e; --missing-soft:#202a33; --hl:#f0a52c;
}}
:root[data-theme="dark"]{
  --ground:#10161c; --surface:#161e26; --surface-2:#1b242e; --ink:#dbe4ec; --muted:#8496a5;
  --line:#27333e; --line-strong:#39485a;
  --accent:#41a5c9; --accent-soft:#123240; --accent-ink:#7cc3de;
  --ok:#3ba877; --ok-soft:#11301f; --bad:#d26257; --bad-soft:#381512; --warn:#cf9138; --warn-soft:#33260e;
  --missing:#7e8f9e; --missing-soft:#202a33; --hl:#f0a52c;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;font:13.5px/1.5 var(--sans);color:var(--ink);background:var(--ground);overflow:hidden}
button,input,select,textarea{font:inherit;color:inherit}
button{cursor:pointer}
button:disabled{opacity:.45;cursor:not-allowed}
:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.small{font-size:11.5px;color:var(--muted)}
.grow{flex:1;min-width:0}
.label{font-size:10px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:var(--muted)}
input[type=file]{display:none}

/* ---------------- 顶栏 ---------------- */
.top{display:flex;align-items:center;gap:14px;padding:0 16px;height:52px;background:var(--surface);
  border-bottom:1px solid var(--line);flex:0 0 auto;flex-wrap:nowrap;overflow:hidden}
.brand{display:flex;align-items:baseline;gap:9px;min-width:0;flex:0 1 auto}
.brand b{font-size:14.5px;font-weight:700;white-space:nowrap}
.brand span{font-size:11.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:26ch}
.stats{display:flex;align-items:center;gap:10px;margin-left:auto}
.stat{display:flex;align-items:baseline;gap:5px;font-size:11px;color:var(--muted);white-space:nowrap}
.stat b{font-size:15px;font-weight:650;color:var(--ink);font-variant-numeric:tabular-nums}
.stat.ok b{color:var(--ok)} .stat.bad b{color:var(--bad)} .stat.pend b{color:var(--warn)}
.progress{width:120px;height:6px;border-radius:99px;background:var(--line);overflow:hidden}
.progress>div{height:100%;width:0%;background:var(--accent);border-radius:99px;transition:width .25s}
.actions{display:flex;align-items:center;gap:7px;flex-wrap:nowrap}
.docid{font-size:10.5px;color:var(--muted);white-space:nowrap}
.docid b{font-family:var(--mono);color:var(--ink);font-weight:600}

/* ---------------- 通用部件 ---------------- */
.btn{border:1px solid var(--line-strong);background:var(--surface);border-radius:var(--r-s);
  padding:7px 12px;font-weight:650;font-size:12.5px;color:var(--ink);white-space:nowrap}
.btn:hover{background:var(--surface-2)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.btn.primary:hover{filter:brightness(1.08)}
.btn.ok{background:var(--ok);border-color:var(--ok);color:#fff}
.btn.bad,.btn.warn{background:var(--bad);border-color:var(--bad);color:#fff}
.btn.ok:hover,.btn.bad:hover,.btn.warn:hover{filter:brightness(1.08)}
.btn.ghost{border-color:var(--line);color:var(--muted);background:transparent}
.btn.ghost:hover{color:var(--ink);background:var(--surface-2)}
.btn.icon{padding:5px 9px}
.btn.sm{padding:4px 9px;font-size:11.5px}
.kbd{display:inline-block;min-width:15px;text-align:center;border:1px solid currentColor;border-radius:4px;
  padding:0 4px;font-family:var(--mono);font-size:10px;opacity:.65;margin-left:4px}
.chip{display:inline-flex;align-items:center;gap:5px;border-radius:99px;padding:2px 9px;
  font-size:10.5px;font-weight:650;letter-spacing:.2px;white-space:nowrap}
.chip.pending{background:var(--warn-soft);color:var(--warn)}
.chip.verified{background:var(--ok-soft);color:var(--ok)}
.chip.conflict{background:var(--bad-soft);color:var(--bad)}
.chip.missing{background:var(--missing-soft);color:var(--missing)}
.chip.derived{background:var(--accent-soft);color:var(--accent-ink)}
.dot{width:8px;height:8px;border-radius:99px;flex:0 0 auto;display:inline-block}
.warning{background:var(--warn-soft);color:var(--warn);font-size:11px;padding:7px 16px;
  border-bottom:1px solid var(--line);flex:0 0 auto}
.warning code{font-family:var(--mono);font-size:10.5px}
.notice{font-size:11px;background:var(--accent-soft);color:var(--accent-ink);padding:7px 10px;
  border-radius:var(--r-s);margin-bottom:8px;line-height:1.5}
.footnote{font-size:10.5px;color:var(--muted);line-height:1.5;margin-top:8px}
.hint{border-top:1px solid var(--line);padding:7px 12px;color:var(--muted);background:var(--surface-2);font-size:10.5px;flex:0 0 auto}
.citation{font-size:11px;color:var(--muted);margin-top:7px;overflow-wrap:anywhere;line-height:1.5}
.hrow{display:flex;align-items:center;justify-content:space-between;gap:10px}
.section-title{font-size:12.5px;font-weight:700}

/* ---------------- 三栏骨架 ---------------- */
.app{display:grid;grid-template-columns:288px minmax(0,1fr) 364px;height:calc(100vh - 52px)}
.app>.warning{grid-column:1/-1}
.rail{display:flex;flex-direction:column;min-height:0;background:var(--surface);border-right:1px solid var(--line)}
.stage{display:flex;flex-direction:column;min-width:0;min-height:0}
.claim{display:flex;flex-direction:column;min-height:0;background:var(--surface);border-left:1px solid var(--line)}

/* ---------------- 左:参数清单 ---------------- */
.rail-head{padding:10px 12px 9px;border-bottom:1px solid var(--line);flex:0 0 auto}
.rail-title{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.rail-title span{font-size:10.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.search{width:100%;border:1px solid var(--line);border-radius:var(--r-s);padding:6px 9px;font-size:12px;background:var(--surface-2)}
.search:focus{outline:none;border-color:var(--accent);background:var(--surface)}
.cat-row{display:flex;gap:5px;margin-top:7px}
.cat-row select{flex:1;min-width:0;border:1px solid var(--line);border-radius:var(--r-s);padding:4px 6px;
  font-size:11px;background:var(--surface-2);color:var(--muted)}
.plist{flex:1;overflow-y:auto;min-height:0}
.pitem{width:100%;text-align:left;display:block;border:0;border-left:3px solid transparent;background:transparent;
  padding:7px 10px 7px 9px;border-bottom:1px solid var(--line)}
.pitem:hover{background:var(--surface-2)}
.pitem.active{background:var(--accent-soft);border-left-color:var(--accent)}
.pitem .l1{display:flex;align-items:center;gap:6px}
.pitem .name{font-size:12.5px;font-weight:650;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;min-width:0}
.pitem .pg{font-family:var(--mono);font-size:10px;color:var(--muted);flex:0 0 auto}
.pitem .l2{display:flex;align-items:center;gap:6px;margin-top:2px}
.pitem .val{font-family:var(--mono);font-size:11px;opacity:.82;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;min-width:0}
.pitem .val.missing{color:var(--muted);opacity:.6}
.pitem .st{flex:0 0 auto;font-size:9.5px;font-weight:700;color:var(--muted);display:flex;align-items:center;gap:4px}
.pitem .st i{width:7px;height:7px;border-radius:99px;background:var(--missing);display:inline-block}
.pitem[data-status="PENDING"] .st i{background:var(--warn)}
.pitem[data-status="VERIFIED"] .st i{background:var(--ok)}
.pitem[data-status="CONFLICT"] .st i{background:var(--bad)}
.pitem[data-status="VERIFIED"] .name,.pitem[data-status="CONFLICT"] .name{opacity:.6}

/* ---------------- 中:证据舞台 ---------------- */
.stage-head{display:flex;align-items:center;gap:10px;padding:0 12px;background:var(--surface);
  border-bottom:1px solid var(--line);flex:0 0 auto;min-height:42px}
.tabs{display:flex;gap:2px;flex-wrap:nowrap}
.tab{padding:7px 12px;border:0;border-bottom:2px solid transparent;background:transparent;
  font-size:12.5px;font-weight:650;color:var(--muted);white-space:nowrap}
.tab:hover{color:var(--ink)}
.tab.active{color:var(--accent-ink);border-bottom-color:var(--accent)}
.tools{display:flex;align-items:center;gap:5px;margin-left:auto}
.page-box{width:46px;text-align:center;border:1px solid var(--line);border-radius:var(--r-s);padding:4px 2px;
  font-family:var(--mono);font-size:12px;background:var(--surface-2)}
.page-total{font-family:var(--mono);font-size:11px;color:var(--muted)}
.stage-body{flex:1;min-height:0;position:relative}
#tab-param{position:absolute;inset:0;display:flex;flex-direction:column;min-height:0}
.viewer{flex:1;min-height:0;overflow:auto;background:var(--ground);padding:18px;position:relative}
.pdf-sheet{position:relative;width:max-content;margin:0 auto;box-shadow:0 3px 18px rgba(13,34,48,.16);background:#fff}
.pdf-sheet canvas{display:block}
.overlay{position:absolute;pointer-events:none;border:2px solid var(--hl);background:rgba(240,165,44,.20);border-radius:2px}
.overlay.pulse{animation:hlpulse 1.1s ease-out 1}
@keyframes hlpulse{0%{box-shadow:0 0 0 0 rgba(240,165,44,.5)}100%{box-shadow:0 0 0 14px rgba(240,165,44,0)}}
#hls{position:absolute;inset:0;pointer-events:none}
.hl-m{position:absolute;border:2px dashed var(--hl);background:rgba(240,165,44,.10);border-radius:2px;
  cursor:pointer;pointer-events:auto}
.hl-m:hover{background:rgba(240,165,44,.26)}
.hl-m b{position:absolute;top:-9px;left:-9px;width:17px;height:17px;border-radius:99px;background:var(--hl);
  color:#fff;font-family:var(--mono);font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center}
.empty-pdf{max-width:460px;margin:9% auto;background:var(--surface);padding:26px;text-align:center;
  border:1px dashed var(--line-strong);border-radius:14px;color:var(--muted)}
.empty-pdf .big{font-size:34px;margin-bottom:6px}
.empty-pdf h3{margin:6px 0;font-size:15px;color:var(--ink)}
.empty-pdf p{margin:0;font-size:12px;line-height:1.6}
.evpanel{position:absolute;inset:0;overflow:auto;padding:14px 16px;background:var(--surface)}

/* ---------------- 表格证据 ---------------- */
.tgrid{border-collapse:collapse;font-size:11px;margin:8px 0}
.tgrid td,.tgrid th{border:1px solid var(--line);padding:5px 7px;max-width:230px;overflow-wrap:anywhere}
.tgrid td.selectable{cursor:pointer}
.tgrid td.selectable:hover{background:var(--accent-soft)}
.tgrid td.hit{outline:2px solid var(--hl);background:var(--warn-soft)}
.merged-note{color:var(--warn);font-size:10px}
#table-picker{border:1px solid var(--line);border-radius:var(--r-s);padding:4px 8px;font-size:11.5px;
  background:var(--surface-2);max-width:280px}

/* ---------------- 公式证据 ---------------- */
.formula-card{border:1px solid var(--line);border-radius:var(--r-m);padding:11px;margin-bottom:11px;background:var(--surface-2)}
.formula-card img{max-width:100%;border:1px solid var(--line);border-radius:var(--r-s);background:#fff}
.formula-card .mono{font-family:var(--mono);font-size:11.5px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--r-s);padding:7px 9px;overflow-wrap:anywhere;white-space:pre-wrap;margin-top:7px}
.checks{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}
.check{font-size:10.5px;border-radius:99px;padding:2px 8px;background:var(--missing-soft);color:var(--muted);border:1px solid var(--line)}
.check.bad{background:var(--bad-soft);color:var(--bad);border-color:transparent}
.check.warn{background:var(--warn-soft);color:var(--warn);border-color:transparent}
.review-bottom{display:flex;flex-wrap:wrap;gap:7px;margin-top:10px;align-items:center}

/* ---------------- 曲线标定 ---------------- */
.curve-card{border:1px solid var(--line);border-radius:var(--r-m);padding:11px;margin-bottom:13px;background:var(--surface-2)}
.curve-canvas{max-width:100%;border:1px solid var(--line);border-radius:var(--r-s);cursor:crosshair;background:#fff}
.cal-steps{display:flex;gap:8px;flex-wrap:wrap;margin-top:7px;font-size:12px;align-items:center}
.cal-pt{border:1px dashed var(--line-strong);border-radius:var(--r-s);padding:4px 8px;background:var(--surface)}
.cal-pt b{color:var(--accent-ink)}
.preview-canvas{border:1px solid var(--line);border-radius:var(--r-s);background:#fff;max-width:100%}

/* ---------------- 右:判定卡 ---------------- */
.claim-head{display:flex;align-items:center;gap:8px;padding:9px 14px;border-bottom:1px solid var(--line);flex:0 0 auto}
#claim-body{flex:1;min-height:0;overflow-y:auto}
.c-sec{padding:10px 14px;border-bottom:1px solid var(--line)}
.c-sec:last-child{border-bottom:0}
.c-name{font-size:15px;font-weight:700;line-height:1.3;text-wrap:balance}
.c-pb{font-family:var(--mono);font-size:10.5px;color:var(--muted);margin-top:3px;overflow-wrap:anywhere}
.c-sub{width:100%;border:0;background:transparent;font-family:var(--mono);font-size:10.5px;color:var(--muted);padding:2px 0}
.c-top{display:flex;align-items:center;gap:6px;margin-bottom:6px;flex-wrap:wrap}
.vrow{display:flex;align-items:baseline;gap:8px}
.v-big{font-family:var(--mono);font-size:20px;font-weight:600;border:0;border-bottom:1px dashed transparent;
  background:transparent;padding:0 0 2px;width:100%;min-width:0}
.v-big:hover{border-bottom-color:var(--line-strong)}
.v-big:focus{outline:none;border-bottom-color:var(--accent)}
.v-unit{font-family:var(--mono);font-size:12px;color:var(--muted);border:0;border-bottom:1px dashed transparent;
  background:transparent;width:88px;flex:0 0 auto;text-align:right}
.v-unit:hover,.v-unit:focus{border-bottom-color:var(--line-strong);outline:none}
.mgrid{display:grid;grid-template-columns:auto 1fr;gap:5px 12px;font-size:11.5px;margin:0;align-items:center}
.mgrid dt{color:var(--muted);white-space:nowrap}
.mgrid dd{margin:0}
.mgrid select,.mgrid input{border:1px solid var(--line);border-radius:var(--r-s);padding:3px 6px;
  font-size:11.5px;background:var(--surface-2);width:100%}
.mgrid input[type=number]{font-family:var(--mono);width:78px}
.quote{font-size:12px;line-height:1.55;background:var(--surface-2);border-left:3px solid var(--line-strong);
  padding:7px 10px;border-radius:0 var(--r-s) var(--r-s) 0;overflow-wrap:anywhere;max-height:132px;overflow-y:auto}
#edit-quote,#edit-note{width:100%;border:1px solid var(--line);border-radius:var(--r-s);padding:6px 9px;
  font-size:11.5px;background:var(--surface-2);resize:vertical;min-height:52px;font-family:inherit}
#edit-quote:focus,#edit-note:focus{outline:none;border-color:var(--accent);background:var(--surface)}
.warnline{display:flex;gap:7px;align-items:flex-start;font-size:11px;color:var(--warn);background:var(--warn-soft);
  border-radius:var(--r-s);padding:7px 10px;line-height:1.45;margin-top:8px}
.claim .actions{display:flex;gap:6px;padding:10px 14px;border-top:1px solid var(--line);flex:0 0 auto;flex-wrap:wrap}
.claim .actions .btn{flex:1;padding:8px 6px;font-size:12px;min-width:76px}

dialog{border:1px solid var(--line-strong);border-radius:12px;padding:20px;max-width:460px;
  box-shadow:0 12px 40px rgba(22,50,74,.3);background:var(--surface);color:var(--ink)}
dialog::backdrop{background:rgba(16,38,58,.72)}
dialog textarea{border:1px solid var(--line);border-radius:var(--r-s);padding:7px;background:var(--surface-2);
  font-family:inherit;font-size:12px;resize:vertical}
.toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(8px);background:var(--ink);
  color:var(--ground);border-radius:var(--r-s);padding:8px 15px;font-size:12px;font-weight:600;opacity:0;
  pointer-events:none;transition:opacity .18s,transform .18s;z-index:90}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
@media (prefers-reduced-motion: reduce){*{animation:none!important;transition:none!important}}

@media (max-width:1240px){
  .app{grid-template-columns:250px minmax(0,1fr) 320px}
}
@media (max-width:1020px){
  body{overflow:auto}
  .app{grid-template-columns:1fr;height:auto}
  .rail{height:340px;border-right:0;border-bottom:1px solid var(--line)}
  .stage{height:70vh}
  .claim{border-left:0;border-top:1px solid var(--line)}
  #claim-body{overflow:visible}
}
"""

# ------------------------------------------------------------------ 新 body
BODY = r"""
<body>
<header class="top">
  <div class="brand">
    <b>⚗ DFN / P2D 参数证据审核</b>
    <span id="doc-title">示例文献</span>
  </div>
  <div class="stats">
    <span class="stat pend">待审 <b id="pending">0</b></span>
    <span class="stat ok">已确认 <b id="verified">0</b></span>
    <span class="stat bad">冲突/缺失 <b id="issues">0</b></span>
    <span class="stat">/ <b id="total">0</b></span>
    <div class="progress"><div id="progressbar" style="width:0%"></div></div>
  </div>
  <div class="actions">
    <span class="docid">ID <b id="doc-id">DEMO</b></span>
    <span class="docid" id="file-status">未加载 PDF</span>
    <span class="docid" title="PDF SHA-256">SHA <b id="doc-sha">—</b></span>
    <label class="btn ghost sm" for="json-input">导入 JSON</label><input type="file" id="json-input" accept="application/json,.json">
    <label class="btn ghost sm" for="pdf-input">本地 PDF</label><input type="file" id="pdf-input" accept="application/pdf,.pdf">
    <button class="btn ghost sm" id="clear-cache">清缓存</button>
    <button class="btn primary sm" id="export-btn">导出审核 JSON ↗</button>
    <button class="btn ghost sm" id="theme-btn" title="明暗主题">◐</button>
  </div>
</header>

<main class="app">
  <div class="warning" id="demo-warning">演示数据仅验证交互逻辑。正式流程用 <code>build_review_page.py</code> 生成内联数据的审核页，或在此导入 review_ready JSON + 原始 PDF。所有审核动作仅存于本机，请及时导出。</div>

  <!-- ========== 左:参数审核清单 ========== -->
  <aside class="rail">
    <div class="rail-head">
      <div class="rail-title"><b>① 参数审核清单</b><span id="count-info">0 项</span></div>
      <input id="search" class="search" placeholder="搜索 名称 / 标识符 / 单位…">
      <div class="cat-row">
        <select id="group-filter"><option value="all">全部类别</option></select>
        <select id="status-filter">
          <option value="all">全部状态</option><option value="PENDING">待审核</option><option value="VERIFIED">已确认</option>
          <option value="CONFLICT">有冲突</option><option value="MISSING">未找到</option><option value="DERIVED">推导待核实</option>
        </select>
      </div>
    </div>
    <div class="plist" id="table-body"></div>
    <div class="hint">点击参数 → 中栏证据 / 右栏判定。快捷键：↑↓ 切换 · <b>Enter</b> 确认 · <b>C</b> 冲突 · <b>[ ]</b> 翻页</div>
  </aside>

  <!-- ========== 中:证据舞台 ========== -->
  <section class="stage">
    <div class="stage-head">
      <div class="tabs" id="tabs">
        <div class="tab active" data-tab="param">PDF 原文</div>
        <div class="tab" data-tab="table">表格证据</div>
        <div class="tab" data-tab="formula">公式证据</div>
        <div class="tab" data-tab="curve">曲线标定</div>
      </div>
      <div class="tools">
        <button class="btn icon ghost" id="prev-page" title="上一页 [">‹</button>
        <input id="page-input" class="page-box" type="number" min="1" value="1"><span class="page-total" id="page-total">/ —</span>
        <button class="btn icon ghost" id="next-page" title="下一页 ]">›</button>
        <button class="btn icon ghost" id="zoom-out">−</button><span class="page-total" id="zoom-label">125%</span><button class="btn icon ghost" id="zoom-in">＋</button>
        <button class="btn ghost sm" id="locate">◎ 定位证据</button>
      </div>
    </div>
    <div class="stage-body">
      <!-- PDF 原文 -->
      <div id="tab-param">
        <div class="viewer" id="viewer">
          <div class="empty-pdf" id="empty-pdf">
            <div class="big">📄</div><h3>加载论文 PDF</h3>
            <p>内联数据页会自动加载 PDF；否则请手动选择本地 PDF 文件。</p>
          </div>
          <div class="pdf-sheet" id="sheet" hidden>
            <canvas id="pdf-canvas"></canvas>
            <div id="hls"></div>
            <div id="overlay" class="overlay" hidden></div>
          </div>
        </div>
      </div>
      <!-- 表格证据 -->
      <div id="tab-table" class="evpanel" hidden>
        <div class="hrow" style="margin-bottom:8px">
          <div class="section-title">结构化表格证据（Docling + PyMuPDF）</div>
          <select id="table-picker"></select>
        </div>
        <div class="notice">点击单元格 → 将 <b>单元格文本 + 页码 + bbox</b> 作为当前参数的证据写入右栏（PDF 会高亮该单元格）。合并单元格标有 ⧉。</div>
        <div id="table-view"></div>
        <div class="footnote" id="table-meta"></div>
      </div>
      <!-- 公式证据 -->
      <div id="tab-formula" class="evpanel" hidden>
        <div class="hrow" style="margin-bottom:8px">
          <div class="section-title">科学公式证据（视觉重建 + SymPy）</div>
          <span class="small" id="formula-summary"></span>
        </div>
        <div class="notice">扫描截图中重建的公式由 Agent 填写 sympy 表达式，SymPy 校验解析/变量/数值/量纲。<b>VALIDATED 只代表数学自洽</b>，与论文一致需人工核对截图后点击“核对无误”。</div>
        <div id="formula-view"></div>
      </div>
      <!-- 曲线标定 -->
      <div id="tab-curve" class="evpanel" hidden>
        <div class="hrow" style="margin-bottom:8px">
          <div class="section-title">科研曲线数字化（WebPlotDigitizer 思路）</div>
          <span class="small" id="curve-summary"></span>
        </div>
        <div class="notice">在图上点击轴参考点（每轴 ≥2 个已知刻度），输入对应数值 → 预览换算曲线 → 确认后生成 CSV 并可绑定到当前函数参数（如 OCP）。人工点击是标定生效的唯一途径。</div>
        <div id="curve-view"></div>
      </div>
    </div>
  </section>

  <!-- ========== 右:当前参数判定 ========== -->
  <aside class="claim">
    <div class="claim-head">
      <span class="chip pending" id="editing-status">待审核</span>
      <span class="grow"></span>
      <span class="small">③ 当前参数判定</span>
    </div>
    <div id="claim-body">
      <div class="c-sec">
        <div class="c-top" id="c-top"></div>
        <div class="c-name" id="c-name">—</div>
        <div class="c-pb" id="c-pb"></div>
        <input class="c-sub" id="edit-name" readonly title="内部标识符">
      </div>
      <div class="c-sec">
        <div class="label" style="margin-bottom:5px">审核后的值（常数 / expr://sym:… / data://curve:…）</div>
        <div class="vrow">
          <input class="v-big" id="edit-value" placeholder="5.22e-6">
          <input class="v-unit" id="edit-unit" placeholder="单位">
        </div>
      </div>
      <div class="c-sec">
        <dl class="mgrid">
          <dt>证据类别</dt><dd><select id="edit-source">
            <option value="PAPER">论文直接报告</option><option value="DERIVED">论文数据推导</option>
            <option value="CITED">引用文献</option><option value="EXTERNAL">外部参数集</option>
            <option value="UNKNOWN">待查证</option></select></dd>
          <dt>状态</dt><dd><select id="edit-status">
            <option value="PENDING">待审核</option><option value="VERIFIED">已确认</option>
            <option value="CONFLICT">有冲突</option><option value="MISSING">未找到</option>
            <option value="DERIVED">待核实推导</option></select></dd>
          <dt>证据页</dt><dd><input id="edit-page" type="number" min="1" placeholder="页码"></dd>
        </dl>
        <div class="citation" id="evidence-desc"></div>
        <div class="citation" id="cand-list" hidden></div>
      </div>
      <div class="c-sec">
        <div class="label" style="margin-bottom:5px">原文引用</div>
        <div class="quote" id="quote-view">—</div>
        <textarea id="edit-quote" placeholder="原文片段 / 表格单元格 / 公式引用" style="margin-top:7px"></textarea>
      </div>
      <div class="c-sec">
        <div class="label" style="margin-bottom:5px">审核备注（修订原因 / 疑点 / 适用范围）</div>
        <textarea id="edit-note"></textarea>
      </div>
      <div class="c-sec">
        <div class="footnote">定位框仅显示已确认的真实 bbox_norm；无坐标时只跳页。reviewed_* 与 extracted_* 独立存储，不覆盖文献原始记录。<b>VERIFIED 只能由人工点击赋予。</b></div>
      </div>
    </div>
    <div class="actions">
      <button class="btn ok" id="verify">✓ 确认<span class="kbd">⏎</span></button>
      <button class="btn bad" id="flag">⚑ 冲突<span class="kbd">C</span></button>
      <button class="btn ghost" id="verify-next">确认并下一条 →</button>
      <button class="btn ghost" id="save">保存</button>
      <button class="btn ghost" id="reset">恢复提取值</button>
    </div>
  </aside>
</main>
"""

# ------------------------------------------------------------------ JS 补丁
PATCHES = [
    # 1) 类别显示名 + 配色
    (
        "const chip = (s, extra='') =>",
        """const CAT_INFO = {
  geometry_structure:{zh:'几何结构', c:'var(--cat-geo)'}, solid_transport:{zh:'固相输运', c:'var(--cat-solid)'},
  electrolyte:{zh:'电解液', c:'var(--cat-elyte)'}, kinetics_ocp:{zh:'动力学 / OCP', c:'var(--cat-kin)'},
  initial_conditions:{zh:'初始条件', c:'var(--cat-init)'}, operating_conditions:{zh:'工况', c:'var(--cat-op)'},
};
const CAT_ALIAS = {'几何':'几何结构','几何结构':'几何结构','颗粒':'颗粒','热力学':'热力学','电解液':'电解液','动力学':'动力学'};
function catInfo(cat){
  if (CAT_INFO[cat]) return CAT_INFO[cat];
  if (CAT_ALIAS[cat]) return {zh:CAT_ALIAS[cat], c:'var(--cat-geo)'};
  let h=0; for (const ch of String(cat)) h=(h*31+ch.charCodeAt(0))%360;
  return {zh:cat, c:`hsl(${h} 42% 46%)`};
}
const chip = (s, extra='') =>""",
    ),
    # 2) 列表渲染 → demoA 卡片式
    (
        """  $('count-info').textContent = `显示 ${filtered.length} / ${data.parameters.length}`;
  $('table-body').innerHTML = filtered.map(p => {
    const v = p.reviewed_value ?? p.value;
    const evTag = p.table_ref?'TableCell':p.formula_ref?'Formula':p.curve_binding?'CurveData':(p.evidence.location_type||'');
    return `<tr data-id="${esc(p.id)}" class="${selectedId===p.id?'active':''}">
      <td><div class="pname">${esc(p.name_zh)}</div><div class="pkey">${esc(p.id)} · ${esc(evTag)}</div></td>
      <td class="val ${v==null?'missing':''}">${v==null?'—':esc(v)} <span class="small">${esc(p.reviewed_unit??p.unit)}</span></td>
      <td>${esc(p.source_type)}</td><td>${p.evidence?.page??'—'}</td><td>${chip(p.review_status)}</td></tr>`;
  }).join('') || '<tr><td colspan="5" class="small">没有符合筛选条件的参数</td></tr>';
  $('table-body').querySelectorAll('tr[data-id]').forEach(tr => tr.addEventListener('click', ()=>select(tr.dataset.id)));""",
        """  $('count-info').textContent = `显示 ${filtered.length} / ${data.parameters.length}`;
  const stDot = {PENDING:'var(--warn)', VERIFIED:'var(--ok)', CONFLICT:'var(--bad)', MISSING:'var(--missing)', DERIVED:'var(--accent)'};
  $('table-body').innerHTML = filtered.map(p => {
    const v = p.reviewed_value ?? p.value;
    const ci = catInfo(p.category);
    return `<button class="pitem ${selectedId===p.id?'active':''}" data-id="${esc(p.id)}" data-status="${esc(p.review_status)}">
      <span class="l1"><span class="dot" style="background:${ci.c}"></span>
        <span class="name">${esc(p.name_zh||p.name_en||p.id)}</span>
        <span class="pg">${p.evidence?.page?'p'+p.evidence.page:'—'}</span></span>
      <span class="l2"><span class="val ${v==null?'missing':''}">${v==null?'—':esc(typeof v==='string'&&v.length>26?v.slice(0,26)+'…':v)} ${esc(p.reviewed_unit??p.unit)}</span>
        <span class="st"><i style="background:${stDot[p.review_status]||'var(--missing)'}"></i>${esc(labels[p.review_status]||p.review_status)}</span></span>
    </button>`;
  }).join('') || '<div class="small" style="padding:16px">没有符合筛选条件的参数</div>';
  $('table-body').querySelectorAll('.pitem[data-id]').forEach(el => el.addEventListener('click', ()=>select(el.dataset.id)));""",
    ),
    # 3) 类别下拉用显示名
    (
        """  const cats=[...new Set(ps.map(p=>p.category))];
  const prev=$('group-filter').value;
  $('group-filter').innerHTML = '<option value="all">全部类别</option>'+cats.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');""",
        """  const cats=[...new Set(ps.map(p=>p.category))];
  const prev=$('group-filter').value;
  $('group-filter').innerHTML = '<option value="all">全部类别</option>'+cats.map(c=>`<option value="${esc(c)}">${esc(catInfo(c).zh)}</option>`).join('');""",
    ),
    # 4) select() 补：刷新右栏名称/类别/引用/候选框
    (
        """  renderTable();
  tab==='param' ? locate() : null;
}""",
        """  // —— 右栏展示位（demoA 版式）
  $('c-name').textContent = p.name_en || p.name_zh || p.id;
  $('c-pb').textContent = p.pybamm_name || '';
  $('edit-name').value = p.id;
  const ci = catInfo(p.category);
  $('c-top').innerHTML = `<span class="dot" style="background:${ci.c}"></span>
    <span class="small">${esc(ci.zh)}</span>
    ${p.source_type!=='PAPER'?`<span class="chip derived">${esc(p.source_type)}</span>`:''}`;
  const qv = $('quote-view');
  qv.innerHTML = p.evidence?.quote ? esc(p.evidence.quote) : '<span style="color:var(--muted)">（无引用文本）</span>';
  renderTable();
  drawCandidates(p);
  tab==='param' ? locate() : null;
}

/* 多义候选：在页面上画出编号虚线框，点选即采纳为定位 */
function drawCandidates(p){
  const box = $('hls'); if(!box) return;
  box.innerHTML = '';
  const cand = (p.evidence?.location_candidates||[]).filter(c=>c.bbox_norm && c.page===currentPage);
  if (p.evidence?.bbox_norm || cand.length < 2) return;
  cand.forEach((c,i)=>{
    const b = c.bbox_norm, el = document.createElement('div');
    el.className = 'hl-m';
    el.style.left=(b[0]*100)+'%'; el.style.top=(b[1]*100)+'%';
    el.style.width=((b[2]-b[0])*100)+'%'; el.style.height=((b[3]-b[1])*100)+'%';
    el.title = `候选 ${i+1} · p${c.page} · 点击采纳为定位`;
    el.innerHTML = `<b>${i+1}</b>`;
    el.onclick = () => {
      p.evidence.bbox_norm = b;
      overlayBox = b;
      showHighlight(); drawCandidates(p); saveCache();
      $('evidence-desc').textContent = `定位：第 ${c.page} 页 · 已采纳候选 ${i+1} 的坐标`;
    };
    box.appendChild(el);
  });
}""",
    ),
    # 5) showHighlight 支持候选框重绘（换页后）
    (
        """  el.hidden=false; el.scrollIntoView({behavior:'smooth',block:'center'});
}""",
        """  el.hidden=false;
  el.classList.remove('pulse'); void el.offsetWidth; el.classList.add('pulse');
  el.scrollIntoView({behavior:'smooth',block:'center'});
  const sp = selected(); if (sp && tab==='param') drawCandidates(sp);
}""",
    ),
    # 6) 键盘：补翻页;主题按钮
    (
        """  if (e.key==='c' || e.key==='C'){ save('CONFLICT'); }
});""",
        """  if (e.key==='c' || e.key==='C'){ save('CONFLICT'); }
  if (e.key==='['){ e.preventDefault(); jump(currentPage-1); }
  if (e.key===']'){ e.preventDefault(); jump(currentPage+1); }
});
$('theme-btn').onclick = () => {
  const cur = document.documentElement.dataset.theme ||
    (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const nx = cur==='dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = nx;
  try{ localStorage.setItem('p2d_theme', nx); }catch(e){}
};
try{ const t = localStorage.getItem('p2d_theme'); if (t) document.documentElement.dataset.theme = t; }catch(e){}""",
    ),
    # 7) 每次换页重画候选框
    (
        """  $('page-input').value = currentPage;
  $('zoom-label').textContent = Math.round(scale*100)+'%';
  showHighlight();""",
        """  $('page-input').value = currentPage;
  $('zoom-label').textContent = Math.round(scale*100)+'%';
  const sp = selected(); if (sp) drawCandidates(sp);
  showHighlight();""",
    ),
    # 8) 修复:boot() 同步执行时 pdf.js(CDN,排在后面)尚未就绪,内联 PDF 永远加载失败。
    #    改为显式等待 pdfjsLib 就绪,pdf.js 脚本移入 <head defer>。
    (
        """/* ================= PDF viewer ================= */
async function loadPdfBase64(b64){
  try{
    if(!window.pdfjsLib) throw Error('PDF.js 未加载（需要联网加载 CDN，或将 pdf.min.js 放到本页同目录）。');
    const bin = atob(b64); const bytes = new Uint8Array(bin.length);
    for(let i=0;i<bin.length;i++) bytes[i]=bin.charCodeAt(i);
    pdf = await window.pdfjsLib.getDocument({data:bytes}).promise;
    afterPdfLoad('(内联 PDF)');
  }catch(ex){ alert('内联 PDF 加载失败：'+ex.message); }
}
$('pdf-input').onchange = async e => {
  const file = e.target.files?.[0]; if(!file) return;
  try{
    if(!window.pdfjsLib) throw Error('PDF.js 未加载。检查联网或本地部署 pdf.min.js。');
    pdf = await window.pdfjsLib.getDocument({data:new Uint8Array(await file.arrayBuffer())}).promise;
    afterPdfLoad(file.name);
  }catch(ex){ alert('PDF 加载失败：'+ex.message); }
};""",
        """/* ================= PDF viewer ================= */
/* pdf.js 由 CDN 异步加载,可能在 boot() 之后才就绪 —— 显式等待,不靠脚本先后顺序。 */
function whenPdfjs(timeoutMs = 20000){
  if (window.pdfjsLib) return Promise.resolve(window.pdfjsLib);
  if (window.__pdfjsWait) return window.__pdfjsWait;
  window.__pdfjsWait = new Promise((resolve, reject) => {
    const t0 = Date.now();
    const iv = setInterval(() => {
      if (window.pdfjsLib){ clearInterval(iv); resolve(window.pdfjsLib); }
      else if (Date.now()-t0 > timeoutMs){
        clearInterval(iv); window.__pdfjsWait = null;
        reject(Error('PDF.js 加载超时。本页需要联网从 CDN 取 pdf.js，离线时请把 pdf.min.js / pdf.worker.min.js 放到本页同目录，并把 <head> 里的 CDN 地址改成相对路径。'));
      }
    }, 120);
  });
  return window.__pdfjsWait;
}
function pdfStatus(msg, bad){
  const el = $('file-status'); if(!el) return;
  el.textContent = msg; el.style.color = bad ? 'var(--bad)' : '';
}
async function loadPdfBase64(b64){
  try{
    pdfStatus('PDF.js 加载中…');
    const lib = await whenPdfjs();
    const bin = atob(b64); const bytes = new Uint8Array(bin.length);
    for(let i=0;i<bin.length;i++) bytes[i]=bin.charCodeAt(i);
    pdf = await lib.getDocument({data:bytes}).promise;
    afterPdfLoad('(内联 PDF)');
  }catch(ex){
    pdfStatus('内联 PDF 失败：' + ex.message, true);
    alert('内联 PDF 加载失败：' + ex.message);
  }
}
$('pdf-input').onchange = async e => {
  const file = e.target.files?.[0]; if(!file) return;
  try{
    pdfStatus('PDF.js 加载中…');
    const lib = await whenPdfjs();
    pdf = await lib.getDocument({data:new Uint8Array(await file.arrayBuffer())}).promise;
    afterPdfLoad(file.name);
  }catch(ex){
    pdfStatus('PDF 失败：' + ex.message, true);
    alert('PDF 加载失败：' + ex.message);
  }
};""",
    ),
    # 9) file-status 由 afterPdfLoad 正常写入
    (
        """function afterPdfLoad(name){
  currentPage = 1;
  $('file-status').textContent = `${name} · ${pdf.numPages} 页`;""",
        """function afterPdfLoad(name){
  currentPage = 1;
  pdfStatus(`${name} · ${pdf.numPages} 页`);""",
    ),
    # 10) 科学计数法显示:7.56e-05 不能变成 0.0000756 —— 审核时极易抄错
    (
        """const clone = o => JSON.parse(JSON.stringify(o));""",
        """const clone = o => JSON.parse(JSON.stringify(o));
/* 论文量级的值一律科学计数法显示,避免 7.56e-05 摊成 0.0000756 而抄错 */
function fmtNum(v){
  const n = Number(v);
  if (v === null || v === undefined || v === '' || Number.isNaN(n)) return v==null?'':String(v);
  if (n === 0) return '0';
  const a = Math.abs(n);
  if (a < 1e-3 || a >= 1e5){
    const exp = Math.floor(Math.log10(a));
    const mant = n / Math.pow(10, exp);
    return String(parseFloat(mant.toPrecision(4))) + 'e' + exp;
  }
  return String(parseFloat(n.toPrecision(6)));
}
function fmtVal(p){
  const v = p.reviewed_value ?? p.value;
  if (typeof v === 'string') return v;
  return fmtNum(v);
}""",
    ),
    # 11) 列表值用科学计数法;名称优先取英文全称(name_zh 常与 id 重复)
    (
        """      <span class="l2"><span class="val ${v==null?'missing':''}">${v==null?'—':esc(typeof v==='string'&&v.length>26?v.slice(0,26)+'…':v)} ${esc(p.reviewed_unit??p.unit)}</span>""",
        """      <span class="l2"><span class="val ${v==null?'missing':''}">${v==null?'—':esc(fmtVal(p).length>26?fmtVal(p).slice(0,26)+'…':fmtVal(p))} ${esc(p.reviewed_unit??p.unit)}</span>""",
    ),
    (
        """        <span class="name">${esc(p.name_zh||p.name_en||p.id)}</span>""",
        """        <span class="name">${esc(displayName(p))}</span>""",
    ),
    (
        """  $('count-info').textContent = `显示 ${filtered.length} / ${data.parameters.length}`;
  const stDot =""",
        """  $('count-info').textContent = `显示 ${filtered.length} / ${data.parameters.length}`;
  const stDot =""",
    ),
    # 12) 右栏值输入框也用科学计数法;select() 填入
    (
        """  $('edit-value').value = p.reviewed_value ?? p.value ?? '';""",
        """  $('edit-value').value = fmtVal(p);""",
    ),
    # 13) displayName 辅助函数(名称优先英文全称,退化到中文名/id)
    (
        """function catInfo(cat){""",
        """function displayName(p){
  const zh = String(p.name_zh||''), en = String(p.name_en||''), id = String(p.id||'');
  if (zh && zh !== id) return zh;
  if (en && en !== id) return en;
  return zh || en || id;
}
function catInfo(cat){""",
    ),
]

# pdf.js 的 <script src> 原本排在 boot() 之后,移入 <head> 并加 defer
PDFJS_TAG = re.compile(
    r'<script src="(https://cdnjs\.cloudflare\.com/ajax/libs/pdf\.js/[^"]+)"([^>]*)></script>')


def splice(html, new_style, new_body):
    # 整块替换 <style>…</style>
    html = re.sub(r'<style>.*?</style>', lambda m: '<style>' + new_style + '</style>', html, count=1, flags=re.S)
    # head 切到 <body> 之前(不含 <body>),tail 从 <script> 起(含收尾的 </body></html>)
    start = html.index('<body>')
    end = html.index("<script>\n'use strict';")
    head = html[:start]
    tail = html[end:]
    dialog_start = html.index('<dialog id="gate-dialog">', start, end)
    dialog = html[dialog_start:end].rstrip()
    out = head + new_body.strip() + '\n\n' + dialog + '\n\n' + tail
    # pdf.js 提到 <head> 并 defer:与内联脚本并行下载,不再阻塞,也不再依赖先后顺序
    m = PDFJS_TAG.search(out)
    if m:
        tag = f'<script defer src="{m.group(1)}"{m.group(2)}></script>'
        out = out[:m.start()] + out[m.end():]
        out = out.replace('</head>', '  ' + tag + '\n</head>', 1)
    return out


def main():
    dry = '--dry-run' in sys.argv
    src = BAK.read_text(encoding='utf-8') if BAK.exists() else TPL.read_text(encoding='utf-8')
    if not BAK.exists() and not dry:
        shutil.copy2(TPL, BAK)
        print('backup ->', BAK.name)

    out = splice(src, STYLE, BODY)

    missing = []
    for old, new in PATCHES:
        if old not in out:
            missing.append(old[:52].replace('\n', '⏎'))
            continue
        out = out.replace(old, new, 1)
    if missing:
        print('!! 以下补丁锚点未命中（模板可能已改动）：')
        for m in missing:
            print('   -', m)
        sys.exit(1)

    # 校验：JS 引用的 id 必须都在新 body 里
    ids = set(re.findall(r"\$\('([a-z0-9-]+)'\)", out))
    body_only = out[out.index('<body>'):out.index("<script>\n'use strict';")]
    absent = sorted(i for i in ids if f'id="{i}"' not in body_only and f"id='{i}'" not in body_only)
    if absent:
        print('!! 新 body 缺少 JS 引用的元素 id:', absent)
        sys.exit(1)

    if dry:
        print('dry-run ok — style %d chars, body %d chars, %d patches' % (len(STYLE), len(BODY), len(PATCHES)))
        return
    TPL.write_text(out, encoding='utf-8')
    print('ported ->', TPL.relative_to(ROOT), f'({len(out)} bytes)')


if __name__ == '__main__':
    main()
