"""Verify public checksums, redacted fixture bindings, and recorded source spans."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    provenance=json.loads((ROOT/'PUBLIC-PROVENANCE.json').read_text())
    records={row['path']:row for row in provenance['imported_files']}
    for name,row in records.items():
        if sha(ROOT/name)!=row['public_sha256']:raise ValueError('Public file changed: '+name)
    freeze=json.loads((ROOT/'workflows/public-freeze.json').read_text())
    for name,digest in freeze['files'].items():
        if sha(ROOT/'workflows'/name)!=digest:raise ValueError('Public fixture changed: '+name)
    for path in (ROOT/'workflows').rglob('document-index.json'):
        index=json.loads(path.read_text())
        for doc_id,meta in index['documents'].items():
            if sha(path.parent/(doc_id+'.md'))!=meta['sha256']:raise ValueError('Index no longer matches source')
    cases={c['id']:c for c in json.loads((ROOT/'workflows/cases.json').read_text())}
    spans=0;reports=0
    for path in sorted((ROOT/'evidence').glob('*/*.json')):
        data=json.loads(path.read_text())
        if data.get('status')!='answer_produced' or data.get('case_id') not in cases:continue
        case=cases[data['case_id']];reports+=1
        for item in data['report']['evidence']:
            source=ROOT/'workflows'/case['documents']/(item['doc_id']+'.md')
            expected='\n'.join(source.read_text().splitlines()[item['start_line']-1:item['end_line']])
            if item['quote']!=expected:raise ValueError('Recorded span differs from public source')
            row=records[source.relative_to(ROOT).as_posix()]
            if item['source_sha256']!=row['original_sha256']:raise ValueError('Original document binding differs')
            spans+=1
    for name in ['confirmation-semantic-review.json','repair-semantic-review.json']:
        review=json.loads((ROOT/'evidence'/name).read_text())
        for row in review['cases']:
            if records[row['response_file']]['original_sha256']!=row['response_sha256']:
                raise ValueError('Review does not bind its original response')
    print(json.dumps({'status':'pass','imported_files_verified':len(records),
        'public_fixture_files_verified':len(freeze['files']),'recorded_reports_checked':reports,
        'redacted_source_spans_checked':spans,'new_model_requests':0}))

if __name__=='__main__':main()
