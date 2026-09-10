import pathlib,json,hashlib,subprocess,os,fcntl,sys,time
p=pathlib.Path(__file__).resolve().parent
lock=open(p.parent/'bf16-overnight-20260909-v1/worker.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert json.loads((p/'PREPARED.json').read_text())['all_q4_layers']==51
src=p/'ordinary.sparse-shell.gguf';receipt=json.loads(pathlib.Path(str(src)+'.json').read_text());assert receipt['format']=='SPARSE_Q4_SHELL_NOT_STANDALONE' and receipt['ordinary_readback_byte_exact']
assert src.stat().st_size==receipt['logical_bytes'] and src.stat().st_blocks*512<20<<30
assert not src.stat().st_mode & 0o222

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()

def state(path):
 s=path.stat();return [s.st_ino,s.st_size,s.st_mtime_ns]
identities={};digests={}
for layer in range(2,53):
 f=p/f'packs/layer{layer}.q4k';r=json.loads(pathlib.Path(str(f)+'.json').read_text());assert r['layer']==layer and r['bytes']==f.stat().st_size==3397386240 and r['type']=='Q4_K'
 assert r['source_sha256']==receipt['source_sha256']
 assert sha(f)==r['sha256'];digests[str(layer)]=r['sha256'];identities[str(f)]=state(f)
with src.open('rb') as f:
 for r in receipt['ranges']:
  f.seek(r['start']);n=r['length'];h=hashlib.sha256()
  while n:
   b=f.read(min(n,8<<20));assert b;h.update(b);n-=len(b)
  assert h.hexdigest()==r['sha256'],r['name']
identities[str(src)]=state(src)
(p/'preflight.json').write_text(json.dumps({'all_pack_sha256_verified':True,'ordinary_ranges_sha256_verified':True,'identities':identities,'pack_sha256':digests,'loader_sha256':sha(p/'loader.so'),'probe_sha256':sha(p/'probe')},indent=2))
print('PREFLIGHT_PASS',flush=True)
requests=[{'id':'code','prompt':'Write a Python function to reverse a list.','max_tokens':16},{'id':'korean','prompt':'하루 동안 처리할 할 일을 중요도순으로 정리하는 방법을 세 단계로 설명해줘.','max_tokens':16}]
b='/opt/motif-work/motif3-tokenizer-runtime-baseline-v1/build/bin'
def run(name,cap,requests):
 d=p/name;d.mkdir()
 for layer in range(2,53):(d/f'layer{layer}.q4k').symlink_to(p/f'packs/layer{layer}.q4k')
 (d/'tensors.txt').symlink_to(p.parent/'bf16-overnight-20260909-v1/tensors.txt')
 for f,s in identities.items():assert state(pathlib.Path(f))==s
 env=os.environ.copy()
 for k in list(env):
  if k.startswith('MOTIF_') or k.startswith('Q4_'):del env[k]
 env.update(LD_LIBRARY_PATH=b,LD_PRELOAD=str(p/'loader.so'),MOTIF_SOURCE=str(src),MOTIF_LOAD_STAGING='1',GGML_OP_OFFLOAD_MIN_BATCH='1',GGML_CUDA_DISABLE_GRAPHS='1',MOTIF_DIRECT_LAYER='q4',Q4_CACHE_EXPERTS=str(cap))
 text=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in requests);(d/'requests.jsonl').write_text(text)
 before=pathlib.Path('/proc/vmstat').read_text();started=time.monotonic()
 with (d/'events.jsonl').open('x') as out,(d/'stderr.log').open('x') as err:
  proc=subprocess.run([str(p/'probe'),str(src),b],cwd=d,env=env,input=text,text=True,stdout=out,stderr=err)
 (d/'process.json').write_text(json.dumps({'returncode':proc.returncode,'seconds':time.monotonic()-started,'vmstat_before':before,'vmstat_after':pathlib.Path('/proc/vmstat').read_text()}))
 assert proc.returncode==0,name
 events=[json.loads(s) for s in (d/'events.jsonl').read_text().splitlines()];done=[r for r in events if r['event']=='request_complete']
 assert len(done)==len(requests) and all(r['source_read_bytes']==0 for r in done)
 assert events[-1]['event']=='worker_complete'
 for f,s in identities.items():assert state(pathlib.Path(f))==s
 print(json.dumps({'run':name,'completed':len(done),'results':[{'id':r['id'],'decode_tps':(r['generated_tokens']-1)/r['decode_seconds'] if r['decode_seconds'] else None,'request_seconds':r['request_seconds']} for r in done]}),flush=True)
 return d,done
for i,cap in enumerate([2048,8192,8192,2048]):
 d,done=run(f'bench-{i}-cap{cap}',cap,requests)
 if i:
  ref=p/'bench-0-cap2048';names=sorted(f.name for f in d.glob('logits-*.bin'));assert names==sorted(f.name for f in ref.glob('logits-*.bin')) and names
  for name in names:assert sha(d/name)==sha(ref/name),'cache logits mismatch'
  (d/'parity.json').write_text(json.dumps({'byte_exact':True,'files':len(names)}))
# The small heldout suite is a functional canary, not a BF16 quality-preservation claim.
sys.path.insert(0,'/opt/motif-work/vllm/.venv/lib/python3.12/site-packages')
from jinja2 import Environment
template=pathlib.Path('/opt/motif-work/motif3-quant/templates/motif3-llama.cpp.jinja');t=Environment().from_string(template.read_text());(p/'prompt-template.jinja').write_text(template.read_text())
cases=[json.loads(s) for s in (p/'quality-cases.jsonl').read_text().splitlines()]
quality=[]
for c in cases:
 prompt=t.render(messages=[{'role':'user','content':c['question']}],tools=[],bos_token='<|beginoftext|>',eos_token='<|endoftext|>',add_generation_prompt=True,enable_thinking=False)
 quality.append({'id':c['id'],'prompt':prompt,'max_tokens':64,'add_bos':False})
d,done=run('quality-cap8192',8192,quality)
(d/'answers.jsonl').write_text(''.join(json.dumps({'id':r['id'],'text':r['text']},ensure_ascii=False)+'\n' for r in done))
with (d/'score.json').open('x') as out:subprocess.run([sys.executable,str(p/'score.py'),str(d/'answers.jsonl')],stdout=out,check=True)
(p/'FINISHED.json').write_text(json.dumps({'benchmark_completed':True,'cache_logits_parity':True,'canary_completed':True,'bf16_quality_parity_tested':False}))
