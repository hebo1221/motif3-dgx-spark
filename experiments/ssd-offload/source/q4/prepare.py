import pathlib,json,hashlib,subprocess,os
p=pathlib.Path(__file__).resolve().parent
root=p.parent
archive='/opt/motif-work/motif3-storage/original-bf16-lossless-v1'
layout=root/'bf16-lossless-archive-20260910-v1/gguf-layout.json'
expected={2:('q4-full-layer-20260910-v1/layer2.q4k','f1f4309a7cdaf4d60ef767d39ceb40b9545076f1283c7fab60a7cf37f74348a5'),3:('q4-two-layer-20260910-v1/layer3.q4k','6e5050f230a985721c261e38b5ed1b7b628b782b1970dd5577b3db13a64de90d'),27:('q4-four-layer-20260910-v1/prepare-27/layer27.q4k','bea9e1e3875f3fb25fd7eb54ec0d559318e791c64846350716d1f51adaa8ca01'),52:('q4-four-layer-20260910-v1/prepare-52/layer52.q4k','0a9ce2c538fd12a06ff6edfb71555e608a790657d32ada0f12ffc0b0e5b77280')}
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
packs=p/'packs';packs.mkdir(exist_ok=False)
v=p/'validation-layer2/layer2.q4k';assert sha(v)==expected[2][1]
for layer,(name,digest) in expected.items():
 src=root/name;assert src.stat().st_size==3397386240 and sha(src)==digest
 (packs/f'layer{layer}.q4k').symlink_to(src)
 (packs/f'layer{layer}.q4k.json').write_text(json.dumps({'layer':layer,'bytes':3397386240,'sha256':digest,'source_sha256':'c921b7afb7fb8b5b5d90ff719e945a16988f696b8353e22bebcad2b6254362aa','type':'Q4_K','reused':True}))
(p/'archive-conversion-parity.json').write_text(json.dumps({'full_layer_byte_hash_exact':True,'layer':2,'sha256':expected[2][1],'bytes':v.stat().st_size,'reused_layers_verified':list(expected)}))
v.unlink() # Only the newly created duplicate; original pack remains verified.
free=os.statvfs(p);assert free.f_bavail*free.f_frsize>47*3397386240+13630106240+(8<<30)
env=os.environ.copy();env['LD_LIBRARY_PATH']='/opt/motif-work/motif3-tokenizer-runtime-baseline-v1/build/bin'
with (p/'conversion.jsonl').open('x') as out,(p/'conversion.stderr').open('x') as err:
 subprocess.run([str(p/'convert'),archive,str(layout),str(packs),','.join(str(l) for l in range(2,53) if l not in expected),'12'],env=env,stdout=out,stderr=err,check=True)
with (p/'shell.jsonl').open('x') as out,(p/'shell.stderr').open('x') as err:
 subprocess.run([str(p/'make-shell'),archive,str(layout),str(p/'ordinary.sparse-shell.gguf')],env=env,stdout=out,stderr=err,check=True)
(p/'PREPARED.json').write_text(json.dumps({'all_q4_layers':51,'sparse_shell':True,'standalone_gguf':False,'quality_qualified':False}))
print('PREPARED',flush=True)
