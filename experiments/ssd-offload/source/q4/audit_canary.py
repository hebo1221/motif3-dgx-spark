import pathlib,json
p=pathlib.Path(__file__).resolve().parent
cases={r['id']:r for r in map(json.loads,(p/'quality-cases.jsonl').read_text().splitlines())}
answers={r['id']:r['text'] for r in map(json.loads,(p/'quality-cap8192/answers.jsonl').read_text().splitlines())}
score=json.loads((p/'quality-cap8192/score.json').read_text());details=[]
for r in score['results']:
 if r['passed']:continue
 expected=cases[r['id']]['expected'];text=answers.get(r['id'],'')
 try:
  actual=json.loads(text)
  same_required=isinstance(actual,dict) and all(k in actual and json.dumps(actual[k],sort_keys=True)==json.dumps(v,sort_keys=True) for k,v in expected.items())
  kind='extra_fields_only' if same_required else 'wrong_value_or_missing_key'
 except ValueError:kind='invalid_json'
 details.append({'id':r['id'],'strict_failure_detail':kind,'question':cases[r['id']]['question'],'expected':expected,'text':text})
result={'strict_score_unchanged':{'passed':score['passed'],'total':score['total']},'posthoc_failure_description_only':True,'failures':details,'not_a_new_pass_rate':True}
(p/'quality-cap8192/failure-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
