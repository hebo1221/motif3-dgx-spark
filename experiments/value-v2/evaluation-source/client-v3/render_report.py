"""Render an agent receipt as an answer with source passages for human review."""
import argparse
import html
import json
from pathlib import Path

def render(receipt):
    task=receipt.get('task') if isinstance(receipt.get('task'),dict) else receipt
    if task.get('status')!='answer_produced':
        return '# 보고서를 완성하지 못했습니다\n\n'+html.escape(task.get('error','상세 기록을 확인하세요.'))+'\n'
    report=task['report']
    lines=['# 검토할 답변','',report['answer'],'','## 확인한 원문','']
    for item in report['evidence']:
        lines+=['### '+item['doc_id']+' · '+str(item['start_line'])+'–'+str(item['end_line'])+'행','']
        lines+=['> '+html.escape(line) for line in item['quote'].splitlines()]
        lines+=['','원문 SHA-256: `'+str(item['source_sha256'])+'`','']
    lines+=['주제 범위와 원문 인용을 확인한 결과입니다. 답변의 해석·판단이 맞는지는 함께 제시된 원문으로 검토하세요.','']
    return '\n'.join(lines)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    with args.output.open('x') as handle:handle.write(render(json.loads(args.receipt.read_text())))
    print(args.output.resolve())

if __name__=='__main__':main()
