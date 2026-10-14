#!/usr/bin/env python3
"""Structured table parsing (P0): Docling + PyMuPDF.

Recognizes tables, row/column structure, merged cells and per-cell coordinates
(page + normalized bbox). The parser NEVER interprets scientific meaning: it
only emits cells with provenance. The Claude Code Agent reads `cell value +
quote + page + bbox` and decides what is a parameter, under human review.

Engines
  pymupdf : page.find_tables() with 'lines' and 'text' strategies (fast, text-layer).
  docling : IBM Docling TableFormer (robust for complex/merged/scanned tables; slower).
  auto    : pymupdf first; docling only when nothing substantial is found or --engine docling.
"""
import argparse, hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def bbox_norm(rect, page_rect):
    """Fitz rect -> [x0,y0,x1,y1] normalized, top-left origin (matches locate_evidence.py)."""
    return [round(rect.x0 / page_rect.width, 6), round(rect.y0 / page_rect.height, 6),
            round(rect.x1 / page_rect.width, 6), round(rect.y1 / page_rect.height, 6)]


def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


# ---------------------------------------------------------------- pymupdf ----
def parse_pymupdf(pdf_path, pages=None, min_cols=2, min_rows=2):
    import fitz
    doc = fitz.open(pdf_path)
    out = []
    per_page_counter = {}
    for idx in range(len(doc)):
        if pages and (idx + 1) not in pages:
            continue
        page = doc[idx]
        found = []  # (strategy, table)
        for strategy in ('lines', 'text'):
            try:
                tabs = page.find_tables(strategy=strategy)
            except Exception as exc:  # pragma: no cover
                out.append({'page': idx + 1, 'engine': 'pymupdf', 'strategy': strategy,
                            'error': str(exc), 'rows': [], 'cells': []})
                continue
            for t in tabs.tables:
                # Dedupe strategies on near-identical bbox.
                if any(fitz.Rect(t.bbox).intersects(fitz.Rect(other.bbox))
                       and abs(fitz.Rect(t.bbox).get_area() - fitz.Rect(other.bbox).get_area())
                       < 0.2 * max(1, fitz.Rect(t.bbox).get_area()) for _, other in found):
                    continue
                found.append((strategy, t))
        for strategy, t in found:
            rows = t.extract() or []
            if len(rows) < min_rows or max((len(r) for r in rows), default=0) < min_cols:
                continue
            cells_rects = [fitz.Rect(c) for c in (t.cells or [])]
            # Map each cell rect to (row, col) grid slot for merged-cell detection.
            col_edges = sorted({round(c.x0, 1) for c in cells_rects})
            row_edges = sorted({round(c.y0, 1) for c in cells_rects})
            grid_cells = []
            for ci, r in enumerate(cells_rects):
                text = ''
                try:
                    text = page.get_text('text', clip=r).strip()
                except Exception:
                    pass
                col0 = col_edges.index(round(r.x0, 1)) if round(r.x0, 1) in col_edges else None
                row0 = row_edges.index(round(r.y0, 1)) if round(r.y0, 1) in row_edges else None
                col_span = 1 + sum(1 for e in col_edges if col0 is not None and r.x0 < e < r.x1 - 0.5)
                row_span = 1 + sum(1 for e in row_edges if row0 is not None and r.y0 < e < r.y1 - 0.5)
                grid_cells.append({
                    'cell_id': f'c{ci}', 'bbox_norm': bbox_norm(r, page.rect),
                    'bbox_pt': [round(v, 2) for v in r], 'text': text,
                    'row': row0, 'col': col0,
                    'row_span': row_span, 'col_span': col_span,
                    'is_merged': row_span > 1 or col_span > 1,
                })
            # Row-major table text for readability.
            table_rows = []
            for ri, row_text in enumerate(rows):
                table_rows.append({'row_index': ri,
                                   'cells': [{'col': ci, 'text': (c or '').strip()}
                                             for ci, c in enumerate(row_text)]})
            per_page_counter[idx + 1] = per_page_counter.get(idx + 1, 0) + 1
            out.append({
                'page': idx + 1, 'engine': 'pymupdf', 'strategy': strategy,
                'table_id': f"p{idx+1}_t{per_page_counter[idx+1]}",
                'bbox_norm': bbox_norm(fitz.Rect(t.bbox), page.rect),
                'bbox_pt': [round(v, 2) for v in t.bbox],
                'n_rows': t.row_count, 'n_cols': t.col_count,
                'header': {'external': bool(getattr(t.header, 'external', False)),
                           'cells': [{'col': i, 'text': (c or '').strip()}
                                     for i, c in enumerate(t.header.names or [])]},
                'merged_cells': [c for c in grid_cells if c['is_merged']],
                'rows': table_rows,
                'cells': grid_cells,
            })
    return out


# ---------------------------------------------------------------- docling ----
def parse_docling(pdf_path, pages=None, docling_json=None):
    """Docling TableFormer. Reuses a pre-computed docling JSON when given (expensive run).

    Docling prov bboxes are top-left-origin points in the *visible* (rotated) page
    space, matching PyMuPDF page.rect — verified on landscape/portrait pages.
    """
    import fitz
    doc = fitz.open(pdf_path)
    if docling_json:
        payload = json.loads(Path(docling_json).read_text(encoding='utf-8'))
    else:
        from docling.document_converter import DocumentConverter
        conv = DocumentConverter()
        res = conv.convert(str(pdf_path))
        payload = {'tables': []}
        for i, t in enumerate(res.document.tables):
            prov = t.prov[0] if t.prov else None
            df = t.export_to_dataframe()
            payload['tables'].append({
                'index': i, 'page': prov.page_no if prov else None,
                'bbox': list(prov.bbox.as_tuple()) if prov else None,
                'nrows': t.data.num_rows, 'ncols': t.data.num_cols,
                'grid': df.to_dict('split')['data']})
    out = []
    for i, t in enumerate(payload.get('tables', [])):
        pg = t.get('page')
        if not pg or (pages and pg not in pages) or pg > len(doc):
            continue
        page_rect = doc[pg - 1].rect
        bbox = t.get('bbox')
        bbox_norm = None
        if bbox and page_rect.width > 0:
            bbox_norm = [round(bbox[0] / page_rect.width, 6), round(bbox[1] / page_rect.height, 6),
                         round(bbox[2] / page_rect.width, 6), round(bbox[3] / page_rect.height, 6)]
        grid = t.get('grid') or []
        rows = []
        for ri, row in enumerate(grid):
            rows.append({'row_index': ri,
                         'cells': [{'col': ci, 'text': str(c).strip()} for ci, c in enumerate(row)]})
        out.append({
            'page': pg, 'engine': 'docling',
            'table_id': f'p{pg}_docling_t{i+1}',
            'bbox_norm': bbox_norm,
            'bbox_pt_docling': bbox,
            'n_rows': t.get('nrows'), 'n_cols': t.get('ncols'),
            'header': {'external': None, 'cells': (rows[0]['cells'] if rows else [])},
            'merged_cells': [], 'rows': rows, 'cells': [],
        })
    return out


def render_crops(pdf_path, tables, outdir):
    import fitz
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    for t in tables:
        pg = t.get('page')
        if not pg or pg > len(doc):
            continue
        page = doc[pg - 1]
        clip = None
        if t.get('bbox_pt'):
            clip = fitz.Rect(t['bbox_pt'])
        elif t.get('bbox_norm'):
            b = t['bbox_norm']
            clip = fitz.Rect(b[0] * page.rect.width, b[1] * page.rect.height,
                             b[2] * page.rect.width, b[3] * page.rect.height)
        if clip is None or clip.is_empty:
            continue
        pix = page.get_pixmap(clip=clip, dpi=200)
        name = f"{t['table_id']}.png"
        pix.save(outdir / name)
        t['crop_png'] = str(Path(outdir).name + '/' + name)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pdf', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--pages', help='1-based page numbers, e.g. "19" or "2,19"')
    ap.add_argument('--engine', default='auto', choices=['auto', 'pymupdf', 'docling'])
    ap.add_argument('--docling-json', help='reuse a pre-computed docling dump instead of running Docling')
    ap.add_argument('--crops', help='directory to render table crop PNGs into')
    args = ap.parse_args()
    pages = {int(x) for x in args.pages.split(',')} if args.pages else None

    pdf_path = Path(args.pdf)
    tables, warnings = [], []
    if args.engine in ('auto', 'pymupdf'):
        tables = parse_pymupdf(pdf_path, pages)
        if not tables:
            warnings.append('pymupdf found no substantial tables (>=2x2)')
    if args.engine == 'docling' or (args.engine == 'auto' and (args.docling_json or not tables)):
        try:
            # auto mode merges both engines (tagged per table); docling-only mode replaces.
            docling_tables = parse_docling(pdf_path, pages, args.docling_json)
            tables = tables + docling_tables if args.engine == 'auto' else docling_tables
        except Exception as exc:
            warnings.append(f'docling engine failed: {exc}')
    if args.crops:
        render_crops(pdf_path, tables, args.crops)

    payload = {
        'schema_version': 'p2d-tables-v1',
        'document': {'pdf_filename': pdf_path.name, 'pdf_sha256': sha256(pdf_path)},
        'engine_requested': args.engine,
        'n_tables': len(tables),
        'methodology': {
            'cells_carry_page_and_bbox_norm': True,
            'merged_cells': 'span>1 marks cells spanning several row/col boundaries',
            'no_semantic_interpretation': 'Agent + human review decide what a cell means',
        },
        'tables': tables, 'warnings': warnings,
    }
    save(args.output, payload)
    print(f"tables={len(tables)} warnings={warnings} -> {args.output}")
    sys.exit(0)


if __name__ == '__main__':
    main()
