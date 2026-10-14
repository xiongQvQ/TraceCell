#!/usr/bin/env python3
"""P2D research skill: deterministic PDF inspection, parameter candidate generation, validation and comparison.
No LLM/API dependency. The Agent must independently read and extract scientific values.
"""
import argparse, csv, hashlib, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DICT = ROOT/'assets'/'parameter_dictionary.json'

def load(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')

def template(args):
    d=load(args.dictionary or DICT)
    doc_id = getattr(args, 'doc_id', None) or (Path(args.pdf).stem if args.pdf else 'PAPER_ID')
    out={'schema_version':'p2d-extraction-v1', 'document':{'id':doc_id,'title':'','doi':'','pdf_sha256':hashlib.sha256(Path(args.pdf).read_bytes()).hexdigest() if args.pdf else None},'provenance_policy':'PAPER_FIRST_NO_CODE_VALUES','parameters':[]}
    for p in d['parameters']:
        out['parameters'].append({'id':p['id'],'name_en':p['name_en'],'category':p['category'],'pybamm_name':p['pybamm_name'],'value':None,'unit':p['unit'],'value_type':p['value_type'],'source_type':'UNKNOWN','value_role':'unspecified','review_status':'MISSING','evidence':{'quote':'','page':None,'document_id':out['document']['id'],'section':None,'table':None,'bbox_norm':None},'notes':''})
    save(args.output,out)
    print('Prepared',len(out['parameters']),'empty parameters:',args.output)

def inventory(args):
    import fitz
    p=Path(args.pdf); doc=fitz.open(p)
    out={'document':{'title':p.name,'pdf_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'pages':len(doc)},'pages':[]}
    for i,page in enumerate(doc):
        text=page.get_text('text') or ''
        out['pages'].append({'page':i+1,'characters':len(text),'text':text[:args.max_chars_per_page], 'is_image_or_low_text':len(text.strip())<60})
    save(args.output,out)
    print('Wrote',len(doc),'page inventory:',args.output)

def validate(args):
    d=load(args.dictionary or DICT)
    indexed={p['id']:p for p in d['parameters']}
    src=load(args.input)
    problems=[]; counts={}; seen=set()
    for i,p in enumerate(src.get('parameters',[])):
        pid=p.get('id',p.get('parameter_id'))
        if pid not in indexed: problems.append(f'{i}: unknown parameter id {pid}')
        if pid in seen: problems.append(f'{i}: repeated id {pid}; multiple candidates require candidates[]')
        seen.add(pid)
        status=p.get('review_status','MISSING'); counts[status]=counts.get(status,0)+1
        value=p.get('value',p.get('paper_value'))
        evidence=p.get('evidence') or p.get('paper_evidence') or {}
        if value is not None and p.get('source_type') in (None,'UNKNOWN'):
            problems.append(f'{pid}: non-null value without source_type')
        if value is not None and p.get('source_type') in ('PAPER','CITED'):
            if not evidence.get('quote'): problems.append(f'{pid}: paper value missing evidence.quote')
            if not evidence.get('page') and not evidence.get('document_id'): problems.append(f'{pid}: paper value missing page/document locator')
        if status=='VERIFIED' and (value is None or not evidence.get('quote')):
            problems.append(f'{pid}: VERIFIED without value and quote')
        if p.get('source_type')=='EXTERNAL' and status=='VERIFIED':
            problems.append(f'{pid}: external source cannot count as verified paper extraction')
        if value is not None and not p.get('unit') and indexed.get(pid,{}).get('unit') not in ('dimensionless','1',''):
            problems.append(f'{pid}: missing unit')
    output={'ok':not problems,'dictionary_items':len(indexed),'provided_items':len(src.get('parameters',[])),'statuses':counts,'problems':problems}
    if args.output:save(args.output,output)
    print(json.dumps(output,ensure_ascii=False,indent=2));sys.exit(0 if not problems else 2)

def compare(args):
    """Only after extraction is frozen! Compare separately-supplied code-derived CSV/JSON."""
    paper=load(args.paper);code=load(args.code)
    pp={p['id']:p for p in paper['parameters']}
    cp={p['id']:p for p in code['parameters']}
    rows=[]
    for id in sorted(set(pp)|set(cp)):
        p=pp.get(id,{});c=cp.get(id,{})
        a=p.get('value');b=c.get('value')
        if a is None: verdict='NOT_EXTRACTED_FROM_PAPER'
        elif b is None: verdict='CODE_NOT_MAPPED'
        elif p.get('value_type') not in ('scalar',None) or isinstance(a,(dict,list)) or isinstance(b,(dict,list)): verdict='FUNCTION_REQUIRES_REVIEW'
        else:
            try:
                same=(p.get('unit')==c.get('unit') and abs(float(a)-float(b)) <= args.atol + args.rtol*max(abs(float(a)),abs(float(b))))
                verdict='MATCH' if same else ('UNIT_DIFFERS' if p.get('unit')!=c.get('unit') else 'VALUE_DIFFERS')
            except (TypeError,ValueError): verdict='NONNUMERIC_REQUIRES_REVIEW'
        rows.append({'id':id,'paper_value':a,'paper_unit':p.get('unit'),'paper_evidence':p.get('evidence'),'code_value':b,'code_unit':c.get('unit'),'code_ref':c.get('code_ref'),'result':verdict})
    summary={}
    for row in rows:summary[row['result']]=summary.get(row['result'],0)+1
    save(args.output,{'method':'paper_first_comparison','note':'Only independent, reviewed paper extraction can support empirical accuracy','summary':summary,'comparisons':rows})
    print('Comparison summary:',summary)

def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('template');p.add_argument('--pdf');p.add_argument('--dictionary');p.add_argument('--doc-id',dest='doc_id');p.add_argument('--output',required=True);p.set_defaults(func=template)
    p=sub.add_parser('inventory');p.add_argument('--pdf',required=True);p.add_argument('--output',required=True);p.add_argument('--max-chars-per-page',type=int,default=15000);p.set_defaults(func=inventory)
    p=sub.add_parser('validate');p.add_argument('--input',required=True);p.add_argument('--dictionary');p.add_argument('--output');p.set_defaults(func=validate)
    p=sub.add_parser('compare');p.add_argument('--paper',required=True);p.add_argument('--code',required=True);p.add_argument('--output',required=True);p.add_argument('--atol',type=float,default=0);p.add_argument('--rtol',type=float,default=1e-6);p.set_defaults(func=compare)
    args=ap.parse_args();args.func(args)
if __name__=='__main__':main()
