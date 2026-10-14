#!/usr/bin/env python3
"""One-command deterministic pipeline: PDF -> structure analysis -> review page -> (optional) PyBaMM baseline sim.

Runs every stage that needs no scientific judgment:

    文献 PDF ─ PDF 结构分析 ─┬─ 正文文本 inventory
                             ├─ 表格解析 (Docling + PyMuPDF)
                             ├─ 公式候选扫描 (crops for 视觉模型)
                             └─ 图像/曲线扫描 (OpenCV + vector)
                                  │
                                  ▼
                     build_review_page.py 打包自包含审核页
                                  │
                                  ▼ (--simulate)
                     pybamm_adapter.py 基线仿真: 有审核用审核值,
                     没有数值的参数回退 Chen2020 默认值 (HYBRID)

The Claude Code Agent then performs 科研语义理解 (fill extraction JSON from the
parse results + its own PDF reading) and the HUMAN reviews/calibrates in the
generated HTML before PyBaMM runs. Those two steps are deliberately NOT here.

Usage:
  python scripts/run_pipeline.py --pdf paper.pdf [--doc-id Chen2020] [--pages 12,19,21] [--simulate]

每篇论文一个运行目录 work/<doc-id>/ —— 多篇论文互不覆盖。doc-id 默认从
PDF 文件名推导(末尾的作者-年份),也可显式指定;目录名 = 该论文的 document.id。
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def derive_doc_id(pdf):
    """从 PDF 文件名推导一个短 id:优先末尾的 <作者>-<年份>,否则压缩成 slug。"""
    stem = Path(pdf).stem
    toks = [t for t in re.split(r'[-_\s]+', stem) if t]
    if len(toks) >= 2 and re.fullmatch(r'(19|20)\d{2}', toks[-1]):
        return f'{toks[-2]}{toks[-1]}'
    slug = re.sub(r'[^A-Za-z0-9]+', '', stem)[:24]
    return slug or 'paper'


def run(cmd):
    print('+', ' '.join(str(c) for c in cmd))
    r = subprocess.run([sys.executable] + [str(c) for c in cmd], cwd=str(ROOT))
    if r.returncode != 0:
        sys.exit(f'stage failed: {cmd[0]}')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pdf', required=True)
    ap.add_argument('--doc-id', help='运行目录名 / document.id;默认从 PDF 文件名推导')
    ap.add_argument('--workdir', help='显式指定运行目录(默认 work/<doc-id>)')
    ap.add_argument('--pages', help='restrict table/figure/formula scanning to pages, e.g. "12,19,21"')
    ap.add_argument('--docling', action='store_true', help='also run Docling live (slow) instead of reusing --docling-json')
    ap.add_argument('--docling-json')
    ap.add_argument('--curve-region', action='append', default=[],
                    help='page:region scan for multi-panel figures, e.g. "21:0.12,0.27,0.88,0.60"; repeatable')
    ap.add_argument('--curve-exclude', action='append', default=[],
                    help='exclude box x0,y0,x1,y1 (legend) applied to raster scans; repeatable')
    ap.add_argument('--template', default=str(ROOT / 'assets' / 'review_template.html'))
    ap.add_argument('--skip-review-page', action='store_true')
    ap.add_argument('--simulate', action='store_true',
                    help='收尾跑一次 PyBaMM DFN 仿真: 有 review/reviewed*.json 用审核值, 否则用占位提取 JSON —— '
                         '没有数值的参数一律回退 Chen2020 默认值 (报告显式标注 HYBRID, 非论文复现)')
    ap.add_argument('--c-rate', type=float, default=1.0, help='仿真倍率 (默认 1C), 传给 pybamm_adapter')
    ap.add_argument('--cut-voltage', type=float, default=3.0, help='仿真截止电压 [V] (默认 3.0), 传给 pybamm_adapter')
    args = ap.parse_args()

    doc_id = args.doc_id or derive_doc_id(args.pdf)
    work = Path(args.workdir) if args.workdir else Path('work') / doc_id
    work.mkdir(parents=True, exist_ok=True)
    pdf = Path(args.pdf)
    pages = args.pages
    print(f'run dir: {work}/  (doc-id={doc_id})')
    extraction = work / 'paper_extracted.json'

    # 1. 正文: text inventory
    run(['scripts/skill_cli.py', 'inventory', '--pdf', pdf, '--output', work / 'pages.json'])

    # 2. 表格: dual engine
    cmd = ['scripts/table_parser.py', '--pdf', pdf, '--output', work / 'tables.json', '--crops', work / 'table_crops']
    if pages:
        cmd += ['--pages', pages]
    if args.docling_json:
        cmd += ['--docling-json', args.docling_json]
    run(cmd)

    # 3. 公式候选: crops for the Agent (视觉模型)
    cmd = ['scripts/formula_parser.py', 'scan', '--pdf', pdf, '--output', work / 'formulas_scan.json',
           '--crops', work / 'formula_crops']
    if pages:
        cmd += ['--pages', pages]
    run(cmd)

    # 4. 曲线: full-page scan + optional per-region scans (multi-panel figures)
    cmd = ['scripts/curve_digitizer.py', 'scan', '--pdf', pdf, '--output', work / 'curves_scan.json',
           '--crops', work / 'curve_crops']
    if pages:
        cmd += ['--pages', pages]
    for ex in args.curve_exclude:
        cmd += ['--exclude', ex]
    run(cmd)
    all_curves = json.loads((work / 'curves_scan.json').read_text())
    seen = {f['figure_id'] for f in all_curves['figures']}
    for spec in args.curve_region:
        page, region = spec.split(':', 1)
        out = work / f'curves_scan_p{page}_region.json'
        run(['scripts/curve_digitizer.py', 'scan', '--pdf', pdf, '--output', out, '--crops', work / 'curve_crops',
             '--pages', page, '--region', region] + sum([['--exclude', e] for e in args.curve_exclude], []))
        extra = json.loads(out.read_text())
        for f in extra['figures']:
            if f['figure_id'] not in seen:
                all_curves['figures'].append(f); seen.add(f['figure_id'])
        (work / 'curves_scan_all.json').write_text(json.dumps(all_curves, indent=1, ensure_ascii=False))
    if not args.curve_region:
        (work / 'curves_scan_all.json').write_text(json.dumps(all_curves, indent=1, ensure_ascii=False))

    if not args.skip_review_page:
        # 5. 打包审核页 (empty extraction template as placeholder until the Agent fills it)
        if not extraction.exists():
            run(['scripts/skill_cli.py', 'template', '--pdf', pdf, '--doc-id', doc_id, '--output', extraction])
            run(['scripts/skill_cli.py', 'validate', '--input', extraction, '--output', work / 'validation.json'])
            run(['scripts/locate_evidence.py', '--pdf', pdf, '--input', extraction,
                 '--dictionary', ROOT / 'assets' / 'parameter_dictionary.json', '--tables', work / 'tables.json',
                 '--output', work / 'review_ready.json'])
        run(['scripts/build_review_page.py', '--template', args.template,
             '--review-ready', work / 'review_ready.json', '--tables', work / 'tables.json',
             '--curves', work / 'curves_scan_all.json', '--pdf', pdf, '--output', work / 'review_page.html'])

    # 6. 仿真收尾 (--simulate): 有人工审核产物就用审核值; 没有审核 (或审核前) 时直接用
    #    占位提取 JSON —— 没有数值的参数全部回退 Chen2020 默认值, 报告显式标注 HYBRID。
    if args.simulate:
        if not extraction.exists():
            run(['scripts/skill_cli.py', 'template', '--pdf', pdf, '--doc-id', doc_id, '--output', extraction])
        sim = work / 'sim'
        sim.mkdir(parents=True, exist_ok=True)
        reviewed = next((c for c in (work / 'review' / 'reviewed_frozen.json',
                                     work / 'review' / 'reviewed.json') if c.exists()), None)
        if reviewed is None:
            reviewed = extraction
            print('simulate: no reviewed JSON yet -> every parameter without a value falls back to the '
                  'Chen2020 baseline defaults (HYBRID run, not a paper reproduction)')
        run(['scripts/pybamm_adapter.py', '--reviewed', reviewed, '--output', sim / 'simulation_report.json',
             '--run', '--c-rate', args.c_rate, '--cut-voltage', args.cut_voltage,
             '--curve-csv', sim / f'sim_{args.c_rate:g}C.csv'])

    if args.skip_review_page:
        print('done (deterministic stages only). Next: Agent semantic extraction -> validate -> locate_evidence -> human review.')
        return

    print(f"""
Pipeline scaffold ready in {work}/:
  pages.json / tables.json / formulas_scan.json / curves_scan(_all).json / review_page.html
NEXT (deliberately manual):
  1. Agent: read PDF + parse outputs -> fill {extraction}  (semantic extraction with evidence)
  2. skill_cli validate + locate_evidence -> rebuild review_page.html
  3. HUMAN: open review_page.html, click through 45 params, calibrate curves, export reviewed JSON
  4. skill_cli compare + pybamm_adapter --run [--calibrate]
     (或直接重跑: python scripts/run_pipeline.py --pdf {pdf.name} --simulate)
""")


if __name__ == '__main__':
    main()
