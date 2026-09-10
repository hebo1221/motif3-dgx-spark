"""Reconstruct complete or partially migrated source into a NEW output file."""
import argparse,hashlib,json,pathlib,subprocess,os,fcntl
ap=argparse.ArgumentParser();ap.add_argument('archive');ap.add_argument('output');ap.add_argument('--codec',required=True);a=ap.parse_args()
root=pathlib.Path(a.archive);lock=open(root/'writer.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);s=json.loads((root/'state.json').read_text());h=hashlib.sha256();written=0
with open(a.output,'xb') as out:
 def copy(stream,limit=None):
  global written
  while limit is None or limit:
   b=stream.read(8<<20 if limit is None else min(8<<20,limit))
   if not b:
    if limit:raise RuntimeError('short migration prefix')
    break
   out.write(b);h.update(b);written+=len(b)
   if limit is not None:limit-=len(b)
 if s['remaining']:
  source=pathlib.Path(s['source']);prefix=source.with_name(source.name+'.lossless-migrating')
  with prefix.open('rb') as f:copy(f,s['remaining'])
 for entry in reversed(s['entries']):
  proc=subprocess.Popen([a.codec,'decode',str(root/entry['file']),'-'],stdout=subprocess.PIPE)
  copy(proc.stdout);proc.stdout.close()
  if proc.wait():raise RuntimeError('frame decode failed; output incomplete')
 out.flush();os.fsync(out.fileno())
assert written==s['source_size'] and h.hexdigest()==s['expected_sha256'],'restore SHA256 mismatch'
print(json.dumps({'bytes':written,'sha256':h.hexdigest()}))
