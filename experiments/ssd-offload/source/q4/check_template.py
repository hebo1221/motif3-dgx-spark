import struct,pathlib,json,hashlib,sys
p=pathlib.Path(__file__).resolve().parent
f=(p.parent/'bf16-lossless-archive-20260910-v1/gguf-header.bin').open('rb');assert f.read(4)==b'GGUF'
def u(fmt):return struct.unpack('<'+fmt,f.read(struct.calcsize('<'+fmt)))[0]
def s(keep=True):
 n=u('Q')
 if keep:return f.read(n).decode()
 f.seek(n,1)
def v(t,keep):
 fm={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
 if t==8:return s(keep)
 if t==9:
  st=u('I');n=u('Q')
  if st in fm and not keep:f.seek(n*struct.calcsize('<'+fm[st]),1);return
  a=[v(st,keep) for _ in range(n)];return a if keep else None
 return u(fm[t])
version=u('I');nt=u('Q');nk=u('Q');meta={}
for _ in range(nk):
 key=s();typ=u('I');keep='chat_template' in key;val=v(typ,keep)
 if keep:meta[key]=val
sys.path.insert(0,'/opt/motif-work/vllm/.venv/lib/python3.12/site-packages')
from jinja2 import Environment
original=(p/'upstream-template.jinja').read_text()
env=Environment(extensions=['jinja2.ext.loopcontrols']);env.globals['raise_exception']=lambda x:(_ for _ in ()).throw(ValueError(x))
t=env.from_string(original)
rows=[]
for filename in ['quality-cap8192/requests.jsonl','long-cap2048/requests.jsonl']:
 for r in map(json.loads,(p/filename).read_text().splitlines()):
  # Recover the user content from the existing single-user project rendering.
  prompt=r['prompt'];begin='<|startofturn|><|user|>';end='<|endofturn|>';question=prompt.split(begin,1)[1].split(end,1)[0]
  rendered=t.render(messages=[{'role':'user','content':question}],tools=[],bos_token='<|beginoftext|>',eos_token='<|endoftext|>',add_generation_prompt=True,enable_thinking=False)
  rows.append({'file':filename,'id':r['id'],'byte_exact':rendered==prompt,'original_suffix':rendered[-100:] if rendered!=prompt else None})
result={'gguf_embedded_chat_template_found':bool(meta),'upstream_source':json.loads((p/'upstream-template-source.json').read_text()),'original_template_sha256':hashlib.sha256(original.encode()).hexdigest(),'all_renderings_byte_exact':all(r['byte_exact'] for r in rows),'rows':rows}
(p/'template-parity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
