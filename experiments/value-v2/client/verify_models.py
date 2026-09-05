#!/usr/bin/env python3
"""Verify the exact released direct IQ2 and linked MTP file pair once."""
import argparse
import hashlib
import json
from pathlib import Path
import time

EXPECTED = {
    "target": (89720474560, "9d6f7aee57f0271223f51d69c63d8576a259809e9f05e2ac596512e940c80c5a"),
    "sidecar": (512363040, "d813251f1b7e8158399352af6e44c92df2445cd807fda1a869d2247279806f81"),
}


def identity(path):
    path=path.resolve(strict=True)
    stat=path.stat()
    return dict(path=str(path),size_bytes=stat.st_size,mtime_ns=stat.st_mtime_ns,
                inode=stat.st_ino,device=stat.st_dev)


def check_binding(path, model, sidecar):
    receipt=json.loads(path.read_text())
    if receipt.get('status')!='pass' or not receipt.get('files_stable_during_check'):
        raise ValueError('Binding did not pass its full hash check')
    for key,asset in [('target',model),('sidecar',sidecar)]:
        current=identity(asset)
        if any(receipt[key].get(k)!=v for k,v in current.items()):
            raise ValueError(f'{key} path or file identity changed; run verification again')
        if receipt[key].get('sha256')!=EXPECTED[key][1]:
            raise ValueError(f'{key} is not the tested artifact')
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--sidecar',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Choose a new receipt path; old evidence is never overwritten')
    receipt=dict(schema_version='motif3-integrated-artifact-check-v1',status='pass',
                 created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
    for key,path in [('target',args.model),('sidecar',args.sidecar)]:
        before=identity(path)
        if before['size_bytes']!=EXPECTED[key][0]:raise ValueError(f'{key} size mismatch')
        print(f'Hashing {key}: {before["size_bytes"]:,} bytes',flush=True)
        with path.open('rb') as handle:
            sha256=hashlib.file_digest(handle,'sha256').hexdigest()
        if before!=identity(path):raise ValueError(f'{key} changed during verification')
        if sha256!=EXPECTED[key][1]:raise ValueError(f'{key} SHA-256 mismatch')
        receipt[key]=dict(before,sha256=sha256)
    receipt['files_stable_during_check']=True
    with args.output.open('x') as handle:
        handle.write(json.dumps(receipt,indent=2)+'\n')
    print('PASS:',args.output)


if __name__=='__main__':
    main()
