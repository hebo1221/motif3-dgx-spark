import pathlib,json,os,fcntl,subprocess,time,sys,hashlib
p=pathlib.Path(__file__).resolve().parent
lock=open(p.parent/'bf16-overnight-20260909-v1/worker.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
verified=json.loads((p/'preflight.json').read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(p/'loader.so')==verified['loader_sha256'] and sha(p/'probe')==verified['probe_sha256']
for name,identity in verified['identities'].items():
 s=pathlib.Path(name).stat();assert [s.st_ino,s.st_size,s.st_mtime_ns]==identity
sys.path.insert(0,'/opt/motif-work/vllm/.venv/lib/python3.12/site-packages')
from jinja2 import Environment
t=Environment().from_string((p/'prompt-template.jinja').read_text())
question='혼자 사는 사람을 돕는 야간 AI 비서의 하루 작업을 20단계로 자세히 설명해줘. 각 단계는 두 문장으로 쓰고, 외부 메시지 발송이나 결제는 사용자 승인 후 실행한다고 명시해줘.'
prompt=t.render(messages=[{'role':'user','content':question}],tools=[],bos_token='<|beginoftext|>',eos_token='<|endoftext|>',add_generation_prompt=True,enable_thinking=False)
requests=[{'id':f'long-{i}','prompt':prompt,'max_tokens':128,'add_bos':False} for i in range(2)]
b='/opt/motif-work/motif3-tokenizer-runtime-baseline-v1/build/bin';src=p/'ordinary.sparse-shell.gguf';results=[]
for cap in [2048,8192]:
 d=p/f'long-cap{cap}';d.mkdir()
 for layer in range(2,53):(d/f'layer{layer}.q4k').symlink_to(p/f'packs/layer{layer}.q4k')
 (d/'tensors.txt').symlink_to(p.parent/'bf16-overnight-20260909-v1/tensors.txt')
 text=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in requests);(d/'requests.jsonl').write_text(text)
 env=os.environ.copy()
 for key in list(env):
  if key.startswith('MOTIF_') or key.startswith('Q4_'):del env[key]
 env.update(LD_LIBRARY_PATH=b,LD_PRELOAD=str(p/'loader.so'),MOTIF_SOURCE=str(src),MOTIF_LOAD_STAGING='1',GGML_OP_OFFLOAD_MIN_BATCH='1',GGML_CUDA_DISABLE_GRAPHS='1',MOTIF_DIRECT_LAYER='q4',Q4_CACHE_EXPERTS=str(cap))
 before=pathlib.Path('/proc/vmstat').read_text();started=time.monotonic()
 with (d/'events.jsonl').open('x') as out,(d/'stderr.log').open('x') as err:r=subprocess.run([str(p/'probe'),str(src),b],env=env,cwd=d,input=text,text=True,stdout=out,stderr=err)
 (d/'process.json').write_text(json.dumps({'returncode':r.returncode,'seconds':time.monotonic()-started,'vmstat_before':before,'vmstat_after':pathlib.Path('/proc/vmstat').read_text()}));assert r.returncode==0
 events=[json.loads(line) for line in (d/'events.jsonl').read_text().splitlines()];done=[r for r in events if r['event']=='request_complete'];assert len(done)==2 and all(r['source_read_bytes']==0 for r in done)
 for row in done:
  tokens=[r for r in events if r['event']=='token' and r['id']==row['id'] and 'elapsed_seconds' in r]
  tail=tokens[-33:];last32_tps=(len(tail)-1)/(tail[-1]['elapsed_seconds']-tail[0]['elapsed_seconds']) if len(tail)==33 else None
  result={'cap':cap,'id':row['id'],'generated_tokens':row['generated_tokens'],'decode_tps':(row['generated_tokens']-1)/row['decode_seconds'],'last32_wall_tps':last32_tps,'request_seconds':row['request_seconds'],'prefill_seconds':row['prefill_seconds'],'text':row['text']};results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
 if cap==8192:
  ref=p/'long-cap2048';names=sorted(f.name for f in d.glob('logits-*.bin'));assert names and names==sorted(f.name for f in ref.glob('logits-*.bin'))
  for name in names:assert sha(d/name)==sha(ref/name),'long cache logits mismatch'
  (d/'parity.json').write_text(json.dumps({'byte_exact':True,'files':len(names)}))
(p/'long-summary.json').write_text(json.dumps({'results':results,'cache_logits_parity':True,'scope':'one 128-token chat prompt repeated twice in each fresh process; 2048 then 8192; no cold-cache reset'},ensure_ascii=False,indent=2)+'\n')
