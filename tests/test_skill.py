import json, subprocess, sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'scripts' / 'skill_cli.py'
LOC = ROOT / 'scripts' / 'locate_evidence.py'
TBL = ROOT / 'scripts' / 'table_parser.py'
FRM = ROOT / 'scripts' / 'formula_parser.py'
CRV = ROOT / 'scripts' / 'curve_digitizer.py'
BLD = ROOT / 'scripts' / 'build_review_page.py'
PYB = ROOT / 'scripts' / 'pybamm_adapter.py'
RPL = ROOT / 'scripts' / 'run_pipeline.py'


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)


def test_dictionary():
    obj = json.loads((ROOT / 'assets' / 'parameter_dictionary.json').read_text())
    assert obj['param_count'] == len(obj['parameters']) == 45
    assert len(set(p['id'] for p in obj['parameters'])) == 45


def test_template_starts_empty(tmp_path):
    target = tmp_path / 'blank.json'
    p = run(CLI, 'template', '--output', target)
    assert p.returncode == 0, p.stderr
    j = json.loads(target.read_text())
    assert len(j['parameters']) == 45
    assert all(x['value'] is None and x['review_status'] == 'MISSING' for x in j['parameters'])


def test_inventory(tmp_path):
    target = tmp_path / 'pages.json'
    p = run(CLI, 'inventory', '--pdf', ROOT / 'examples' / 'synthetic.pdf', '--output', target)
    assert p.returncode == 0, p.stderr
    assert json.loads(target.read_text())['document']['pages'] > 0


def test_locator(tmp_path):
    target = tmp_path / 'review.json'
    p = run(LOC, '--pdf', ROOT / 'examples' / 'synthetic.pdf', '--input', ROOT / 'examples' / 'synthetic_extracted.json',
            '--dictionary', ROOT / 'assets' / 'parameter_dictionary.json', '--output', target)
    assert p.returncode == 0, p.stderr
    values = json.loads(target.read_text())['parameters']
    assert len(values) == 2
    assert all(x['evidence']['location_status'] == 'located_exact' for x in values)
    assert all(len(x['evidence']['bbox_norm']) == 4 for x in values)


def test_locator_never_promotes_unverified_bbox(tmp_path):
    src = tmp_path / 'in.json'
    src.write_text(json.dumps({'parameters': [
        {'id': 'negative_electrode_thickness', 'value': 1.0, 'unit': 'm', 'source_type': 'PAPER',
         'evidence': {'page': 1, 'quote': 'a fabricated quote that does not exist anywhere',
                      'bbox_norm': [0.1, 0.1, 0.5, 0.5]}}]}))
    out = tmp_path / 'out.json'
    p = run(LOC, '--pdf', ROOT / 'examples' / 'synthetic.pdf', '--input', src, '--output', out)
    assert p.returncode == 0, p.stderr
    ev = json.loads(out.read_text())['parameters'][0]['evidence']
    assert ev['bbox_norm'] is None  # fabricated coordinates must not survive


def test_compare_never_backfills(tmp_path):
    paper = {'parameters': [{'id': 'a', 'value': None, 'unit': 'm'},
                            {'id': 'b', 'value': 2, 'unit': 'm', 'value_type': 'scalar'}]}
    code = {'parameters': [{'id': 'a', 'value': 10, 'unit': 'm'}, {'id': 'b', 'value': 2, 'unit': 'm'}]}
    f, g, out = tmp_path / 'paper.json', tmp_path / 'code.json', tmp_path / 'out.json'
    f.write_text(json.dumps(paper)); g.write_text(json.dumps(code))
    p = run(CLI, 'compare', '--paper', f, '--code', g, '--output', out)
    assert p.returncode == 0, p.stderr
    rows = json.loads(out.read_text())['comparisons']; by = {x['id']: x for x in rows}
    assert by['a']['result'] == 'NOT_EXTRACTED_FROM_PAPER' and by['a']['paper_value'] is None
    assert by['b']['result'] == 'MATCH'


# ---------------- table parser ----------------
def test_table_parser_cells_and_bbox(tmp_path):
    out = tmp_path / 'tables.json'
    p = run(TBL, '--pdf', ROOT / 'examples' / 'synthetic.pdf', '--output', out,
            '--crops', tmp_path / 'crops')
    assert p.returncode == 0, p.stderr
    d = json.loads(out.read_text())
    assert d['schema_version'] == 'p2d-tables-v1'
    for t in d['tables']:
        assert t['engine'] in ('pymupdf', 'docling')
        assert t['page'] >= 1
        assert t['bbox_norm'] is None or all(0 <= v <= 1 for v in t['bbox_norm'])
        for c in t.get('cells', []):
            assert 0 <= c['bbox_norm'][0] <= 1


# ---------------- formula parser ----------------
def test_formula_validation_statuses(tmp_path):
    agent = tmp_path / 'formulas_agent.json'
    agent.write_text(json.dumps({'formulas': [
        {'id': 'ok', 'page': 1, 'sympy_str': '8.794e-11*ce**2 - 3.972e-10*ce + 4.862e-10',
         'lhs_unit': 'm2.s-1', 'variables': [{'symbol': 'ce', 'unit': 'mol.dm-3'}],
         'value_at_reference': {'ce': 1}},
        {'id': 'bad', 'page': 1, 'sympy_str': '8.794e-11*ce**2 - 3.972e-10*ce + 4.862e-10',
         'lhs_unit': 'm2.s-1', 'variables': [], 'value_at_reference': {}},
    ]}))
    out = tmp_path / 'validated.json'
    p = run(FRM, 'validate', '--input', agent, '--output', out)
    assert p.returncode == 0, p.stderr
    fs = {f['id']: f for f in json.loads(out.read_text())['formulas']}
    assert fs['ok']['validation_status'] == 'VALIDATED'
    assert fs['ok']['evaluated'] is not None
    assert fs['bad']['validation_status'] == 'SYMBOL_MISMATCH'


def test_formula_dimensionless_exp_guard(tmp_path):
    agent = tmp_path / 'f.json'
    agent.write_text(json.dumps({'formulas': [
        {'id': 'struct', 'sympy_str': '2*exp(-0.65*ce) + 1', 'lhs_unit': '1',
         'variables': [{'symbol': 'ce', 'unit': 'mol.m-3'}], 'value_at_reference': {'ce': 1}},
    ]}))
    out = tmp_path / 'v.json'
    run(FRM, 'validate', '--input', agent, '--output', out)
    f = json.loads(out.read_text())['formulas'][0]
    assert f['validation_status'] == 'DIMENSION_MISMATCH'  # dimensionful exp argument


# ---------------- curve digitizer ----------------
def _cal_file(tmp_path):
    cal = tmp_path / 'cal.json'
    cal.write_text(json.dumps({
        'x': {'points': [{'px': [0.1, 0.5], 'data': [0.0]}, {'px': [0.5, 0.5], 'data': [3.0]}], 'log': False},
        'y': {'points': [{'px': [0.1, 0.2], 'data': [4.0]}, {'px': [0.1, 0.7], 'data': [2.5]}], 'log': False},
        'reviewed': True}))
    return cal


def test_curve_digitize_roundtrip(tmp_path):
    # 1x1 synthetic scan JSON: a straight line trace y_norm = f(x_norm)
    scan = tmp_path / 'scan.json'
    trace = [[0.1 + 0.005 * i, 0.2 + 0.6 * (0.005 * i / 0.4)] for i in range(81)]
    scan.write_text(json.dumps({'document': {'pdf_filename': 'synthetic', 'pdf_sha256': '0' * 64},
                                'figures': [{'figure_id': 'f1', 'page': 1, 'source': 'synthetic',
                                             'traces': [{'trace_id': 't1', 'n_points': len(trace),
                                                         'points_norm': trace}]}]}))
    cal = _cal_file(tmp_path)
    csv_out = tmp_path / 'curve.csv'
    p = run(CRV, 'digitize', '--scan', scan, '--figure', 'f1', '--trace', 't1',
            '--calibration', cal, '--output-csv', csv_out)
    assert p.returncode == 0, p.stderr
    rows = [ln.split(',') for ln in csv_out.read_text().splitlines() if not ln.startswith('#')][1:]
    xs = [float(r[0]) for r in rows]; ys = [float(r[1]) for r in rows]
    # x: px 0.1->0, 0.5->3 (a=7.5); y: px 0.2->4.0, 0.7->2.5 (a=-3, b=4.6)
    assert abs(xs[0] - 0.0) < 1e-9 and abs(xs[-1] - 3.0) < 1e-9
    # at x_norm=0.1 y_norm=0.2 -> exactly the calibration point (4.0)
    assert abs(ys[0] - 4.0) < 1e-9


def test_curve_digitize_requires_two_points(tmp_path):
    scan = tmp_path / 'scan.json'
    scan.write_text(json.dumps({'document': {'pdf_filename': 'x', 'pdf_sha256': '0'},
                                'figures': [{'figure_id': 'f', 'page': 1, 'traces': [
                                    {'trace_id': 't', 'points_norm': [[0.1, 0.2], [0.3, 0.3]]}]}]}))
    cal = tmp_path / 'cal.json'
    cal.write_text(json.dumps({'x': {'points': [{'px': [0.1, 0], 'data': [0]}], 'log': False},
                               'y': {'points': [{'px': [0, 0.2], 'data': [4.0]}], 'log': False}}))
    p = run(CRV, 'digitize', '--scan', scan, '--figure', 'f', '--trace', 't', '--calibration', cal)
    assert p.returncode != 0  # fail-closed: 1 point per axis is not enough


# ---------------- review page builder ----------------
def test_build_review_page_inlines_everything(tmp_path):
    rr = tmp_path / 'review_ready.json'
    rr.write_text(json.dumps({'document': {'id': 'T'}, 'parameters': [
        {'id': 'x1', 'name_en': 'X1', 'value': 1.0, 'unit': 'm', 'review_status': 'PENDING',
         'evidence': {'page': 1, 'quote': 'q'}}]}))
    out = tmp_path / 'page.html'
    p = run(BLD, '--review-ready', rr, '--pdf', ROOT / 'examples' / 'synthetic.pdf', '--output', out)
    assert p.returncode == 0, p.stderr
    html = out.read_text()
    assert 'window.__REVIEW_DATA__' in html
    assert '__REVIEW_DATA__ = null' not in html  # data actually injected
    import re
    payload = html.split('window.__REVIEW_DATA__ = ', 1)[1].split(';\n', 1)[0]
    data = json.loads(payload.replace('<\\/script>', '</script>'))
    assert data['document']['id'] == 'T'
    assert data['pdf_base64']


def test_review_template_js_present():
    html = (ROOT / 'assets' / 'review_template.html').read_text()
    for marker in ('tab-curve', 'applyCalibration', 'bindCurve', 'gate-dialog', 'data-cand',
                   "expr://sym", 'data://curve'):
        assert marker in html, f'review template missing HITL feature: {marker}'


# ---------------- pybamm simulation ----------------
def test_pybamm_baseline_defaults_when_review_empty(tmp_path):
    """No reviewed values -> every parameter falls back to the Chen2020 default
    set; the run must stay SOLVED and be conspicuously labeled HYBRID."""
    pytest.importorskip('pybamm')
    blank = tmp_path / 'blank.json'
    assert run(CLI, 'template', '--output', blank).returncode == 0
    out = tmp_path / 'sim' / 'simulation_report.json'
    p = run(PYB, '--reviewed', blank, '--output', out, '--run',
            '--curve-csv', tmp_path / 'sim' / 'sim_1C.csv')
    assert p.returncode == 0, p.stderr
    rep = json.loads(out.read_text())
    assert rep['simulation']['status'] == 'SOLVED'
    assert rep['overrides_applied'] == []          # nothing reviewed -> nothing injected
    assert 'HYBRID' in rep['hybrid_warning']
    assert (tmp_path / 'sim' / 'sim_1C.csv').exists()


def test_run_pipeline_simulate_stage(tmp_path):
    """run_pipeline --simulate: no reviewed JSON -> end-of-pipeline baseline run
    with Chen2020 defaults for the missing parameters."""
    pytest.importorskip('pybamm')
    work = tmp_path / 'work' / 'S'
    p = run(RPL, '--pdf', ROOT / 'examples' / 'synthetic.pdf', '--workdir', work, '--simulate')
    assert p.returncode == 0, p.stderr
    rep = json.loads((work / 'sim' / 'simulation_report.json').read_text())
    assert rep['simulation']['status'] == 'SOLVED'
    assert 'HYBRID' in rep['hybrid_warning']
    assert '45/45' in rep['hybrid_warning']        # every dictionary entry defaulted
    assert (work / 'sim' / 'sim_1C.csv').exists()
