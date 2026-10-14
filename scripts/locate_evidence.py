#!/usr/bin/env python3
"""P2D PDF evidence locator. It NEVER extracts or invents scientific parameter values.

Input: JSON with independent paper-extracted parameter candidates and exact evidence.quote.
Output: JSON for the HTML review template, with page and normalized bbox only when
        the exact text can be found on the PDF page. All unresolved claims stay unresolved.
"""
import argparse, json, hashlib, re
from pathlib import Path
import fitz


def norm(s):
    return re.sub(r'\s+', ' ', str(s)).strip().casefold()


def locate(doc, quote, page_hint=None):
    """Return a SINGLE unambiguous text location. Never guess locations for numbers.

    Short quotes (>=5 chars) are only accepted when a page hint restricts the
    search to one page — numeric-only strings stay fail-closed via uniqueness.
    """
    quote = (quote or '').strip()
    min_len = 5 if page_hint is not None else 10
    if len(quote) < min_len:
        return {'status':'quote_too_short', 'matches':[]}
    indices = list(range(len(doc)))
    if page_hint is not None and 1 <= int(page_hint) <= len(doc):
        indices = [int(page_hint)-1] + [i for i in indices if i != int(page_hint)-1]
    matches=[]
    for idx in indices:
        page=doc[idx]
        # Exact phrase search via PDF text layer; layout discontinuities may fail safely.
        try:
            found=page.search_for(quote, quads=False)
        except Exception:
            found=[]
        for rect in found:
            rect=fitz.Rect(rect)
            if rect.is_empty: continue
            b=[round(rect.x0/page.rect.width,6),round(rect.y0/page.rect.height,6),
               round(rect.x1/page.rect.width,6),round(rect.y1/page.rect.height,6)]
            if all(0<=x<=1 for x in b):
                matches.append({'page':idx+1,'bbox_norm':b,'bbox_pt':[round(v,2) for v in rect], 'method':'exact_pdf_text_search'})
    # Multiple rects on SAME page can be a phrase broken across lines; do not merge in V1.
    if len(matches)==1:
        return {'status':'located_exact','matches':matches}
    return {'status':'not_found' if not matches else 'ambiguous_multiple_matches','matches':matches}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf',required=True)
    parser.add_argument('--input',required=True,help='JSON containing independently extracted parameters with evidence.quote')
    parser.add_argument('--dictionary',help='45-item DFN JSON dictionary; for metadata and missing placeholders only')
    parser.add_argument('--tables',help='tables.json from table_parser.py — enables parser-provided table-cell bboxes')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    src=json.loads(Path(args.input).read_text(encoding='utf-8'))
    ps=src.get('parameters',src.get('extractions',[]))
    if not isinstance(ps,list): raise SystemExit('input parameters must be an array')
    by_id={}
    if args.dictionary:
        d=json.loads(Path(args.dictionary).read_text(encoding='utf-8'))
        by_id={p['id']:p for p in d['parameters']}
    table_lookup={}
    if args.tables:
        tj=json.loads(Path(args.tables).read_text(encoding='utf-8'))
        for t in tj.get('tables',[]):
            table_lookup[t.get('table_id')]=t
    doc=fitz.open(args.pdf)
    digest=hashlib.sha256(Path(args.pdf).read_bytes()).hexdigest()
    out=[]
    for i,p in enumerate(ps):
        p=dict(p)
        key=p.get('id',p.get('parameter_id',f'param_{i}'))
        reference=by_id.get(key,{})
        ev=p.get('evidence') or p.get('paper_evidence') or {}
        if not isinstance(ev,dict): ev={}
        quote=ev.get('quote') or ev.get('text') or ''
        hint=ev.get('page')
        result=locate(doc,quote,hint)
        matches=result['matches']
        evidence={**ev,'quote':quote,'location_status':result['status'],
                  'location_candidates':matches}
        if result['status']=='located_exact':
            evidence['page']=matches[0]['page']
            evidence['bbox_norm']=matches[0]['bbox_norm']
            evidence['bbox_pt']=matches[0]['bbox_pt']
            evidence['bbox_provenance']='exact_quote_match'
        else:
            # Never promote provided unverified coordinates to a confirmed location.
            # Parser-provided TABLE-CELL coordinates are a different, labeled source:
            # they highlight the parsed cell (human still confirms in review HTML).
            evidence['bbox_norm']=None
            tc = ev.get('table_cell') or p.get('table_cell')
            if tc and tc.get('table_id') in table_lookup:
                t = table_lookup[tc['table_id']]
                cell_bbox=None
                for c in t.get('cells',[]):
                    if c.get('cell_id')==tc.get('cell_id'):
                        cell_bbox=c.get('bbox_norm'); break
                if cell_bbox is None:
                    cell_bbox = t.get('bbox_norm')  # fall back to whole-table highlight
                if cell_bbox:
                    evidence['location_status']='table_cell_parser'
                    evidence['bbox_norm']=cell_bbox
                    evidence['bbox_provenance']='table_parser_cell (not quote-verified; human confirms)'
                    evidence['table_ref']={'table_id':tc['table_id'],'cell_id':tc.get('cell_id')}
        out.append({
            'id':key,
            'name_zh':p.get('name_zh',reference.get('name_zh',key)),
            'name_en':p.get('name_en',reference.get('name_en','')),
            'category':p.get('category',reference.get('category','未分类')),
            'pybamm_name':p.get('pybamm_name',reference.get('pybamm_name')),
            'value':p.get('value',p.get('paper_value')),
            'unit':p.get('unit',reference.get('unit','')),
            'value_type':p.get('value_type',reference.get('value_type','scalar')),
            'source_type':p.get('source_type','PAPER'),
            'review_status':p.get('review_status','PENDING' if p.get('value',p.get('paper_value')) is not None else 'MISSING'),
            'evidence':evidence,
            'original_claim':p
        })
    output={
        'schema_version':'p2d-review-v1',
        'document':{'id':src.get('document',{}).get('id',Path(args.pdf).stem),
                    'title':src.get('document',{}).get('title',Path(args.pdf).name),
                    'pdf_filename':Path(args.pdf).name,'pdf_sha256':digest,
                    'page_count':len(doc)},
        'methodology':{'no_value_extraction':'This pipeline NEVER extracts scientific values',
                       'location':'Only unambiguous exact text match receives bbox_norm',
                       'bbox_format':'[x0,y0,x1,y1] normalized to top-left visible PyMuPDF page'},
        'parameters':out
    }
    Path(args.output).write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    statuses={}
    for p in out:
        s=p['evidence']['location_status'];statuses[s]=statuses.get(s,0)+1
    print(f'PDF pages: {len(doc)} | Parameters: {len(out)} | Evidence: {statuses}')
    print('Saved:',args.output)

if __name__=='__main__':main()
