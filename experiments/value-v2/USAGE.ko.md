# 공개 문서 에이전트 사용법

Python 3과 네이티브 도구 호출을 지원하는 로컬 서버가 필요하다. 모델과 실행 바이너리는 포함하지 않는다. 아래 `agent.py`는 이미 실행 중인 localhost 서버를 사용하며, 모델을 자동으로 내려받거나 시작하지 않는다. 자세한 환경·파서 준비는 [영문 사용법](USAGE.md)에 있다.

## 모델 없이 실제 예제 보기

이 디렉터리에서 아직 존재하지 않는 출력 파일을 지정한다.

```bash
python3 client/render_report.py \
  --receipt evidence/motif-repair-recheck-v4/known-target-020.json \
  --output /tmp/motif-example-report.md
```

보고서에는 답변과 실제 원문 구절이 함께 표시된다. 형식이 맞고 원문이 존재해도 답변의 해석이 틀릴 수 있다. [실제 오류 예제](examples/README.ko.md)도 함께 확인한다.

## 내 문서 넣기

한 프로젝트의 UTF-8 Markdown 파일을 한 폴더 바로 아래에 둔다. 최대 256개, 파일당 32 KiB다. 하위 폴더·PDF·Word·심볼릭 링크는 지원하지 않는다.

```bash
python3 client/index_documents.py \
  --documents /absolute/path/to/documents \
  --subject my-project --alias '내 프로젝트'
```

색인은 모든 문서의 프로젝트와 해시를 기록하며 기존 색인을 덮어쓰지 않는다. 문서를 수정하면 새 스냅샷의 색인을 다시 만든다. 여러 프로젝트를 섞을 때에는 문서마다 올바른 프로젝트를 직접 배정해야 한다.

네이티브 도구 호출 서버를 따로 준비한 뒤 실행한다.

```bash
python3 client/agent.py \
  --endpoint http://127.0.0.1:8825 \
  --model-name YOUR_LOCAL_MODEL_NAME \
  --documents /absolute/path/to/documents \
  --subject my-project \
  --task '내 프로젝트의 확인 코드를 해당 문서를 인용해서 알려줘.' \
  --output /tmp/my-document-receipt.json
python3 client/render_report.py \
  --receipt /tmp/my-document-receipt.json \
  --output /tmp/my-document-report.md
```

질문의 대상을 `--subject`로 명시하는 편이 좋다. 색인이 있는 폴더에서 대상을 알 수 없으면 모델 호출 전에 중단한다. 색인이 없는 기존 폴더는 `subject_bound: false`로 표시된다.

## 한도와 결과 해석

업무당 최대 8단계·300초, 모델 요청당 최대 90초, 답변 최대 640자다. 최대 네 개의 실제 원문 구절을 붙이며 한 구절은 16행·4,000자 이하다. 마지막 단계에는 답변 또는 근거 부족 보고만 허용한다. 미완성 보고서에 두 번까지 수정 기회를 주지만 같은 호출을 반복하면 중단한다.

모델 도구는 문서 검색·읽기·제한 산술·보고다. 파일 수정, 외부 명령, 웹 검색, 메시지 발송 도구는 없다. 실행 프로그램은 사용자가 지정한 결과 파일을 저장한다. `answer_produced`는 검토할 답변이 생겼다는 상태이며 정답 보증이 아니다.

최종 소스의 경계 검사 30개는 Mac과 Spark에서 통과했다. `client` 디렉터리에서 `python3 -m unittest -v test_agent`로 실행할 수 있다. 공개본의 색인은 공개 문서 해시에 연결돼 있다. 원래 실험과 공개 문서의 입력 바이트는 다를 수 있으므로, 재실행 결과는 별도의 새 실험으로 기록한다.
