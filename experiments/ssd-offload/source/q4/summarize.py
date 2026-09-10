import pathlib,json,statistics
p=pathlib.Path(__file__).resolve().parent
rows=[]
for d in sorted(p.glob('bench-*-cap*')):
 events=[json.loads(s) for s in (d/'events.jsonl').read_text().splitlines()]
 cache=[json.loads(s[len('Q4_CACHE '):]) for s in (d/'stderr.log').read_text().splitlines() if s.startswith('Q4_CACHE ')]
 done=[r for r in events if r['event']=='request_complete']
 proc=json.loads((d/'process.json').read_text())
 def swap(text):
  v=dict(line.split() for line in text.splitlines());return {k:int(v[k]) for k in ['pswpin','pswpout']}
 before=swap(proc['vmstat_before']);after=swap(proc['vmstat_after'])
 row={'run':d.name,'cap':int(d.name.split('cap')[1]),'returncode':proc['returncode'],'requests':[],
 'logical_q4_read_bytes':sum(c['logical_bytes'] for c in cache),'q4_fetch_seconds':sum(c['fetch_ms'] for c in cache)/1000,
 'physical_nvme_during_fetch_bytes':sum(c['physical_nvme_bytes'] for c in cache),
 'external_read_during_fetch_bytes':sum(c['external_read_bytes'] for c in cache),
 'hit_rate':1-sum(c['misses'] for c in cache)/sum(c['selected'] for c in cache) if cache else None,
 'swap_pages_delta':{k:after[k]-before[k] for k in before}}
 for r in done:row['requests'].append({'id':r['id'],'generated_tokens':r['generated_tokens'],'decode_steps':r['generated_tokens']-1,'decode_tps':(r['generated_tokens']-1)/r['decode_seconds'] if r['decode_seconds'] else None,'prefill_seconds':r['prefill_seconds'],'request_seconds':r['request_seconds'],'routed_bf16_read_bytes':r['source_read_bytes'],'text':r['text']})
 rows.append(row)
summary={'runs':rows,'scope':'51 routed-expert layers Q4_K; ordinary tensors unchanged; warm process cache comparison','target_decode_tps':{'minimum':3,'desired':5},'bf16_quality_preservation_established':False}
if len(rows)==4 and all(r['returncode']==0 and len(r['requests'])==2 for r in rows):
 summary['medians']={str(cap):statistics.median(r['decode_tps'] for row in rows if row['cap']==cap for r in row['requests']) for cap in [2048,8192]}
 summary['cache_logits_parity']=all(json.loads((p/f'bench-{i}-cap{cap}/parity.json').read_text())['byte_exact'] for i,cap in [(1,8192),(2,8192),(3,2048)])
 summary['minimum_speed_met_in_this_comparison']=summary['medians']['8192']>=3
q=p/'quality-cap8192/score.json'
if q.exists():summary['synthetic_canary']=json.loads(q.read_text())
(p/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
