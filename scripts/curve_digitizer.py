#!/usr/bin/env python3
"""Research curve digitization (P1): WebPlotDigitizer-inspired pipeline.

  scan      -> per page: extract embedded raster figures (PyMuPDF) and vector
               drawings; OpenCV detects the plot frame and colored curve pixels
               in rasters; vector strokes are extracted directly from the PDF
               drawing paths (exact, when the figure is not a bitmap). Emits
               figure crops + UNCALIBRATED pixel traces. No data values yet.
  (calib)   -> axis calibration points {pixel -> data value}, supplied by the
               Agent (视觉模型 reading the crop) and CONFIRMED by the human in
               the review HTML (click-2-points-per-axis interaction).
  digitize  -> applies the approved calibration (linear or log axes) to the
               pixel trace and writes the final CSV + provenance.

All coordinates are stored normalized to the crop box [0..1] (top-left origin)
so HTML clicks and offline finalize agree regardless of render resolution.
"""
import argparse, csv, hashlib, json, math, sys
from pathlib import Path


def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------- raster: OpenCV ------
def raster_traces(img_path, min_trace_pixels=60, exclude_norm=None):
    """Detect plot frame + curve traces in a raster figure. Returns dict.

    exclude_norm: list of [x0,y0,x1,y1] boxes (normalized) to mask out — the
    WebPlotDigitizer-style human exclusion of legends/annotations.
    """
    import cv2
    import numpy as np
    img = cv2.imread(str(img_path))
    if img is None:
        return {'error': 'unreadable image'}
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ink = (gray < 200).astype(np.uint8)  # dark pixels
    if exclude_norm:
        for b in exclude_norm:
            x0, y0, x1, y1 = [int(round(v * (w if i % 2 == 0 else h))) for i, v in enumerate(b)]
            ink[max(0, y0):min(h, y1), max(0, x0):min(w, x1)] = 0

    # --- plot frame: strongest horizontal/vertical ink lines -------------
    col_ink = ink.sum(axis=0) / h    # per-x fraction
    row_ink = ink.sum(axis=1) / w
    v_lines = [int(x) for x in range(w) if col_ink[x] > 0.55]
    h_lines = [int(y) for y in range(h) if row_ink[y] > 0.55]

    def collapse(idxs, min_gap=4):
        groups, cur = [], []
        for i in idxs:
            if cur and i - cur[-1] <= min_gap:
                cur.append(i)
            else:
                if cur:
                    groups.append(int(np.mean(cur)))
                cur = [i]
        if cur:
            groups.append(int(np.mean(cur)))
        return groups

    v_lines, h_lines = collapse(v_lines), collapse(h_lines)
    frame = None
    if len(v_lines) >= 2 and len(h_lines) >= 2:
        frame = {'left': v_lines[0], 'right': v_lines[-1],
                 'top': h_lines[0], 'bottom': h_lines[-1]}
    axes_candidates = {'vertical_lines_px': v_lines, 'horizontal_lines_px': h_lines}

    # --- curve pixels: colored strokes inside the frame -------------------
    traces = []
    box = frame or {'left': 0, 'right': w - 1, 'top': 0, 'bottom': h - 1}
    sat = hsv[:, :, 1]
    colored = ((sat > 60) & (hsv[:, :, 2] > 60)).astype(np.uint8)
    if exclude_norm:
        for b in exclude_norm:
            x0, y0, x1, y1 = [int(round(v * (w if i % 2 == 0 else h))) for i, v in enumerate(b)]
            colored[max(0, y0):min(h, y1), max(0, x0):min(w, x1)] = 0
    colored[:box['top'] + 2, :] = 0; colored[box['bottom'] - 1:, :] = 0
    colored[:, :box['left'] + 2] = 0; colored[:, box['right'] - 1:] = 0
    n_colored = int(colored.sum())
    if n_colored >= min_trace_pixels:
        # Cluster colored pixels by hue band (each curve usually one hue).
        hue = hsv[:, :, 0]
        hues = hue[colored > 0]
        hist, edges = np.histogram(hues, bins=18, range=(0, 180))
        for bi in np.argsort(hist)[::-1]:
            if hist[bi] < min_trace_pixels:
                break
            lo, hi = int(edges[bi]), int(edges[bi + 1])
            mask = colored & (((hue >= lo) & (hue < hi)).astype(np.uint8))
            pts = _order_curve(np.column_stack(np.nonzero(mask.T)))  # (x,y)
            if len(pts) >= min_trace_pixels:
                for si, seg in enumerate(_split_on_gap(pts)):
                    traces.append({
                        'trace_id': f'color_hue{lo}-{hi}' + (f'_seg{si+1}' if si else ''),
                        'color_hint': f'hue[{lo},{hi})',
                        'n_points': int(len(seg)),
                        'points_norm': [[round(x / w, 5), round(y / h, 5)] for x, y in seg[::2]],
                    })
            if len(traces) >= 8:
                break
    # Grayscale curves: ink inside frame minus axis lines, ordered by x
    # (may capture experimental bands / black model lines; human filters).
    m = ink.copy()
    m[:box['top'] + 2, :] = 0; m[box['bottom'] - 1:, :] = 0
    m[:, :box['left'] + 2] = 0; m[:, box['right'] - 1:] = 0
    m &= ~colored  # colored strokes already separate
    for x in v_lines:
        m[:, max(0, x - 2):x + 3] = 0
    for y in h_lines:
        m[max(0, y - 2):y + 3, :] = 0
    pts = _order_curve(np.column_stack(np.nonzero(m.T)))
    if len(pts) >= min_trace_pixels:
        for si, seg in enumerate(_split_on_gap(pts)):
            traces.append({'trace_id': 'gray_ink' + (f'_seg{si+1}' if si else ''),
                           'color_hint': 'grayscale',
                           'n_points': int(len(seg)),
                           'points_norm': [[round(x / w, 5), round(y / h, 5)] for x, y in seg[::2]]})

    frame_norm = None
    if frame:
        frame_norm = {'left': round(box['left'] / w, 5), 'right': round(box['right'] / w, 5),
                      'top': round(box['top'] / h, 5), 'bottom': round(box['bottom'] / h, 5)}
    return {'size_px': [w, h], 'plot_frame_px': frame, 'plot_frame_norm': frame_norm,
            'axes_candidates': axes_candidates, 'traces': traces}


def _split_on_gap(pts, rel_gap=0.045):
    """Split an ordered polyline where consecutive x jump (multi-panel figures)."""
    import numpy as np
    if len(pts) < 8:
        return [pts]
    xs = pts[:, 0]
    w = xs.max() - xs.min()
    gaps = np.nonzero(np.diff(xs) > rel_gap * max(w, 1))[0]
    if not len(gaps):
        return [pts]
    segs, start = [], 0
    for g in list(gaps) + [len(xs) - 1]:
        seg = pts[start:g + 1]
        if len(seg) >= 8:
            segs.append(seg)
        start = g + 1
    return segs or [pts]


def _order_curve(pts_xy, max_gap=None):
    """Order raw pixel set into a path. Function-like data: sort by x and mean-y."""
    import numpy as np
    if len(pts_xy) == 0:
        return pts_xy
    xs = pts_xy[:, 0]
    order = np.argsort(xs, kind='stable')
    pts = pts_xy[order]
    # bin by x (1px) and average y -> robust polyline for function-like curves
    out = []
    cur_x, ys = None, []
    for x, y in pts:
        if cur_x is None or x == cur_x:
            cur_x, ys = x, ys + [y]
        else:
            out.append((float(cur_x), float(np.mean(ys))))
            cur_x, ys = x, [y]
    if cur_x is not None:
        out.append((float(cur_x), float(np.mean(ys))))
    return np.round(np.array(out), 2)


# ------------------------------------------------------ vector drawings ------
def vector_traces(page, crop_rect=None, min_points=12):
    """Extract curve-like vector strokes from PDF drawings (exact geometry)."""
    import fitz
    strokes = {}
    for d in page.get_drawings():
        color = d.get('color')
        if color is None:
            continue
        width = round(float(d.get('width') or 0), 2)
        pts = []
        for item in d['items']:
            if item[0] == 'l':
                pts += [item[1], item[2]]
            elif item[0] == 'c':
                pts += [item[1], item[4]]  # endpoints of bezier
        if len(pts) < min_points:
            continue
        key = (tuple(round(c, 3) for c in color), width)
        strokes.setdefault(key, [])
        strokes[key] += pts
    out = []
    for (color, width), pts in strokes.items():
        arr = [(p.x, p.y) for p in pts]
        if crop_rect is not None:
            arr = [(x, y) for x, y in arr
                   if crop_rect.x0 <= x <= crop_rect.x1 and crop_rect.y0 <= y <= crop_rect.y1]
        if len(arr) < min_points:
            continue
        out.append({'color_rgb': list(color), 'width': width,
                    'n_points': len(arr), 'points_pt': [[round(x, 2), round(y, 2)] for x, y in arr]})
    out.sort(key=lambda s: -s['n_points'])
    return out


# ---------------------------------------------------------------- scan -------
def scan(pdf_path, output, pages=None, crops_dir='work/curve_crops', max_raster_px=2400, region=None, exclude=None):
    import fitz
    doc = fitz.open(pdf_path)
    crops = Path(crops_dir); crops.mkdir(parents=True, exist_ok=True)
    figures = []
    region_rect = None
    if region:
        x0, y0, x1, y1 = map(float, region.split(','))
        region_rect = fitz.Rect(x0, y0, x1, y1)  # normalized; scaled per page below
    for idx in range(len(doc)):
        if pages and (idx + 1) not in pages:
            continue
        page = doc[idx]
        page_region = None
        if region_rect is not None:
            page_region = fitz.Rect(region_rect.x0 * page.rect.width, region_rect.y0 * page.rect.height,
                                    region_rect.x1 * page.rect.width, region_rect.y1 * page.rect.height)
        # --- embedded raster images -------------------------------------
        seen_xref = set()
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            if xref in seen_xref:
                continue
            seen_xref.add(xref)
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                rects = []
            if not rects:
                continue
            full_bbox = rects[0]
            bbox = full_bbox
            if page_region is not None:
                bbox = bbox & page_region
                if bbox.is_empty or bbox.width < 80:
                    continue
            if bbox.width < 120 or bbox.height < 90:
                continue  # skip logos/decoration
            extract = doc.extract_image(xref)
            raw = crops / f'p{idx+1}_img{img_index}_raw.{extract["ext"]}'
            raw.write_bytes(extract['image'])
            # Downscale for detection (speed) but keep original for quality.
            import cv2
            im = cv2.imread(str(raw))
            if im is None:
                continue
            # Crop to the requested region at pixel level (multi-panel figures).
            if page_region is not None:
                ih, iw = im.shape[:2]
                px0 = int(round((bbox.x0 - full_bbox.x0) / full_bbox.width * iw))
                px1 = int(round((bbox.x1 - full_bbox.x0) / full_bbox.width * iw))
                py0 = int(round((bbox.y0 - full_bbox.y0) / full_bbox.height * ih))
                py1 = int(round((bbox.y1 - full_bbox.y0) / full_bbox.height * ih))
                im = im[max(0, py0):max(0, py1), max(0, px0):max(0, px1)]
            scale = min(1.0, max_raster_px / max(im.shape[:2]))
            if scale < 1.0:
                im = cv2.resize(im, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            small = crops / f'p{idx+1}_img{img_index}.png'
            cv2.imwrite(str(small), im)
            analysis = raster_traces(small, exclude_norm=exclude)
            # Page-visible crop of the same region (context incl. axis labels).
            pix = page.get_pixmap(clip=bbox, dpi=200)
            crop = f'p{idx+1}_img{img_index}_page.png'
            pix.save(crops / crop)
            figures.append({
                'figure_id': f'p{idx+1}_img{img_index}', 'page': idx + 1,
                'source': 'raster_image', 'image_xref': xref,
                'bbox_norm': [round(bbox.x0 / page.rect.width, 6), round(bbox.y0 / page.rect.height, 6),
                              round(bbox.x1 / page.rect.width, 6), round(bbox.y1 / page.rect.height, 6)],
                'crop_png': str(Path(crops_dir).name + '/' + crop),
                'analysis_png': str(Path(crops_dir).name + '/' + small.name),
                **analysis,
            })
        # --- vector drawings on the page ---------------------------------
        vstrokes = vector_traces(page)
        if len(vstrokes) >= 3:
            region = fitz.Rect()
            for s in vstrokes[:8]:
                for x, y in s['points_pt'][:50]:
                    region |= fitz.Rect(x, y, x, y)
            if not region.is_empty:
                region = (region + (-14, -14, 14, 14)) & page.rect
                pix = page.get_pixmap(clip=region, dpi=200)
                crop = f'p{idx+1}_vector.png'
                pix.save(crops / crop)
                for s in vstrokes:
                    s['points_norm'] = [[round((x - region.x0) / region.width, 5),
                                         round((y - region.y0) / region.height, 5)] for x, y in s['points_pt'][::2]]
                figures.append({
                    'figure_id': f'p{idx+1}_vector', 'page': idx + 1,
                    'source': 'vector_drawings',
                    'bbox_norm': [round(region.x0 / page.rect.width, 6), round(region.y0 / page.rect.height, 6),
                                  round(region.x1 / page.rect.width, 6), round(region.y1 / page.rect.height, 6)],
                    'crop_png': str(Path(crops_dir).name + '/' + crop),
                    'traces': [{'trace_id': f'stroke_{i}', 'color_rgb': s['color_rgb'],
                                'n_points': s['n_points'], 'points_norm': s['points_norm']}
                               for i, s in enumerate(vstrokes)],
                })
    payload = {
        'schema_version': 'p2d-curves-scan-v1',
        'document': {'pdf_filename': Path(pdf_path).name, 'pdf_sha256': sha256(pdf_path)},
        'n_figures': len(figures),
        'methodology': {
            'uncalibrated': 'traces are pixel coordinates; values require axis calibration',
            'calibration': 'points[{px:[x,y],data:[x_val,y_val]}] normalized to crop box; human-confirmed in review HTML',
            'vector_exact': 'vector strokes carry exact PDF path geometry (no pixel error)',
        },
        'figures': figures,
    }
    save(output, payload)
    print(f"figures={len(figures)} -> {output} (crops in {crops})")


# ------------------------------------------------------------- digitize ------
def _fit_axis(pairs, log):
    """pairs: [(px, data)] -> (a,b) with data = a*px+b (log: log10(data))."""
    import numpy as np
    px = np.array([p[0] for p in pairs], float)
    dv = np.array([math.log10(p[1]) if log else p[1] for p in pairs], float)
    if len(px) < 2 or np.ptp(px) == 0:
        raise ValueError('need >=2 calibration points with distinct pixel positions')
    a, b = np.polyfit(px, dv, 1)
    resid = dv - (a * px + b)
    return float(a), float(b), float(np.max(np.abs(resid)))


def _axis_value(p, axis):
    """Calibration point value: accept {data: scalar} (HTML convention, axis-tagged)
    or {data: [x_val, y_val]} (WebPlotDigitizer-style pairs)."""
    d = p.get('data')
    if isinstance(d, (list, tuple)):
        if not d:
            raise ValueError('empty calibration data point')
        if len(d) == 1:
            return d[0]
        return d[0] if axis == 'x' else d[1]
    return d


def digitize(scan_json, figure_id, trace_id, calib, output_csv=None, output_json=None):
    scan = json.loads(Path(scan_json).read_text(encoding='utf-8'))
    fig = next(f for f in scan['figures'] if f['figure_id'] == figure_id)
    tr = next(t for t in fig['traces'] if t['trace_id'] == trace_id)
    pts = tr['points_norm']  # [x,y] in [0..1] of crop
    ax, ay = calib['x'], calib['y']
    a_x, b_x, rx = _fit_axis([(p['px'][0], _axis_value(p, 'x')) for p in ax['points']], ax.get('log', False))
    a_y, b_y, ry = _fit_axis([(p['px'][1], _axis_value(p, 'y')) for p in ay['points']], ay.get('log', False))
    rows = []
    for x, y in pts:
        dx = a_x * x + b_x
        dy = a_y * y + b_y
        if ax.get('log'):
            dx = 10 ** dx
        if ay.get('log'):
            dy = 10 ** dy
        rows.append([dx, dy])
    rows.sort(key=lambda r: r[0])
    # provenance header
    header = [
        f"# digitized_curve figure={figure_id} trace={trace_id} source={fig['source']}",
        f"# pdf={scan['document']['pdf_filename']} sha256={scan['document']['pdf_sha256'][:16]}...",
        f"# x_axis={ax.get('label','')} unit={ax.get('unit','')} log={ax.get('log',False)}",
        f"# y_axis={ay.get('label','')} unit={ay.get('unit','')} log={ay.get('log',False)}",
        f"# calibration_x={[(p['px'],p['data']) for p in ax['points']]} max_residual={rx:.4g}",
        f"# calibration_y={[(p['px'],p['data']) for p in ay['points']]} max_residual={ry:.4g}",
        f"# approved_by={calib.get('approved_by','human_review')} reviewed={calib.get('reviewed', False)}",
        f"# n_points={len(rows)}",
    ]
    if output_csv:
        Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
        with open(output_csv, 'w', newline='', encoding='utf-8') as fh:
            for line in header:
                fh.write(line + '\n')
            w = csv.writer(fh)
            w.writerow([ax.get('column', 'x'), ay.get('column', 'y')])
            w.writerows(rows)
    payload = {
        'schema_version': 'p2d-curve-digitized-v1',
        'figure_id': figure_id, 'trace_id': trace_id,
        'x': {'label': ax.get('label'), 'unit': ax.get('unit'), 'log': ax.get('log', False),
              'calibration': ax, 'fit': {'a': a_x, 'b': b_x, 'max_residual': rx}},
        'y': {'label': ay.get('label'), 'unit': ay.get('unit'), 'log': ay.get('log', False),
              'calibration': ay, 'fit': {'a': a_y, 'b': b_y, 'max_residual': ry}},
        'provenance': [h.lstrip('# ') for h in header],
        'points': rows,
        'review': calib.get('review', {'human_review_status': 'PENDING'}),
    }
    if output_json:
        save(output_json, payload)
    print(f"digitized {figure_id}/{trace_id}: {len(rows)} points -> {output_csv}")
    return payload


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('scan')
    s.add_argument('--pdf', required=True); s.add_argument('--output', required=True)
    s.add_argument('--pages'); s.add_argument('--crops', default='work/curve_crops')
    s.add_argument('--max-raster-px', type=int, default=2400)
    s.add_argument('--region', help='normalized page region x0,y0,x1,y1 to restrict scanning (multi-panel figures)')
    s.add_argument('--exclude', action='append', help='normalized crop box x0,y0,x1,y1 to mask out (legend/annotation); repeatable')
    s.set_defaults(func=lambda a: scan(a.pdf, a.output,
                                       {int(x) for x in a.pages.split(',')} if a.pages else None,
                                       a.crops, a.max_raster_px, a.region,
                                       [[float(v) for v in b.split(',')] for b in (a.exclude or [])]))
    d = sub.add_parser('digitize')
    d.add_argument('--scan', required=True); d.add_argument('--figure', required=True)
    d.add_argument('--trace', required=True); d.add_argument('--calibration', required=True)
    d.add_argument('--output-csv'); d.add_argument('--output-json')
    d.set_defaults(func=lambda a: digitize(a.scan, a.figure, a.trace, json.loads(Path(a.calibration).read_text()), a.output_csv, a.output_json))
    args = ap.parse_args(); args.func(args)


if __name__ == '__main__':
    main()
