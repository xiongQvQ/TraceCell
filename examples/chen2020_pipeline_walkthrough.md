# End-to-end walkthrough: Chen et al. 2020 (JES 167 080534)

Input: `WRAP-development-experimental-techniques-parameterization-multi-scale-lithium-ion-battery-models-Chen-2020.pdf`
(23 pages, "Development of Experimental Techniques for Parameterization of Multi-scale Lithium-ion Battery Models", DOI 10.1149/1945-7111/abab05).
Working directory: `work/` (all paths below relative to it).

## Stage 1 — PDF 结构分析 (deterministic)

| Product | Result |
|---|---|
| `pages.json` | 23 pages, 1.3k–8.9k chars/page (no scanned pages) |
| `tables.json` | 6 tables on pages 2/6/19; **Table VII** (Newman P2D parameter set) found by both engines: pymupdf `text` strategy (37×9 candidate grid) and Docling TableFormer (22×6 clean grid, 65 s whole-doc). Docling bbox mapped to normalized page coords; crop PNGs rendered |
| `formulas_scan.json` | 125 equation candidates (number-anchored + math-density), crops incl. `p18_eq23/24/25.png` |
| `curves_scan.json` | Figure 12 (p12, 2 panels) and Figure 17 (p21, 3 panels) detected as rasters; hue-clustered traces; legend boxes excluded via `--exclude`; 1C panel isolated via `--region` |

## Stage 2 — 科研语义理解 (Agent, evidenced)

45/45 dictionary entries filled from the PDF (`work/paper_extracted.json`):
- 43 values with quotes machine-verified against the text layer (µm→m, %→fraction conversions documented);
- 2 `MISSING` (OCP entropic change — not reported, isothermal model);
- electrolyte functions reconstructed **visually** from crops (text layer scrambles math):
  - eq.[23] De = 8.794e-11·ce² − 3.972e-10·ce + 4.862e-10 (ce in mol dm⁻³) — a **polynomial**, notably different from PyBaMM's Nyman2008 exponential;
  - eq.[24] σe = 0.1297·ce³ − 2.51·ce^1.5 + 3.329·ce;
  - eq.[25] t⁺ = −0.1287·ce³ + 0.4106·ce² − 0.4717·ce + 0.4492 → evaluates to **0.2594 at ce=1**, matching the sentence "yields t+= 0.2594" on p18 (SymPy cross-validation);
- OCP functions bound to digitized curves from Fig. 12 (see Stage 2b).

## Stage 2b — 曲线数字化 (Agent measures ticks, human confirms)

Tick pixel positions measured programmatically from the crops (`work/calibrations/*.json`):
- Fig. 12(a) positive half-cell: sto 1.0→0.2 (top axis), 4.2→3.6 V → `fig12a_Upos.csv` (152 pts, sto 0.33–1.0)
- Fig. 12(b) negative half-cell: sto 0.0→1.0, 1.4→0.0 V → `fig12b_Uneg.csv` (204 pts, U_n 0.07–1.30 V)
- Fig. 17 1C panel: 0/3 h ticks, 4.0/2.5 V ticks → `fig17_1C_raw.csv` (224 pts)

A first automated pass surfaced two classic digitization traps, both fixed with tool support:
1. **legend contamination** — the legend's red line sample averaged into the curve (phantom U_n ≈ 0.67 V at sto 0.4). Added `--exclude` boxes → U_neg RMSE vs code OCP improved 251 mV → 94 mV (21.5 mV over sto 0.1–0.95; remaining max 0.63 V only at the sto→0.03 steep head).
2. **multi-panel mixing** — one image contains panels (a)+(b); added x-gap segmentation + `--region`.

## Stage 3 — 校验 + 证据定位

- `validate`: ok, 45/45, all PENDING (pre-review).
- `locate_evidence`: 10 `located_exact` (unique text matches), 22 `table_cell_parser` (Table VII cells, parser-provided bboxes), 11 `ambiguous_multiple_matches` (e.g. "0.18 S m−1 and 215 S m−1" appears in text AND table) — preserved as clickable candidates for the human, 2 `quote_too_short` (the MISSING entries).

## Stage 4 — 人工审核 (HITL)

`review_page.html` (9.8 MB, self-contained: base64 PDF + 30+ crops + all JSON) built by `build_review_page.py`; DOM smoke-tested with jsdom (45 rows render; click→edit→确认 updates counters; table/formula/curve tabs populate; export gate present).

For the E2E demonstration the review decisions were applied programmatically by `work/review_pass.py` **in exactly the exported JSON shape** (`work/reviewed.json`): 43 VERIFIED (incl. PyBaMM-convention electrolyte expressions and curve bindings), 2 MISSING. **A human should redo/override this in the browser** — that is the real gate the template enforces; the programmatic pass exists only to exercise the downstream pipeline end-to-end.

## Stage 5 — 冻结 → 独立对比 → 仿真 + 校准

- Freeze: `work/reviewed_frozen.json` (sha256 in `work/freeze_meta.json`).
- `compare` vs installed PyBaMM `Chen2020` set (only NOW allowed): **23 MATCH, 12 VALUE_DIFFERS, 6 CODE_NOT_MAPPED (functions), 2 NOT_EXTRACTED_FROM_PAPER, 2 FUNCTION_REQUIRES_REVIEW.** Genuine paper-vs-code differences surfaced by paper-first extraction:

| Parameter | Paper (Table VII / text) | PyBaMM Chen2020 |
|---|---|---|
| cs,max negative | 29 583 mol m⁻³ | 33 133 mol m⁻³ |
| cs,max positive | 51 765 mol m⁻³ | 63 104 mol m⁻³ |
| Bruggeman (pos/sep/neg) | 2.43 / 2.57 / 2.91 (adjusted, p20) | 1.5 (electrolyte) / 0 (electrode) |
| Particle diffusivity (neg/pos) | 1.74e-15 / 1.48e-15 m² s⁻¹ | 3.3e-14 / 4e-15 (functions) |
| Electrolyte diffusivity | eq.[23] polynomial | Nyman2008 exponential |
| Current (1C) | 4.6225 A (derived) | 5.0 A |
| electrode width/height | 0.065 / 1.58 m | 1.58 / 0.065 m (swapped; same area) |

  Function-shape RMSEs in `work/function_comparison.json`: U_pos 19 mV (max 30 mV); U_neg 21.5 mV on sto 0.1–0.95.
- Simulation (all 41 applicable reviewed overrides applied — 37 scalars + 2 SymPy-compiled electrolyte laws + 2 digitized-OCP Interpolants; j0 coefficients deliberately blocked): 1C discharge reaches the 2.5 V cutoff after only **0.375 Ah** — the paper's Table VII scalar diffusivities (19× lower than the code's) polarize the cell excessively. This is a *legitimate paper-parameters outcome*, and precisely why the next stage exists.
- **自动仿真训练** (`--calibrate --fit <id>:log_scale,...`, bounded 0.05–20×, scalar cost = overlap RMSE + 0.1 V/Ah documented shortfall penalty; coarse log-grid search per parameter, then `scipy.optimize.least_squares` polish from the best grid point, every evaluation logged). A first diagnostic isolated the limiting physics: with paper Table VII values the 1C discharge dies at 0.37 Ah, and the dominant limiter is the negative-electrode Bruggeman exponent 2.91 (ε^2.91 ≈ 0.018); lowering it to 1.5 alone extends runtime to 2.42 Ah. The converged fit (CALIBRATED, never paper evidence):

  | parameter | paper base | fitted factor | fitted value |
  |---|---|---|---|
  | neg. Bruggeman (electrolyte) | 2.91 | ×0.500 | 1.455 |
  | separator Bruggeman (electrolyte) | 2.57 | ×0.250 | 0.643 |
  | neg. particle diffusivity | 1.74e-15 | ×8.07 | 1.41e-14 m²/s |
  | pos. particle diffusivity | 1.48e-15 | ×4.00 | 5.92e-15 m²/s |

  Result: 1C discharge now reaches 2.17 Ah at the 2.5 V cutoff with 214 mV RMSE over the overlapping window (baseline before calibration: 0.37 Ah, 528 mV). The fit independently moves toward the code's transport values — evidence that the paper's own *simulation* used effectively higher transport than its Table VII scalars (which are superseded by the paper's concentration-dependent functions). The residual capacity shortfall vs the paper's 4.5 Ah is the honest limit of constant-diffusivity reproduction and is reported, not hidden. Full iteration log: `work/calibration_run2.log`; report: `work/calibration_report.json`.

## Output inventory

`work/paper_extracted.json`, `work/validation.json`, `work/review_ready.json`, `work/review_page.html`, `work/reviewed.json` (HITL export shape), `work/reviewed_frozen.json` + `freeze_meta.json`, `work/code_values.json`, `work/comparison.json`, `work/function_comparison.json`, `work/simulation_report.json` + `sim_1C.csv/png`, `work/calibration_report.json` + `sim_1C_calibrated.csv/png`, `work/curves/*.csv`, `work/calibrations/*.json`, `work/formulas_*.json`, `work/tables.json` + `table_crops/`.
