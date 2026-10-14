---
name: p2d-dfn-research
summary: Evidence-first extraction, review and simulation of baseline isothermal DFN/P2D lithium-ion battery parameters from research PDFs.
description: Use when a researcher asks to extract DFN/P2D parameters from battery papers, trace each reported number/function to an exact PDF location, review evidence, compare independently with PyBaMM sets, or run an explicitly labeled baseline simulation. Do not include SEI, plating, LAM or other degradation models.
---

# P2D / DFN Research Skill

## Scope and scientific integrity

Target classic isothermal **Doyle–Fuller–Newman (DFN / P2D)** lithium-ion electrochemistry only. Exclude SEI, Li plating/stripping, dead lithium, LAM, fracture, thermal field and aging. The 45-entry `assets/parameter_dictionary.json` is a **candidate extraction template**, **not** a verified complete dependency set for a pinned PyBaMM release.

**HARD RULE: PAPER FIRST.** Never source an extracted scientific value from a PyBaMM parameter module, repository, or internet snippet of code. Do not read comparison code before completing and freezing the independent paper extraction JSON. No absent evidence means `value: null` and `review_status: MISSING` (not a guess). Distinguish `PAPER`, `CITED`, `DERIVED`, `EXTERNAL`, `UNKNOWN`. Keep a candidate array if multiple values exist; human decides which to use. `VERIFIED` is a **human-only** status, granted by clicking in the review page.

## Pipeline (execute in this order)

```
文献 PDF
     │
PDF 结构分析   (run_pipeline.py — deterministic)
     │
┌─────┼──────────┐
▼     ▼          ▼
正文   表格       图像/曲线
│     │          │
文本解析  Docling+PyMuPDF  视觉+曲线提取
│     │ (cell级bbox)  │ (OpenCV+矢量, WebPlotDigitizer思路)
└─────┼──────────┘
     ▼
Claude Code Agent          ← 科研语义理解 (读 PDF + 三路解析结果, 填参数 JSON)
     ▼
参数 JSON 字典 + 原文位置与证据  (validate + locate_evidence)
     ▼
HTML 人工审核  (review_page.html — 人必须逐条点击确认/标定曲线)
     ▼
审核后 PyBaMM  (pybamm_adapter.py — 仿真 + 有界校准训练)
```

### Stage 1 — PDF 结构分析 (deterministic, one command)

**每篇论文一个运行目录 `work/<doc-id>/`**，多篇论文互不覆盖。`--doc-id` 默认从 PDF 文件名末尾的作者-年份推导（`...-Chen-2020.pdf` → `Chen2020`），也可显式指定；该 id 同时写入 `document.id`。

```bash
python scripts/run_pipeline.py --pdf paper.pdf --doc-id Chen2020 --pages 12,19,21 \
  --curve-region "21:0.12,0.27,0.88,0.60" --curve-exclude "0.27,0.20,0.49,0.315"
```

`--simulate` 在脚手架末尾追加一次 PyBaMM DFN 基线仿真：存在 `review/reviewed_frozen.json`（或 `reviewed.json`）就用审核值，否则用占位提取 JSON——**没有数值的参数一律回退 Chen2020 默认值**，报告 `hybrid_warning` 显式标注 HYBRID（非论文复现）。产物在 `sim/`；求解失败也会落一份 `FAILED` 报告并以非零码退出。

运行目录内部（`work/<doc-id>/`）：

| 位置 | 内容 |
|---|---|
| 根 | 解析产物 `pages.json` / `tables.json` / `formulas_scan.json` / `curves_scan(_all).json` / `paper_extracted.json` / `review_ready.json`，以及三个裁片目录 |
| `table_crops/` `formula_crops/` `curve_crops/` | 证据裁片。**目录名不可改、不可下移** —— JSON 里以相对路径引用 |
| `review/` | `review_page.html`、`reviewed.json`、`reviewed_frozen.json`、`freeze_meta.json` |
| `sim/` | `sim_1C*.csv/png`、`simulation_report.json`、`calibration_report.json`、`comparison.json`、`code_values.json` |
| `curves/` `calibrations/` | 曲线数字化 CSV 与标定记录 |
| `scripts/` `logs/` | 该论文的一次性脚本与日志 |

Produces: `pages.json` (text inventory), `tables.json` (cells + row/col + merged cells + per-cell bbox, engines tagged `pymupdf`/`docling`), `formulas_scan.json` (equation-number anchored candidates + rendered crops), `curves_scan(_all).json` (raster traces via OpenCV hue clustering, vector strokes via PyMuPDF paths, plot-frame detection, legend exclusion boxes), and a first `review/review_page.html`.

已有扁平 `work/` 时用 `python scripts/migrate_workdir.py --work work --doc-id <id> --apply` 迁入运行目录（默认 dry-run，先打印计划；除 `.DS_Store` 外不删除任何文件，杂项一律移入 `_inbox/`）。

**审核页即备份**：`build_review_page.py` 生成的是自包含页面，`review_ready / tables / formulas / curves` 全部原样内联（裁片转 data URI）。因此只要留住任意一份审核页，这些产物都能反解回运行目录：

```bash
python scripts/recover_from_review_page.py --page <审核页>.html --out work/<doc-id> --pdf paper.pdf [--apply]
```

它会比对页内 PDF 与磁盘 PDF 的 sha256 以确认同源，并把 `review_ready.json`、`tables.json`、`curves_scan_all.json`、`formulas_validated.json` 及全部裁片还原出来。**反解不出**的是人工审核决定（`reviewed*.json`）与 `sim/` 仿真产物 —— 审核页只保存文献侧证据，不保存人的判定。开工前把审核页复制一份到别处，是最省事的保险。

### Stage 2 — 三路模块职责

| 模块 | 脚本 | 产出 | 优先级 |
|---|---|---|---|
| 结构化表格解析 | `table_parser.py` (Docling + PyMuPDF, `--docling-json` 可复用昂贵结果) | 行列/合并单元格/单元格坐标 JSON + 表格裁剪 PNG | P0 |
| 科学公式解析 | `formula_parser.py scan` + **Agent 视觉重建** + `validate` | 候选截图 → `formulas_agent.json` (sympy_str+变量+单位) → SymPy 解析/变量/数值/结构校验 | P0 |
| 科研曲线数字化 | `curve_digitizer.py scan/digitize` | 轴检测 + 像素轨迹 → **人工标定** → 换算 CSV(带溯源头) | P1 |

Formula notes: PDF text layers scramble inline math — the **Agent reads the crop images** and reconstructs each equation as a SymPy string; `validate` then checks parse / symbol coverage / finite reference value / dimensionless exp-log args. Strict dimensional comparison only applies when all variables are dimensionless; numeric laws (pure-number coefficients carrying units) are flagged for **human** confirmation, never auto-passed. The review page shows each formula's crop + sympy source + check chips, and the human clicks 核对无误/有疑问.

Curve notes: traces are **uncalibrated pixels** until calibration points exist. Calibration points come from axis-tick reading (Agent) and are **confirmed by the human clicking** in the review page's 曲线标定 tab (2+ points per axis, optional log axes). `digitize` applies the human-approved calibration (linear/log affine least squares) and writes a CSV with full provenance headers. Multi-panel figures need `--region`; legends need `--exclude` boxes — both selectable by the human.

### Stage 3 — 科研语义理解 (the Agent; never automated)

For each of the 45 dictionary entries, reason **from the PDF**: fill value (with deterministic unit conversion documented in notes), original units, exact quote copied from the text layer, page (1-based), table/figure/formula reference, conditions. Functions: record an explicit symbolic expression (`expr://sym:...` — with the variable's unit convention stated) or a digitized curve reference (`data://curve:<figure>:<trace>`). Leave `MISSING` when the paper does not establish the claim. Then:

```bash
W=work/Chen2020            # 该论文的运行目录
python scripts/skill_cli.py validate --input $W/paper_extracted.json --output $W/validation.json
python scripts/locate_evidence.py --pdf paper.pdf --input $W/paper_extracted.json \
  --dictionary assets/parameter_dictionary.json --tables $W/tables.json --output $W/review_ready.json
```

`locate_evidence` grants `bbox_norm` only on **unique exact-text matches**; short quotes require a page hint and uniqueness; parser-provided **table-cell bboxes** are attached under the distinct status `table_cell_parser` (highlight style differs; still human-confirmed). Ambiguous matches stay listed as clickable candidates in the review page.

### Stage 4 — HTML 人工审核 (human-in-the-loop, mandatory)

Rebuild `work/<doc-id>/review/review_page.html` (`build_review_page.py` — self-contained: inlined PDF, crops, all JSON). 版式为**三栏主审式**：左窄列参数清单 / 中栏证据（PDF 原文·表格·公式·曲线四个 tab）/ 右栏当前参数判定。

The human:

1. clicks each parameter row → PDF jumps to the page and highlights the evidence bbox; ambiguous text matches are drawn as **numbered dashed boxes on the page** — clicking one adopts that bbox;
2. edits value/unit/source if needed, then **确认 (VERIFIED) / 冲突 / 恢复** — export is gated while any parameter is PENDING (a written gap reason is required to force export);
3. 表格证据 tab: clicking a parsed cell adopts cell text + page + bbox as that parameter's evidence;
4. 公式证据 tab: visually checks each reconstructed formula against its crop; 核对无误 / 标记有疑问 / 绑定到当前参数;
5. 曲线标定 tab: clicks ≥2 axis reference points per axis, enters tick values, previews the mapped CSV, then 确认采纳并写入当前参数 (this is the ONLY path a curve becomes data).

Progress autosaves to localStorage; 导出审核 JSON produces the reviewed file consumed downstream.

### Stage 5 — Freeze, independent code comparison, simulation

Freeze the reviewed JSON (hash + copy) **before** touching PyBaMM code. Then build `code_values.json` from the installed PyBaMM set and run `skill_cli.py compare`. Compare function shapes **numerically** as well (see `work/Chen2020_080534/sim/function_comparison.json` from the E2E example): sample code OCPs against digitized curves, code electrolyte laws against reconstructed equations.

```bash
W=work/Chen2020
python scripts/pybamm_adapter.py --reviewed $W/review/reviewed_frozen.json --output $W/sim/simulation_report.json \
  --run --c-rate 1.0 --cut-voltage 2.5 --curve-csv $W/sim/sim_1C.csv
# 自动仿真训练 (calibration): bounded least-squares of reviewed params vs a digitized curve
python scripts/pybamm_adapter.py --reviewed $W/review/reviewed_frozen.json --output $W/sim/calibration_report.json \
  --run --calibrate --target $W/curves/fig17_1C_discharge_target.csv \
  --fit negative_particle_diffusivity:log_scale,positive_particle_diffusivity:log_scale \
  --curve-csv $W/sim/sim_1C_calibrated.csv
```

The adapter applies VERIFIED entries only: scalars, SymPy-compiled function expressions (paper unit convention → PyBaMM convention conversion must be inside the expression and documented), and digitized-curve Interpolants (arguments clamped to the digitized domain). Reaction-rate **coefficients** (m_k) are deliberately blocked from being injected as constant j0 — implement the function shape manually instead. Any gap filled by the fallback parameter set makes the run a **HYBRID experiment, never a reproduction**; the report states the denominator.

Calibrated values are labeled `CALIBRATED_SIMULATION_FIT` — never cite them as paper evidence, and never feed them back into the extraction JSON.

## Output contract

Produce: (1) independently extracted JSON; (2) evidence-location JSON; (3) human-reviewed JSON (+ export gate reason if any); (4) independent code comparison JSON + function-shape comparison; (5) missing/ambiguous/conflict report; (6) simulation/calibration report + curves + plot. Report **denominators** for extracted coverage and verified accuracy; don't call absent items wrong or infer accuracy from code matches alone.

## Safety gates and fail-closed behavior

- PDF text with fewer than ~60 characters/page may be scanned; use a robust document parser/OCR only with explicit verification and flag uncertainty.
- Exact quote matches at multiple locations stay unresolved and surface as clickable candidates; numeric-only quotes require a page hint and uniqueness.
- Normalized bounding boxes are page-relative; PDF page starts at 1. Exact-match and parser-table-cell highlights use different provenance labels.
- Unit conversions must be deterministic with dimensional checking; never assume an unlabeled quantity's unit. Formula validation passes structural errors (dimensionful exp/log args, inconsistent Add terms) and defers unit-convention judgments to the human.
- `VERIFIED` is reserved for explicit human action, never automatically assigned. Curve CSVs carry calibration provenance and a human-review field.
- Do not inject an unverified scalar into PyBaMM. Missing data should block *paper-only reproduction*. Baseline mixing is allowed only with an explicit conspicuous warning.
- Calibration runs are bounded (scipy least_squares with explicit bounds and max_nfev) and reported iteration-by-iteration; a simulation shorter than the target curve adds a documented shortfall penalty, not silent truncation.

## References

Read `references/PARAMETER_POLICY.md`, `references/WORKFLOW.md`, and `README.md` for data schema, commands and assumptions.
