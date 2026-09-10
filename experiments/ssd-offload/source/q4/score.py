"""Score externally collected final answers. Never executes model output."""
import json,pathlib,sys
p=pathlib.Path(__file__).resolve().parent
cases={r['id']:r for r in map(json.loads,(p/'quality-cases.jsonl').read_text().splitlines())}
answers={}
for line in pathlib.Path(sys.argv[1]).read_text().splitlines():
 r=json.loads(line)
 if r['id'] in answers:raise ValueError('duplicate id')
 if r['id'] not in cases:raise ValueError('unknown id')
 answers[r['id']]=r['text']
rows=[]
for i,c in cases.items():
 try:obj=json.loads(answers[i]);ok=isinstance(obj,dict) and json.dumps(obj,sort_keys=True)==json.dumps(c['expected'],sort_keys=True);reason='match' if ok else 'wrong_answer'
 except KeyError:ok=False;reason='missing'
 except (ValueError,TypeError):ok=False;reason='invalid_json'
 rows.append({'id':i,'category':c['category'],'passed':ok,'reason':reason})
print(json.dumps({'passed':sum(r['passed'] for r in rows),'total':len(rows),'scope':'small synthetic canary; not general agent quality','results':rows},ensure_ascii=False,indent=2))
