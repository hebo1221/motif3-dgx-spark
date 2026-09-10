#!/usr/bin/env python3
"""Offline integrity and score replay; does not run or qualify a model."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'EXPORT.json').read_text())
for row in manifest['files']:
    path = root / row['published']
    assert path.is_file(), row['published']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == row['published_sha256'], row['published']

def read(name):
    return json.loads((root / name).read_text())

def lines(name):
    return [json.loads(s) for s in (root / name).read_text().splitlines() if s.strip()]

cases = lines('evidence/q4/quality-cases.jsonl')
answers = lines('evidence/q4/quality-cap8192/answers.jsonl')
assert len({a['id'] for a in answers}) == len(answers) == len(cases) == 16
by_id = {a['id']: a['text'] for a in answers}
score = read('evidence/q4/quality-cap8192/score.json')
expected_results = {a['id']: a['passed'] for a in score['results']}
passed = 0
for case in cases:
    try:
        result = json.loads(by_id[case['id']])
        ok = isinstance(result, dict) and result == case['expected']
    except json.JSONDecodeError:
        ok = False
    assert ok == expected_results[case['id']], case['id']
    passed += ok
assert passed == score['passed'] == 10 and score['total'] == 16
outcome = read('evidence/q4/outcome.json')
assert outcome['routed_q4_layers'] == 51
assert outcome['actual_weight_bytes'] == 186896804480
assert outcome['bf16_quality_preservation_verified'] is False
assert outcome['production_default_changed'] is False
long_run = read('evidence/q4/sustained-summary.json')['results'][0]
assert long_run['generated_tokens'] == 1024
assert round(long_run['decode_tps'], 2) == 2.81
assert outcome['sustained']['finish_reason'] == 'length'
assert outcome['sustained']['results'][0]['decode_tps'] == long_run['decode_tps']
for name in ('bf16_cpu_unified.json', 'iq2_cpu_unified.json'):
    rows = read('evidence/earlier-four-choice/' + name)['rows']
    assert len(rows) == 4 and sum(r['choice_pass'] for r in rows) == 3
print(json.dumps({'status': 'pass', 'exported_files_verified': len(manifest['files']),
                  'strict_json_replayed': f'{passed}/16', 'earlier_choice_each': '3/4',
                  'new_model_requests': 0, 'bf16_q4_quality_comparison': 'not_performed'}))
