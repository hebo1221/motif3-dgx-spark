"""Create a digest-bound index for a folder containing one project's Markdown files."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from agent import DocumentStore

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--documents',type=Path,required=True)
    p.add_argument('--subject',required=True)
    p.add_argument('--alias',action='append',default=[])
    args=p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',args.subject):p.error('Use an ASCII subject id of at most 80 characters')
    aliases=args.alias or [args.subject]
    if not 1<=len(aliases)<=8 or any(not 1<=len(alias)<=120 for alias in aliases):p.error('Use 1 to 8 short aliases')
    target=args.documents/'document-index.json'
    if target.exists() or target.is_symlink():p.error('An index already exists; preserve it before creating a new snapshot')
    store=DocumentStore(args.documents)
    if not store.paths:p.error('No Markdown documents found')
    index={'version':1,'subjects':{args.subject:aliases},'documents':{}}
    for doc_id in store.paths:
        document=store.read(doc_id)
        index['documents'][doc_id]={'subject':args.subject,'sha256':document['sha256']}
    with target.open('x') as handle:json.dump(index,handle,ensure_ascii=False,indent=2);handle.write('\n')
    print(json.dumps({'index':str(target.resolve()),'subject':args.subject,'documents':len(store.paths),
                      'sha256':hashlib.sha256(target.read_bytes()).hexdigest()},ensure_ascii=False))

if __name__=='__main__':main()
