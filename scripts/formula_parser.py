#!/usr/bin/env python3
"""Scientific formula parsing (P0): candidate scan + SymPy validation.

PDF text layers scramble inline math (superscripts/subscripts out of order), so
this module is deliberately split:

  scan     -> deterministic candidate detection from the PDF text layer:
              equations numbered "(N)", math-symbol lines; renders a crop PNG
              per candidate and dumps the raw word grid. NO interpretation.
  (Agent)  -> the Claude Code Agent reads the crop images ("视觉模型") and
              reconstructs each equation as a SymPy-parseable string with
              declared variables and units.
  validate -> SymPy parse + symbol coverage + finite numeric evaluation +
              optional dimensional consistency check. Fail-closed statuses.

Nothing here extracts a value by itself; every formula stays PENDING until a
human approves it in the review HTML.
"""
import argparse, hashlib, json, re, sys
from pathlib import Path


def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


MATH_HINTS = re.compile(r'(\beq|exp\s*\(|log\s*\(|=|\bE\s*a\b|·|−|\^|∫|Σ|∂)', re.I)


# ------------------------------------------------------------------ scan -----
def scan(pdf_path, output, pages=None, crops_dir='work/formula_crops', max_per_page=12):
    import fitz
    doc = fitz.open(pdf_path)
    crops = Path(crops_dir); crops.mkdir(parents=True, exist_ok=True)
    eq_re = re.compile(r'^\((\d{1,3})[).,:]?$')  # standalone "(23)" token
    candidates = []
    for idx in range(len(doc)):
        if pages and (idx + 1) not in pages:
            continue
        page = doc[idx]
        words = page.get_text('words')  # x0,y0,x1,y1,word,block,line,word_no
        if not words:
            continue
        # Group words into text lines by (block, line).
        lines = {}
        for w in words:
            key = (w[5], w[6])
            lines.setdefault(key, []).append(w)
        for key, ws in lines.items():
            ws.sort(key=lambda w: w[0])
            tokens = [w[4] for w in ws]
            mathish = sum(1 for tok in tokens if MATH_HINTS.search(tok))
            # Equation-number anchor: "(23)" or a bare 1-2 digit number at line
            # end (text layers often split the parentheses into separate words).
            anchor = None
            for j, tok in enumerate(tokens):
                t = tok.strip().strip('[],')
                if j < len(tokens) - 3:
                    continue
                if eq_re.fullmatch(f'({t})') or eq_re.fullmatch(t):
                    anchor = (j, re.search(r'\d+', t).group(0))
                elif re.fullmatch(r'\d{1,2}', t) and mathish >= 2:
                    anchor = (j, t)
            if not anchor and mathish < 2:
                continue
            eq_no = anchor[1] if anchor else None
            region = fitz.Rect(ws[0][:4])
            for w in ws:
                region |= fitz.Rect(w[:4])
            # Expand region to nearby lines in the same block (equations wrap).
            for key2, ws2 in lines.items():
                if key2[0] != key[0]:
                    continue
                r2 = fitz.Rect(ws2[0][:4])
                for w in ws2:
                    r2 |= fitz.Rect(w[:4])
                if r2.y0 < region.y1 + 14 and r2.y1 > region.y0 - 14:
                    region |= r2
            region = (region + (-6, -8, 6, 8)) & page.rect
            raw = ' '.join(tokens)
            cand = {
                'candidate_id': f'p{idx+1}_eq{eq_no or len(candidates)+1}',
                'page': idx + 1, 'eq_no': int(eq_no) if eq_no else None,
                'raw_text': raw[:500],
                'n_math_tokens': mathish,
                'detection': 'eq_number_anchor' if anchor else 'math_symbol_density',
                'region_bbox_norm': [round(region.x0 / page.rect.width, 6),
                                     round(region.y0 / page.rect.height, 6),
                                     round(region.x1 / page.rect.width, 6),
                                     round(region.y1 / page.rect.height, 6)],
                'region_bbox_pt': [round(v, 2) for v in region],
                'words': [[round(w[0], 1), round(w[1], 1), w[4]] for w in ws[:80]],
            }
            candidates.append(cand)
        # Render crops for this page's candidates (after region merge above).
        for cand in [c for c in candidates if c['page'] == idx + 1]:
            r = fitz.Rect(cand['region_bbox_pt'])
            pix = page.get_pixmap(clip=r, dpi=220)
            name = f"{cand['candidate_id']}.png"
            pix.save(crops / name)
            cand['crop_png'] = str(Path(crops_dir).name + '/' + name)
        # Cap per-page noise.
        page_cands = [c for c in candidates if c['page'] == idx + 1]
        if len(page_cands) > max_per_page:
            page_cands.sort(key=lambda c: (-c['n_math_tokens'], -(1 if c['eq_no'] else 0)))
            drop = {c['candidate_id'] for c in page_cands[max_per_page:]}
            candidates = [c for c in candidates if c['candidate_id'] not in drop]

    # Filter page furniture and near-duplicate regions (same page, same eq_no,
    # overlapping regions) — the scan is intentionally over-inclusive otherwise.
    NOISE = re.compile(r'Journal of The Electrochemical|Downloaded via|This article is', re.I)
    candidates = [c for c in candidates if not NOISE.search(c['raw_text'])]
    deduped = []
    for c in sorted(candidates, key=lambda c: -(1 if c['eq_no'] else 0)):
        dup = False
        for d in deduped:
            if d['page'] == c['page'] and d['eq_no'] and c['eq_no'] and d['eq_no'] == c['eq_no']:
                a, b = fitz.Rect(c['region_bbox_pt']), fitz.Rect(d['region_bbox_pt'])
                if a.intersects(b):
                    dup = True
                    break
        if not dup:
            deduped.append(c)
    candidates = deduped

    payload = {
        'schema_version': 'p2d-formulas-scan-v1',
        'document': {'pdf_filename': Path(pdf_path).name, 'pdf_sha256': sha256(pdf_path)},
        'n_candidates': len(candidates),
        'methodology': {
            'raw_text_is_scrambled': 'PDF text layer order is unreliable for math; trust crop image + Agent reconstruction',
            'next_step': 'Agent reads each crop, fills formulas_agent.json with sympy_str + variables + units; then run validate',
        },
        'candidates': candidates,
    }
    save(output, payload)
    print(f"candidates={len(candidates)} -> {output} (crops in {crops})")


# -------------------------------------------------------------- validate -----
# Unit string -> dimension exponent vector (tokens: m, s, kg, mol, A, K, plus
# derived electrical units resolved against SI base dimensions).
BASE_DIMS = {'m': 'L', 's': 'T', 'kg': 'M', 'mol': 'N', 'A': 'I', 'K': 'Θ'}
DERIVED_DIMS = {
    'V': {'M': 1, 'L': 2, 'T': -3, 'I': -1},          # volt
    'S': {'M': -1, 'L': -2, 'T': 3, 'I': 2},          # siemens
    'J': {'M': 1, 'L': 2, 'T': -2},                   # joule
    'C': {'T': 1, 'I': 1},                            # coulomb
    'F': {'M': -1, 'L': -2, 'T': 4, 'I': 2},          # farad
    'h': {'T': 1},                                    # hour
    'Hz': {'T': -1},
    'W': {'M': 1, 'L': 2, 'T': -3},
    'Ω': {'M': 1, 'L': 2, 'T': -3, 'I': -2},
}
TOKEN_RE = re.compile(r'^([A-Za-zΩµ]+?)([+-]?\d+)?$')
# SI prefixes change scale, never dimension — strip them before matching units.
SI_PREFIXES = ('da', 'h', 'k', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y',
               'd', 'c', 'm', 'µ', 'u', 'n', 'p', 'f', 'a', 'z', 'y')


def _unit_token_dims(name):
    if name in BASE_DIMS:
        return {BASE_DIMS[name]: 1}
    if name in DERIVED_DIMS:
        return dict(DERIVED_DIMS[name])
    for p in SI_PREFIXES:
        if name.startswith(p) and len(name) > len(p):
            stripped = name[len(p):]
            if stripped in BASE_DIMS:
                return {BASE_DIMS[stripped]: 1}
            if stripped in DERIVED_DIMS:
                return dict(DERIVED_DIMS[stripped])
    return None


def unit_dims(unit):
    """'m2.s-1', 'mol.dm-3', 'S.m-1', 'V', '1' -> {'L':2,'T':-1} or None if unknown."""
    if unit in (None, '', '1', 'dimensionless', '-'):
        return {}
    dims = {}
    for tok in str(unit).replace('·', '.').split('.'):
        tok = tok.strip()
        m = TOKEN_RE.match(tok)
        if not m:
            return None
        name, exp = m.group(1), int(m.group(2) or 1)
        base = _unit_token_dims(name)
        if base is None:
            return None
        for k, v in base.items():
            dims[k] = dims.get(k, 0) + v * exp
    return dims


def _check_exp_args(expr, var_dims):
    """Structural check: exp()/log() arguments must be dimensionless (numeric laws)."""
    import sympy as sp
    expr = sp.sympify(expr)
    for node in sp.preorder_traversal(expr):
        if node.func in (sp.exp, sp.log):
            ad = dims_of_expr(node.args[0], var_dims)
            if ad and any(v != 0 for v in ad.values()):
                raise ValueError(f'{node.func} argument must be dimensionless, got {ad}')


def dims_of_expr(expr, var_dims):
    """Dimension vector of a sympy expression given var->dims map. None = undecidable."""
    import sympy as sp
    expr = sp.sympify(expr)
    if expr.is_Number:
        return {}
    if isinstance(expr, sp.Symbol):
        return var_dims.get(str(expr))
    if isinstance(expr, (sp.exp, sp.log)) or expr.func in (sp.exp, sp.log):
        arg = expr.args[0]
        ad = dims_of_expr(arg, var_dims)
        if ad is None or any(v != 0 for v in ad.values()):
            raise ValueError(f'{expr.func} argument must be dimensionless, got {ad}')
        return {}
    if isinstance(expr, sp.Pow):
        base = dims_of_expr(expr.base, var_dims)
        expo = expr.exp
        if base is None:
            return None
        if not base:            # dimensionless base: any exponent stays dimensionless
            return {}
        if isinstance(expo, sp.Integer):
            return {k: v * int(expo) for k, v in base.items()}
        return None  # non-integer power of a dimensionful quantity
    if isinstance(expr, (sp.Add,)):
        acc = None
        for a in expr.args:
            d = dims_of_expr(a, var_dims)
            if d is None:
                return None
            if acc is None:
                acc = d
            elif acc != d:
                raise ValueError(f'Add terms disagree in dimensions: {acc} vs {d}')
        return acc or {}
    if isinstance(expr, (sp.Mul,)):
        acc = {}
        for a in expr.args:
            d = dims_of_expr(a, var_dims)
            if d is None:
                return None
            for k, v in d.items():
                acc[k] = acc.get(k, 0) + v
        acc = {k: v for k, v in acc.items() if v != 0}
        return acc
    # Unknown function: undecidable.
    return None


def same_dims(a, b):
    a = {k: v for k, v in (a or {}).items() if v}
    b = {k: v for k, v in (b or {}).items() if v}
    return a == b


def validate(input_json, output):
    src = json.loads(Path(input_json).read_text(encoding='utf-8'))
    import sympy as sp
    PRIORITY = ['PARSE_ERROR', 'SYMBOL_MISMATCH', 'DIMENSION_MISMATCH', 'NONFINITE']
    results = []
    ok_count = 0
    for f in src.get('formulas', []):
        checks, failed = [], set()
        sympy_str = f.get('sympy_str') or ''
        expr = None
        try:
            expr = sp.sympify(sympy_str, locals={'E': sp.E})
            checks.append({'check': 'sympy_parse', 'ok': True,
                           'detail': f'free_symbols={sorted(map(str, expr.free_symbols))}'})
        except Exception as exc:
            checks.append({'check': 'sympy_parse', 'ok': False, 'detail': str(exc)})
            failed.add('PARSE_ERROR')
        declared = {v['symbol']: v for v in f.get('variables', [])}
        if expr is not None:
            undeclared = sorted(str(s) for s in expr.free_symbols if str(s) not in declared)
            if undeclared:
                checks.append({'check': 'symbol_coverage', 'ok': False,
                               'detail': f'undeclared symbols: {undeclared}'})
                failed.add('SYMBOL_MISMATCH')
            else:
                checks.append({'check': 'symbol_coverage', 'ok': True, 'detail': 'all symbols declared'})
            # Finite numeric evaluation at reference values.
            ref = f.get('value_at_reference') or {}
            try:
                subs = {}
                for sym in expr.free_symbols:
                    v = ref.get(str(sym))
                    if v is None:
                        raise ValueError(f"missing reference value for '{sym}'")
                    subs[sym] = sp.Float(v)
                val = float(expr.subs(subs))
                finite = val == val and abs(val) != float('inf')
                checks.append({'check': 'numeric_reference', 'ok': finite,
                               'detail': f'{"finite" if finite else "non-finite"} value {val}'})
                if finite:
                    f['evaluated'] = val
                else:
                    failed.add('NONFINITE')
            except Exception as exc:
                checks.append({'check': 'numeric_reference', 'ok': False, 'detail': str(exc)})
                failed.add('NONFINITE')
            # Dimensional consistency. Strict comparison is only decidable when ALL
            # variables are declared and dimensionless. Otherwise the expression is
            # a "numeric law" whose pure-number coefficients implicitly carry units
            # — we then check only STRUCTURAL errors (dimensionful exp/log args)
            # and leave unit assignment to the human.
            try:
                var_dims = {}
                undecidable = []
                for sym, meta in declared.items():
                    d = unit_dims(meta.get('unit'))
                    if d is None:
                        undecidable.append(sym)
                    else:
                        var_dims[sym] = d
                lhs = unit_dims(f.get('lhs_unit'))
                if f.get('lhs_unit') and lhs is None:
                    checks.append({'check': 'dimensional_consistency', 'ok': None,
                                   'detail': f"unrecognized lhs unit '{f.get('lhs_unit')}'"})
                elif undecidable:
                    checks.append({'check': 'dimensional_consistency', 'ok': None,
                                   'detail': 'undecidable (unknown units) — human decides'})
                elif declared and all(not d for d in var_dims.values()):
                    rhs = dims_of_expr(expr, var_dims)
                    agree = rhs is not None and same_dims(rhs, lhs or {})
                    checks.append({'check': 'dimensional_consistency', 'ok': agree,
                                   'detail': f'lhs={lhs} rhs={rhs} (all variables dimensionless)'})
                    if not agree:
                        failed.add('DIMENSION_MISMATCH')
                elif not declared:
                    checks.append({'check': 'dimensional_consistency', 'ok': None,
                                   'detail': 'no variables declared — nothing to check; human decides'})
                else:
                    _check_exp_args(expr, var_dims)
                    checks.append({'check': 'dimensional_consistency', 'ok': None,
                                   'detail': f'numeric law: coefficients implicitly carry units (variables={var_dims}); exp/log args dimensionless OK — human confirms'})
            except ValueError as exc:
                checks.append({'check': 'dimensional_consistency', 'ok': False, 'detail': str(exc)})
                failed.add('DIMENSION_MISMATCH')
        status = next((p for p in PRIORITY if p in failed), 'VALIDATED')
        results.append({**f, 'validation_status': status, 'checks': checks,
                        'human_review_status': 'PENDING'})
        if status == 'VALIDATED':
            ok_count += 1
    payload = {
        'schema_version': 'p2d-formulas-validated-v1',
        'document': src.get('document', {}),
        'summary': {'total': len(results), 'validated': ok_count,
                    'statuses': {s: sum(1 for r in results if r['validation_status'] == s)
                                 for s in {r['validation_status'] for r in results}}},
        'methodology': {'symyy_checks': ['sympy_parse', 'symbol_coverage', 'numeric_reference', 'dimensional_consistency'],
                        'human_review_required': 'VALIDATED only means mathematically consistent, NOT that it matches the paper'},
        'formulas': results,
    }
    save(output, payload)
    print(f"formulas={len(results)} validated={ok_count} -> {output}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('scan')
    s.add_argument('--pdf', required=True); s.add_argument('--output', required=True)
    s.add_argument('--pages'); s.add_argument('--crops', default='work/formula_crops')
    s.add_argument('--max-per-page', type=int, default=12)
    s.set_defaults(func=lambda a: scan(a.pdf, a.output,
                                       {int(x) for x in a.pages.split(',')} if a.pages else None,
                                       a.crops, a.max_per_page))
    v = sub.add_parser('validate')
    v.add_argument('--input', required=True, help='formulas_agent.json filled by the Agent')
    v.add_argument('--output', required=True)
    v.set_defaults(func=lambda a: validate(a.input, a.output))
    args = ap.parse_args(); args.func(args)


if __name__ == '__main__':
    main()
