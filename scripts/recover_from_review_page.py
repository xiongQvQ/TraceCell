#!/usr/bin/env python3
"""从自包含审核页里把内联的数据还原回 work/<doc-id>/ 的运行目录。

背景:build_review_page.py 把 review_ready / tables / formulas / curves 原样内联进
单个 HTML(裁片转 data URI)。因此只要还有一份审核页,这些产物就能反解出来。
裁片的原始文件名在 data URI 里已丢失,按 <table_id>.png / <fig>_page.png 重新命名
并同步改写 JSON 里的相对路径 —— 只要两侧一致,链接即成立。

用法:
  python3 scripts/recover_from_review_page.py --page review_page.html \
      --out work/<doc-id> [--pdf paper.pdf] [--apply]
"""
import argparse, base64, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_payload(page_html):
    s = Path(page_html).read_text(encoding='utf-8')
    key = 'window.__REVIEW_DATA__ = '
    i = s.find(key)
    if i < 0:
        sys.exit('未找到 window.__REVIEW_DATA__ —— 这不是 build_review_page.py 生成的审核页')
    dec = json.JSONDecoder()
    obj, _ = dec.raw_decode(s[i + len(key):].replace('<\\/script>', '</script>'))
    return obj


def decode_uri(uri):
    m = re.match(r'data:image/(png|jpeg|jpg);base64,(.*)$', uri or '', re.S)
    if not m:
        return None, None
    return m.group(1), base64.b64decode(m.group(2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--page', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--pdf', help='校验用:比对页内 base64 与磁盘 PDF 的 sha256')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    out = Path(a.out)
    d = load_payload(a.page)
    doc = d.get('document', {})
    print(f"审核页 document.id = {doc.get('id')} · {str(doc.get('title'))[:50]}")
    print(f"参数 {len(d.get('parameters',[]))} · 表格 {len(d.get('tables',[]))} · "
          f"公式 {len(d.get('formulas',[]))} · 曲线图 {len(d.get('curves',{}).get('figures',[]))}")

    files = {}     # 相对路径 -> bytes
    restored = []

    # 1) review_ready.json —— 只保留它自己的四个顶层键
    rr = {k: d[k] for k in ('schema_version', 'document', 'methodology', 'parameters') if k in d}
    files['review_ready.json'] = json.dumps(rr, ensure_ascii=False, indent=1).encode()
    restored.append(f"review_ready.json ({len(rr.get('parameters',[]))} 参数)")

    # 2) tables.json + table_crops/<table_id>.png
    if d.get('tables'):
        tabs = json.loads(json.dumps(d['tables']))   # 深拷贝,避免改到原 payload
        for t in tabs:
            uri = t.get('crop_png')
            if isinstance(uri, str) and uri.startswith('data:'):
                ext, blob = decode_uri(uri)
                name = f"table_crops/{t['table_id']}.{'jpg' if ext in ('jpeg','jpg') else 'png'}"
                files[name] = blob
                t['crop_png'] = name
            for key in ('analysis_png',):
                if isinstance(t.get(key), str) and t[key].startswith('data:'):
                    ext, blob = decode_uri(t[key])
                    name = f"table_crops/{t['table_id']}_analysis.png"
                    files[name] = blob; t[key] = name
        files['tables.json'] = json.dumps({'tables': tabs}, ensure_ascii=False, indent=1).encode()
        restored.append(f"tables.json ({len(tabs)} 表格 + 裁片)")

    # 3) curves_scan_all.json + curve_crops/<fig>_*.png
    figs = (d.get('curves') or {}).get('figures') or []
    if figs:
        cur = json.loads(json.dumps(figs))
        for f in cur:
            for key, suffix in (('crop_png', '_page'), ('analysis_png', '_analysis')):
                uri = f.get(key)
                if isinstance(uri, str) and uri.startswith('data:'):
                    ext, blob = decode_uri(uri)
                    name = f"curve_crops/{f['figure_id']}{suffix}.{'jpg' if ext in ('jpeg','jpg') else 'png'}"
                    files[name] = blob; f[key] = name
        files['curves_scan_all.json'] = json.dumps({'figures': cur}, ensure_ascii=False, indent=1).encode()
        restored.append(f"curves_scan_all.json ({len(cur)} 图)")

    # 4) formulas_validated.json
    if d.get('formulas'):
        fs = json.loads(json.dumps(d['formulas']))
        for f in fs:
            uri = f.get('crop_png')
            if isinstance(uri, str) and uri.startswith('data:'):
                ext, blob = decode_uri(uri)
                name = f"formula_crops/{f['id']}.png"
                files[name] = blob; f['crop_png'] = name
        files['formulas_validated.json'] = json.dumps(
            {'schema_version': 'p2d-formulas-v1', 'document': doc, 'formulas': fs},
            ensure_ascii=False, indent=1).encode()
        restored.append(f"formulas_validated.json ({len(fs)} 条)")

    # 5) 内联 PDF 与磁盘 PDF 校验
    b64 = d.get('pdf_base64')
    if b64:
        import hashlib
        got = hashlib.sha256(base64.b64decode(b64)).hexdigest()
        print(f"页内 PDF sha256 = {got[:16]}…")
        if a.pdf and Path(a.pdf).exists():
            want = hashlib.sha256(Path(a.pdf).read_bytes()).hexdigest()
            print(f"磁盘 PDF sha256 = {want[:16]}…  {'✓ 一致' if want == got else '✗ 不一致'}")
        files['_recovered/pdf_base64.bin'] = base64.b64decode(b64)
        restored.append('_recovered/pdf_base64.bin (页内 PDF 副本)')

    print('\n可还原:')
    for r in restored:
        print('  •', r)
    crops = sum(1 for k in files if k.endswith(('.png', '.jpg')))
    print(f'  裁片图片共 {crops} 张')

    print('\n无法从审核页还原(需重新生成或已永久丢失):')
    print('  • pages.json / formulas_scan.json / curves_scan.json / docling_out.json —— 由确定性阶段从 PDF 重跑')
    print('  • reviewed.json / reviewed_frozen.json —— 人工审核决定,页内未保存')
    print('  • sim/ 仿真与对比产物 —— 依赖 reviewed_frozen.json 重跑 pybamm_adapter')

    if not a.apply:
        print('\n(dry-run — 加 --apply 写入)')
        return
    for rel, blob in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(blob)
    print(f'\n已写入 {len(files)} 个文件 -> {out}/')


if __name__ == '__main__':
    main()
