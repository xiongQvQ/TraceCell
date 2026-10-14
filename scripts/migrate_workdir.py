#!/usr/bin/env python3
"""把扁平的 work/ 迁移成「每篇论文一个运行目录」:work/<doc-id>/...

约束:crop 目录名 table_crops/ formula_crops/ curve_crops/ 被 JSON 以相对路径
引用,必须与解析 JSON 同级,不得改名或下移。

运行目录内部:
  <doc-id>/            解析产物(pages/tables/formulas/curves/... .json)+ 三个 crop 目录
  <doc-id>/curves/     曲线数字化 CSV/JSON
  <doc-id>/calibrations/
  <doc-id>/review/     审核阶段产物(审核页、reviewed、freeze)
  <doc-id>/sim/        仿真 + 对比产物
  <doc-id>/scripts/    针对该论文的一次性脚本
  <doc-id>/logs/

用法:python3 scripts/migrate_workdir.py --work work --doc-id Chen2020_080534 [--apply]
不带 --apply 只打印计划。
"""
import argparse, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 文件名 -> 目标子目录(None = 留在运行目录根)
LAYOUT = {
    'review': ['review_page.html', 'reviewed.json', 'reviewed_frozen.json',
               'freeze_meta.json'],
    'sim': ['sim_1C.csv', 'sim_1C.png', 'sim_1C_calibrated.csv', 'sim_1C_calibrated.png',
            'simulation_report.json', 'calibration_report.json', 'chart_data.json',
            'chart.svg.fragment', 'comparison.json', 'code_values.json',
            'function_comparison.json'],
    'scripts': ['review_pass.py', 'build_extraction.py', 'make_chart.py',
                'extract_chart_data.py'],
    'logs': ['calibration_run.log', 'calibration_run2.log', 'docling_err.log'],
}
# 整目录平移(None = 留在根;这些名字被相对路径或 CLI 文档引用,不改名)
DIRS = {
    'table_crops': None, 'formula_crops': None, 'curve_crops': None,
    'curves': 'curves', 'calibrations': 'calibrations',
}
# 只清理 macOS 元数据;其余一切——包括看起来像临时产物的文件——一律移入 _inbox,
# 绝不删除。迁移工具不该替人判断什么可以丢。
JUNK = ['.DS_Store']


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work', default='work')
    ap.add_argument('--doc-id', required=True)
    ap.add_argument('--demos-to', help='把 work/demos 移到该目录(如 design)')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    work = ROOT / a.work
    dest = work / a.doc_id
    actions = []
    planned = set()

    def plan(src, dst):
        if src.exists() and src not in planned:
            planned.add(src)
            actions.append((src, dst))

    for d, target in DIRS.items():
        plan(work / d, (dest / target) if target else (dest / d))
    for target, names in LAYOUT.items():
        for n in names:
            plan(work / n, dest / target / n)
    # 其余散落的 .json 留在运行目录根(已在上面归类的跳过)
    for p in sorted(work.glob('*.json')):
        plan(p, dest / p.name)

    if a.demos_to:
        plan(work / 'demos', ROOT / a.demos_to / 'demos')

    print(f'目标运行目录: {dest}/')
    print(f'计划迁移 {len(actions)} 项:')
    for s, d in actions:
        print(f'  {s.relative_to(ROOT)}  ->  {d.relative_to(ROOT)}')
    junk = [work / j for j in JUNK if (work / j).exists()]
    if junk:
        print('将删除(macOS 元数据):')
        for j in junk:
            print(f'  {j.relative_to(ROOT)}')

    if not a.apply:
        print('\n(dry-run — 加 --apply 执行)')
        return

    dest.mkdir(parents=True, exist_ok=True)
    for s, d in actions:
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(s), str(d))
    for j in junk:
        j.unlink()
    # 归拢剩下的杂项(图片等)到 _inbox,避免污染运行目录
    leftovers = [p for p in work.iterdir() if p != dest and p.name != '_demos']
    if leftovers:
        inbox = dest / '_inbox'
        inbox.mkdir(exist_ok=True)
        for p in leftovers:
            shutil.move(str(p), str(inbox / p.name))
        print(f'另有 {len(leftovers)} 项杂项移入 {inbox.relative_to(ROOT)}/')
    print('迁移完成:', dest.relative_to(ROOT))


if __name__ == '__main__':
    main()
