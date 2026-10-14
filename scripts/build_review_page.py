#!/usr/bin/env python3
"""Bundle the full pipeline output into ONE self-contained human-review page.

Takes the review-ready JSON (+ optional tables / formulas / curves JSON and the
original PDF), inlines everything (crops as data: URIs, PDF as base64) into a
copy of assets/review_template.html. The human opens that single file in a
browser: click through parameters, verify evidence against the highlighted PDF,
calibrate curves by clicking axis points, then export the reviewed JSON.

No upload, no server: everything stays on the reviewer's machine.
"""
import argparse, base64, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = 'window.__REVIEW_DATA__ = null; //__INJECT__'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def inline_crops(obj, search_dirs, exts=('.png', '.jpg', '.jpeg')):
    """Recursively rewrite *_png crop paths to data: URIs (found under search_dirs)."""
    cache = {}
    def walk(node):
        if isinstance(node, dict):
            return {k: (data_uri(v, search_dirs, cache) if _is_crop_key(k, v) else walk(v))
                    for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node
    return walk(obj)


def _is_crop_key(key, val):
    return isinstance(val, str) and (key.endswith('png') or key.endswith('_png') or key == 'crop_png') and val.lower().endswith(('.png', '.jpg', '.jpeg'))


def data_uri(rel, search_dirs, cache):
    if rel in cache:
        return cache[rel]
    for d in search_dirs:
        p = (d / rel)
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode('ascii')
            uri = f'data:image/png;base64,{b64}'
            cache[rel] = uri
            return uri
    cache[rel] = rel  # unresolved: keep original path (browser will show broken img, data intact)
    return rel


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--template', default=str(ROOT / 'assets' / 'review_template.html'))
    ap.add_argument('--review-ready', required=True)
    ap.add_argument('--tables')
    ap.add_argument('--formulas')
    ap.add_argument('--curves')
    ap.add_argument('--pdf')
    ap.add_argument('--output', required=True)
    args = ap.parse_args()

    review = load(args.review_ready)
    base_dirs = [Path(args.review_ready).resolve().parent, Path.cwd()]
    if args.tables:
        base_dirs.insert(0, Path(args.tables).resolve().parent)
        review['tables'] = load(args.tables).get('tables', [])
    if args.formulas:
        base_dirs.insert(0, Path(args.formulas).resolve().parent)
        fdata = load(args.formulas)
        review['formulas'] = fdata.get('formulas', [])
        # Pre-compute sympy reference values for display.
        try:
            import sympy as sp
            for f in review['formulas']:
                ref = f.get('value_at_reference') or {}
                try:
                    expr = sp.sympify(f.get('sympy_str') or '')
                    subs = {sp.Symbol(k): sp.Float(v) for k, v in ref.items()}
                    f['evaluated'] = float(expr.subs(subs))
                except Exception:
                    pass
        except ImportError:
            pass
    if args.curves:
        base_dirs.insert(0, Path(args.curves).resolve().parent)
        cdata = load(args.curves)
        review['curves'] = {'figures': cdata.get('figures', [])}

    # Crop paths inside tables/curves/formulas may be relative to their own dirs.
    review = inline_crops(review, base_dirs)

    if args.pdf:
        pdf_bytes = Path(args.pdf).read_bytes()
        review['pdf_base64'] = base64.b64encode(pdf_bytes).decode('ascii')
        review['document'] = {**review.get('document', {}), 'pdf_filename': Path(args.pdf).name,
                              'pdf_sha256': review.get('document', {}).get('pdf_sha256')}

    review['review_meta'] = {
        'generated_by': 'build_review_page.py',
        'instructions': '逐条审核参数 → 表格/公式/曲线证据页核对 → 全部确认或带缺口导出。',
        'human_required': True,
    }

    template = Path(args.template).read_text(encoding='utf-8')
    if MARKER not in template:
        sys.exit('template marker not found; template file mismatch?')
    payload = json.dumps(review, ensure_ascii=False).replace('</script>', '<\\/script>')
    html = template.replace(MARKER, f'window.__REVIEW_DATA__ = {payload};')
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding='utf-8')
    size_mb = out.stat().st_size / 1e6
    n_params = len(review.get('parameters', []))
    print(f'review page: {out} ({size_mb:.1f} MB, {n_params} parameters, '
          f"tables={len(review.get('tables', []))}, formulas={len(review.get('formulas', []))}, "
          f"figures={len(review.get('curves', {}).get('figures', []))}, pdf={'yes' if args.pdf else 'no'})")


if __name__ == '__main__':
    main()
