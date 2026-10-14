# CLI workflow

Install `pip install -r requirements.txt` (PyMuPDF, docling, opencv-python, sympy, pybamm, scipy, matplotlib). Docling is heavyweight but pre-installed results can be reused with `--docling-json`.

## One-command deterministic scaffold

```bash
python scripts/run_pipeline.py --pdf paper.pdf --workdir work \
  --pages 12,19,21 \
  --curve-region "21:0.12,0.27,0.88,0.60" \
  --curve-exclude "0.27,0.20,0.49,0.315"
```

Stages: inventory → table_parser (pymupdf + docling) → formula scan → curve scan (+ per-region scans for multi-panel figures) → placeholder review page. Multi-panel figures: `page:region` pairs; legends: normalized exclude boxes.

### Optional: end-of-pipeline baseline simulation

```bash
python scripts/run_pipeline.py --pdf paper.pdf --workdir work --simulate [--c-rate 1.0] [--cut-voltage 3.0]
```

Runs the same scaffold, then a closing PyBaMM DFN stage into `work/<doc-id>/sim/`:

- `work/<doc-id>/review/reviewed_frozen.json` (or `reviewed.json`) exists → the simulation uses the human-reviewed values;
- otherwise the placeholder `paper_extracted.json` (all 45 entries `MISSING`) is used and **every parameter without a value falls back to the Chen2020 default set** — the report's `hybrid_warning` states `45/45 … filled by Chen2020 baseline` and the run is labeled **HYBRID, NOT a paper reproduction**.

Outputs: `sim/simulation_report.json`, `sim/sim_<c>C.csv`, `sim/sim_<c>C.png`. A failed solve still writes a `FAILED` report and exits non-zero. Calibration stays a separate, explicit step (`pybamm_adapter.py --calibrate`).

## Agent semantic extraction (manual, evidenced)

```bash
python scripts/skill_cli.py template --pdf paper.pdf --output work/paper_extracted.json   # empty 45-entry scaffold
# Agent reads the PDF + parse outputs and fills every entry with quotes/pages/refs
python scripts/skill_cli.py validate --input work/paper_extracted.json --output work/validation.json
python scripts/locate_evidence.py --pdf paper.pdf --input work/paper_extracted.json \
  --dictionary assets/parameter_dictionary.json --tables work/tables.json --output work/review_ready.json
```

## Formula reconstruction loop

```bash
python scripts/formula_parser.py scan --pdf paper.pdf --output work/formulas_scan.json --crops work/formula_crops --pages 18
# Agent visually reconstructs each crop -> work/formulas_agent.json (sympy_str, variables+units, value_at_reference)
python scripts/formula_parser.py validate --input work/formulas_agent.json --output work/formulas_validated.json
```

Checks: sympy parse → symbol coverage → finite value at reference → dimensional structure (exp/log args dimensionless; strict lhs/rhs comparison only when all variables are dimensionless). Statuses: VALIDATED / PARSE_ERROR / SYMBOL_MISMATCH / NONFINITE / DIMENSION_MISMATCH.

## Curve digitization loop

```bash
python scripts/curve_digitizer.py scan --pdf paper.pdf --output work/curves_scan.json --pages 12 \
  --exclude "0.60,0.23,0.82,0.37"          # legend boxes, normalized to crop
python scripts/curve_digitizer.py scan --pdf paper.pdf --output work/curves_1C.json --pages 21 \
  --region "0.12,0.27,0.88,0.60"            # one panel of a multi-panel figure
# calibration JSON: {"x": {"points": [{"px":[..],"data":[..]}..], "log": false}, "y": {...}} (or interactive in the review page)
python scripts/curve_digitizer.py digitize --scan work/curves_scan.json --figure p12_img1 \
  --trace color_hue0-10_seg2 --calibration work/calibrations/fig12b_Uneg.json \
  --output-csv work/curves/fig12b_Uneg.csv --output-json work/curves/fig12b_Uneg.json
```

## Human review (browser, no server)

```bash
python scripts/build_review_page.py --review-ready work/review_ready.json --tables work/tables.json \
  --formulas work/formulas_validated.json --curves work/curves_scan_all.json \
  --pdf paper.pdf --output work/review_page.html
```

Open `work/review_page.html`: click parameters → PDF highlights; 表格证据 click-to-adopt cells; 公式证据 verify crops; 曲线标定 click axis points and confirm CSV; export reviewed JSON (gated while PENDING items remain).

## Freeze → compare → simulate → calibrate

```bash
cp work/reviewed.json work/reviewed_frozen.json && sha256sum work/reviewed_frozen.json
# build work/code_values.json from the installed PyBaMM set ONLY NOW
python scripts/skill_cli.py compare --paper work/reviewed_frozen.json --code work/code_values.json --output work/comparison.json
python scripts/pybamm_adapter.py --reviewed work/reviewed_frozen.json --output work/simulation_report.json \
  --run --c-rate 1.0 --cut-voltage 2.5 --curve-csv work/sim_1C.csv
python scripts/pybamm_adapter.py --reviewed work/reviewed_frozen.json --output work/calibration_report.json \
  --run --calibrate --target work/curves/fig17_1C_discharge_target.csv \
  --fit negative_particle_diffusivity:log_scale,positive_particle_diffusivity:log_scale \
  --max-nfev 6 --curve-csv work/sim_1C_calibrated.csv
```

Code comparison JSON shape: `{"parameters":[{"id":"negative_electrode_thickness","value":8.52e-5,"unit":"m","code_ref":"repo@commit:path#line"}]}`. The code extraction is deliberately separate from the paper process. Function-shape comparison is numeric (sample code functions vs digitized curves / reconstructed equations) and lives next to the scalar comparison.

Calibration fit spec: `parameter_id:scale` (multiplicative, bounded 0.05–20) or `parameter_id:log_scale` (bounded e^±…). Every iteration is logged (scales, sim capacity, RMSE); a sim shorter than the target adds a documented 0.1 V/Ah shortfall penalty. Fitted values are `CALIBRATED_SIMULATION_FIT`, never paper evidence.
