# -*- coding: utf-8 -*-
"""生成三个版式 demo:A 三栏主审 / B 沉浸聚焦 / C 双轨对照。
共享内核在 common.py;本文件只放各版式的布局 CSS、body 结构与少量布局专属 JS。
运行:python3 build_demos.py
"""
from common import html, LIST_RAIL, STAGE, CLAIM_COL
import os

HERE = os.path.dirname(os.path.abspath(__file__))

def spec_div(name, lines):
    return ('<div class="spec" id="spec">'
            '<button class="x" onclick="document.getElementById(\'spec\').remove()">✕</button>'
            f'<b>{name}</b>{lines}</div>')

# ================================================================ A 三栏主审
CSS_A = """
.app{display:grid;grid-template-columns:276px minmax(0,1fr) 356px;height:calc(100vh - 52px)}
.rail{border-right:1px solid var(--line)}
.claim{border-left:1px solid var(--line);flex:1;min-height:0}
"""

BODY_A = '<main class="app">' + LIST_RAIL + STAGE + CLAIM_COL + '</main>'

JS_A = """
document.getElementById('layout-tag').textContent = '方案 A · 三栏主审式 — 证据满高居中，声称窄列常驻';
bindToolbar(); renderList(); renderStats(); select(0);
"""

# ================================================================ B 沉浸聚焦
CSS_B = """
.app{position:relative;height:calc(100vh - 52px)}
.stage{position:absolute;inset:0}

/* 左缘常驻轨：类别上下文 + 抽屉开关 */
.edge{position:fixed;left:0;top:52px;bottom:0;width:44px;background:var(--surface);border-right:1px solid var(--line);
  display:flex;flex-direction:column;align-items:center;gap:10px;padding:12px 0;z-index:30}
.edge button{border:0;background:none;padding:4px;border-radius:var(--r-s);display:flex;color:var(--muted);font-size:15px}
.edge button:hover{background:var(--surface-2);color:var(--ink)}
.edge .dot{cursor:pointer;opacity:.45;transition:opacity .15s,transform .15s}
.edge .dot:hover{opacity:1;transform:scale(1.25)}
.edge .dot.on{opacity:1;outline:2px solid var(--ink);outline-offset:2px}
.edge .spacer{flex:1}

/* 列表抽屉 */
.drawer{position:fixed;left:44px;top:52px;bottom:0;width:308px;background:var(--surface);z-index:50;
  border-right:1px solid var(--line);box-shadow:var(--shadow-float);transform:translateX(calc(-100% - 44px));
  transition:transform .22s ease}
.drawer.open{transform:translateX(0)}
.drawer .rail{height:100%}

/* 声称 HUD */
.hud{position:fixed;right:16px;bottom:16px;width:368px;max-height:min(72vh,660px);display:flex;flex-direction:column;
  background:var(--surface);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow-float);z-index:40;overflow:hidden}
.hud-head{display:flex;align-items:center;gap:8px;padding:9px 12px;border-bottom:1px solid var(--line);flex:0 0 auto;cursor:pointer}
.hud-head .t{font-size:10px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:var(--muted);flex:1}
.hud.collapsed .hud-head{border-bottom:0}
.hud.collapsed #claim-body,.hud.collapsed .actions{display:none}
.hud .actions{border-radius:0 0 12px 12px}
"""

BODY_B = """
<div class="app">
  """ + STAGE.replace('↑↓ 切换 · Enter 确认 · C 冲突', 'L 清单 · ↑↓ 切换 · ⏎ 确认 · C 冲突') + """
</div>
<aside class="edge">
  <button id="drawer-toggle" title="参数清单 (L)">☰</button>
  <div id="edge-cats" style="display:flex;flex-direction:column;gap:10px;margin-top:4px"></div>
  <div class="spacer"></div>
  <div id="edge-progress" style="writing-mode:vertical-rl;font-family:var(--mono);font-size:9.5px;color:var(--muted);letter-spacing:1px"></div>
</aside>
<aside class="drawer" id="drawer">""" + LIST_RAIL + """</aside>
<aside class="hud" id="hud">
  <div class="hud-head" id="hud-head">
    <span class="t">当前参数 · 审核</span>
    <span class="page-total mono" id="hud-pos"></span>
    <button class="btn icon ghost" id="hud-toggle" title="收起 / 展开 (H)">▾</button>
  </div>
  <div id="claim-body"></div>
  <div class="actions">
    <button class="btn ok" id="verify">✓ 确认<span class="kbd">⏎</span></button>
    <button class="btn bad" id="flag">⚑ 冲突<span class="kbd">C</span></button>
    <button class="btn ghost" id="missing">⊘ 未找到</button>
  </div>
</aside>
"""

JS_B = r"""
document.getElementById('layout-tag').textContent = '方案 B · 沉浸聚焦式 — 证据占满全窗，审核要素浮动按需出现';

const drawer = document.getElementById('drawer');
const hud = document.getElementById('hud');
window.toggleDrawer = () => drawer.classList.toggle('open');
window.closeDrawer  = () => drawer.classList.remove('open');
window.toggleHud    = () => {
  hud.classList.toggle('collapsed');
  document.getElementById('hud-toggle').textContent = hud.classList.contains('collapsed') ? '▴' : '▾';
};
document.getElementById('drawer-toggle').addEventListener('click', toggleDrawer);
document.getElementById('hud-head').addEventListener('click', e=>{
  if (e.target.id!=='hud-toggle') toggleHud();
});
document.getElementById('hud-toggle').addEventListener('click', toggleHud);
document.addEventListener('keydown', e=>{
  if (e.key==='Escape') closeDrawer();
  if (e.key==='h'||e.key==='H') toggleHud();
});

/* 左缘类别点 = 分类筛选 */
const ec = document.getElementById('edge-cats');
Object.entries(CATS).forEach(([k,c])=>{
  const d = document.createElement('span');
  d.className='dot'; d.style.background=c.c; d.title=c.zh; d.dataset.cat=k;
  d.addEventListener('click', ()=>{
    state.filter.cat = state.filter.cat===k ? 'all' : k;
    ec.querySelectorAll('.dot').forEach(x=>x.classList.toggle('on', x.dataset.cat===state.filter.cat));
    renderList(); syncActive();
  });
  ec.appendChild(d);
});

/* HUD 位置指示 + 统计挂钩 */
const _renderStats = renderStats;
renderStats = function(){
  _renderStats();
  const done = state.items.filter(p=>p.status!=='PENDING').length;
  document.getElementById('edge-progress').textContent = done + '/' + state.items.length;
};
const _renderClaim = renderClaim;
renderClaim = function(){
  _renderClaim();
  const p = state.items[state.cur];
  document.getElementById('hud-pos').textContent = (state.cur+1) + '/' + state.items.length + ' · p' + (p.pg??'—');
};

bindToolbar(); renderList(); renderStats(); select(0);
"""

# ================================================================ C 双轨对照
CSS_C = """
.app{display:grid;grid-template-columns:276px minmax(0,1fr);height:calc(100vh - 52px)}
.rail{border-right:1px solid var(--line)}
.main{display:flex;flex-direction:column;min-width:0;min-height:0}
.viewer{flex:1}

/* 固定声称条：横向三列 */
.strip{flex:0 0 auto;border-top:1px solid var(--line);background:var(--surface);
  display:grid;grid-template-columns:minmax(300px,1fr) minmax(0,1.45fr) 236px;height:196px}
#claim-body{display:grid;grid-template-columns:minmax(300px,1fr) minmax(0,1.45fr);
  grid-template-rows:auto minmax(0,1fr) auto;min-height:0;overflow:hidden}
#claim-body .c-sec{border-bottom:0;border-right:1px solid var(--line);padding:8px 12px;min-height:0;overflow:hidden}
#claim-body [data-zone="id"]{grid-area:1/1;padding-bottom:4px}
#claim-body [data-zone="value"]{grid-area:2/1;border-bottom:0;padding-top:2px}
#claim-body [data-zone="meta"]{grid-area:1/2}
#claim-body [data-zone="quote"]{grid-area:2/2/4/3}
#claim-body [data-zone="evidence"]{display:none}
#claim-body [data-zone="note"]{display:none}
#claim-body .c-name{font-size:13.5px}
#claim-body .c-pb{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#claim-body .v-big{font-size:18px}
#claim-body .mgrid{grid-template-columns:auto auto auto;gap:2px 18px;white-space:nowrap}
#claim-body .mgrid dt{display:none}
#claim-body .mgrid dd{color:var(--muted)}
#claim-body .quote{font-size:11.5px;overflow-y:auto;border-left-width:2px;padding:5px 8px}
#claim-body .warnline{margin-top:5px;padding:4px 8px;font-size:10.5px}

.strip-side{display:flex;flex-direction:column;gap:6px;padding:8px 12px;min-height:0}
.strip-side .nota{flex:1;min-height:0;font-size:11px}
.strip-side .acts{display:flex;gap:5px}
.strip-side .acts .btn{flex:1;padding:6px 4px;font-size:11.5px}
"""

BODY_C = """
<div class="app">
  """ + LIST_RAIL + """
  <div class="main">
    """ + STAGE + """
    <div class="strip">
      <div id="claim-body"></div>
      <div class="strip-side">
        <textarea class="nota" id="edit-note" placeholder="审核备注：修订原因 / 疑点 / 适用范围……"></textarea>
        <div class="acts">
          <button class="btn ok" id="verify">✓ 确认</button>
          <button class="btn bad" id="flag">⚑ 冲突</button>
          <button class="btn ghost" id="missing">⊘ 缺失</button>
        </div>
      </div>
    </div>
  </div>
</div>
"""

JS_C = """
document.getElementById('layout-tag').textContent = '方案 C · 双轨对照式 — 证据在上、声称条固定在下，竖向眼动往返最短';

/* C 的备注/操作在条侧栏,claim-body 里的 note 区移除,避免重复 id */
const _rc = renderClaim;
renderClaim = function(){
  _rc();
  const zone = document.querySelector('#claim-body [data-zone="note"]');
  if (zone) zone.remove();
  const el = document.getElementById('edit-note');
  if (el) el.value = state.items[state.cur].note;
};
document.getElementById('edit-note').addEventListener('input', e=>{ state.items[state.cur].note = e.target.value; });

bindToolbar(); renderList(); renderStats(); select(0);
"""

# ================================================================ 输出
SPECS = {
    'A': spec_div('方案 A · 三栏主审式', '假说:声称信息量小 → 窄列;证据需要分辨率 → 中央满高最大矩形。<br><br>列表 276px · PDF 弹性最大 · 声称卡 356px,三者常驻同屏、零遮挡。'),
    'B': spec_div('方案 B · 沉浸聚焦式', '假说:读证据时其余皆噪音 —— PDF 独占全窗;清单 = 左抽屉(快捷键 L),声称卡 = 右下浮动 HUD(可折叠,H)。'),
    'C': spec_div('方案 C · 双轨对照式', '假说:判定是竖向「证据↔声称」往返 —— 声称压成固定 196px 横条,PDF 占其余全部高度。当前布局的最小改造版。'),
}

OUTS = [
    ('demoA.html', '证据审核台 A · 三栏主审式', 'A', CSS_A, BODY_A, JS_A),
    ('demoB.html', '证据审核台 B · 沉浸聚焦式', 'B', CSS_B, BODY_B, JS_B),
    ('demoC.html', '证据审核台 C · 双轨对照式', 'C', CSS_C, BODY_C, JS_C),
]

if __name__ == '__main__':
    for fn, title, key, css, body, js in OUTS:
        page = html(title, key, body, css, js, SPECS[key])
        with open(os.path.join(HERE, fn), 'w', encoding='utf-8') as f:
            f.write(page)
        print('wrote', fn, len(page), 'bytes')
