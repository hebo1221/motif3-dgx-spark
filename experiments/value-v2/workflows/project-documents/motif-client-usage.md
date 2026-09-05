# DGX Spark에서 문서 에이전트 실행하기

이 패키지는 Python 표준 라이브러리와 이미 준비한 로컬 런타임을 사용한다.
모델 가중치와 실행 바이너리는 포함하지 않는다. 현재 검증한 운영체제는
DGX Spark의 Linux ARM64다.

## 현재 Spark에서 한 번 실행

검증에 사용한 폴더는 다음과 같다.

```text
/opt/motif-work/motif3-quant/campaigns/agent-readiness-v1/release-client-v1
```

다른 모델 작업이 실행 중이지 않을 때 다음과 같이 사용한다. 출력 폴더는
아직 존재하지 않는 이름을 지정한다.

```bash
cd /opt/motif-work/motif3-quant/campaigns/agent-readiness-v1/release-client-v1
python3 run_local.py \
  --config ../config.default-agent.json \
  --documents demo-documents \
  --task 'Motif-3의 이전 단계와 현재 단계 문서를 모두 읽고, 도구 호출 문제의 상태와 원본 품질 보존 검증 여부를 두 문서를 인용해 알려줘.' \
  --draft 0 \
  --output runs/my-first-document-task
```

실행기는 로컬 서버를 띄워 업무 하나를 수행하고 자신이 띄운 서버를 종료한다.
모델 적재 시간은 답변 시간과 별도다. 종료 후에도 결과 폴더에
`receipt.json`, `server-lifecycle.json`, 서버 로그와 메모리 관측 기록이 남는다.
서버를 상시 등록하거나 외부 주소에 공개하지 않는다.

`--print-command`를 추가하면 모델을 시작하지 않고 실행 경로와 설정만 확인한다.
`--draft 0`은 MTP를 끈 비교용 실행이다. 명시하지 않으면 실행기의 기본값은 0이다.
이번 별도 100건 평가에서는 `--draft 1`을 사용했다.

기본 설정은 Qwen3-8B Q8_0이다. Motif IQ2와 MTP를 실험하려면 같은 폴더에서
다음 설정으로 실행한다.

```bash
python3 run_local.py \
  --config ../config.agent.json \
  --documents demo-documents \
  --task 'Motif-3의 이전 단계와 현재 단계 문서를 모두 읽고, 도구 호출 문제의 상태와 원본 품질 보존 검증 여부를 두 문서를 인용해 알려줘.' \
  --draft 1 \
  --output runs/my-first-motif-task
```

## 내 문서를 넣기

별도 디렉터리 안에 UTF-8 Markdown 문서를 둔다. 현재 지원 범위는 폴더
바로 아래의 `.md` 파일, 최대 256개, 파일당 32 KiB다. 파일 이름에서
확장자를 뺀 값이 문서 ID다. 심볼릭 링크와 폴더 밖 파일은 허용하지 않는다.
문서 ID는 영문·숫자·하이픈 등 짧고 구별하기 쉬운 이름을 권한다.

`--documents`를 그 디렉터리로 바꾸고, `--task`에 찾고 싶은 정보나 계산을
적는다. 검색은 단어 출현 횟수로 상위 네 문서를 고른다. PDF, Word, 하위
디렉터리, 의미 기반 검색은 현재 구현 범위에 들어 있지 않다.

에이전트는 최대 여섯 차례 도구를 선택하고, 업무당 180초 안에 끝낸다.
한 모델 요청은 최대 60초이며 최종 보고서는 최대 320자와 인용 네 개다.
파일 수정, 명령 실행, 인터넷 검색, 메시지 발송 도구는 제공하지 않는다.

## 결과 읽기

- `status: answer_produced`: 형식과 출처 검사를 통과한 보고서가 생겼다.
  사실 정확성을 자동으로 보증하는 상태는 아니다.
- `report.status: answered`: 읽은 문서를 인용해 답변했다.
- `report.status: insufficient_evidence`: 필요한 정보가 없다고 답변했다.
- `status: failed`: 시간·단계 제한, 잘린 응답, 잘못된 호출, 반복 호출 등의
  이유로 중단했다. `error`와 `steps`에서 마지막 상태를 확인한다.
- `steps[].execution: completed`: 실제 도구 구현을 실행했다.
  `source_receipts`에는 읽은 문서의 SHA-256이 기록된다.
- `server-lifecycle.json`의 `owned_process_stopped`는 실행기가 띄운 서버의
  종료 여부다.

오류가 나면 기록을 보존하고 원인을 확인한다. 사실을 잘못 답한 경우에는
질문, 기대 답, 근거 문서, 실제 답을 함께 남긴다. 별도 평가의 실패를 고친
후 같은 문제를 다시 풀어 높은 점수만 보고하면 독립 평가가 되지 않는다.

## 다른 디렉터리에 패키지를 옮겼을 때

`config.example.json`은 Qwen 기본 예제이고, `config.motif.example.json`은
Motif 예제다. 사용할 모델의 후보 바이너리, target, 모델 검증 기록의
절대 경로를 채운다. Motif에는 sidecar 경로도 필요하다. `gpu_uuid`가 비어 있으면 실행기가
현재 한 GPU의 식별자를 읽는다. 설정의 모델 경로는 검증 기록과
일치해야 한다.

Qwen용 예제는 `config.qwen.example.json`이다. `backend`를 `qwen`으로 두고,
Qwen 전용 후보 바이너리와 전체 해시 검사 후 기록한 파일 식별 정보를 사용한다.
실행기는 공식 Q8_0의 해시와 기록의 경로·크기·수정 시각·inode를 확인한다.

모델을 새로 복사했다면 파일 크기만 보고 검증을 승계하지 않는다.
Motif 파일 쌍은 동봉한 `verify_models.py`로 전체 해시를 확인해 새 기록을 만들 수 있다.
89.72 GB 파일 전체를 읽으므로 이 작업은 모델 평가와 겹치지 않게 수행한다.

```bash
python3 verify_models.py \
  --model /absolute/path/to/motif3-direct-iq2xxs.gguf \
  --sidecar /absolute/path/to/motif3-mtp-linked-bf16.gguf \
  --output /absolute/path/to/model-binding.json
```

`run_local.py`는 후보 바이너리가 있는 디렉터리로 `LD_LIBRARY_PATH`를
설정한다. 직접 서버를 띄우는 경우에도 이것이 필요하다. 복사된 서버의
기존 RPATH 때문에 이전 공용 라이브러리가 선택될 수 있기 때문이다.

## 검사와 재현

모델 없이 실행하는 에이전트 경계 검사는 다음과 같다.

```bash
python3 -m unittest -v test_agent
```

현재 Spark의 원본 실험 폴더에서는 다음 명령으로 새 이름의 개발 검사를
수행할 수 있다. 100건과 정답은 이미 본 평가 자료이므로, 이를 다시 실행한
결과를 새 독립 성능 평가로 발표해서는 안 된다.

```bash
python3 run_campaign.py \
  --run my-development-check \
  --backend motif --draft 1 \
  --phases quality stream development
```

위 평가 명령의 작업 디렉터리는
`/opt/motif-work/motif3-quant/campaigns/agent-readiness-v1`이다.
`release-client-v1`에서 실행할 때에는 먼저 상위 디렉터리로 이동한다.
평가 원본 클라이언트와 잘못된 계산식 처리만 보완한 전달용 클라이언트는
분리해 보존했다. 차이와 검증 범위는 `EVALUATION.md`에 있다.

수정 후 Qwen 개발 비교에는 상위 실험 폴더의 `run_campaign_qwen_v2.py`와
`--backend qwen --draft 0`을 사용한다. `baseline-download.json`과
`baseline-before-evaluation.json`이 고정 리비전과 전체 해시 검사 결과를 갖고 있다.
이 실행은 공식 내장 템플릿의 메시지 형식에 별도 호출 파서를 연결한 구성이다.
처음 사용한 기본 파서의 실패·중단 기록은 보존했다.

원본 모델 파일을 검사한 경로·inode·mtime 기록과 실험용 `config.json`은
장치에 종속된다. 패키지의 예제 설정만으로 다른 장치에서 전체 평가가
자동 재현된다고 가정하지 않는다.

## 파서 빌드 범위

`build_overlay.py`는 현재 Spark에 있는 기존 통합 빌드
`/opt/motif-work/motif3-integrated-runtime-v1`을 기반으로 한다.
비어 있는 별도 패키지 디렉터리에서 실행하면 그 디렉터리에 `runtime/`을
만들고, 동봉한 `chat.cpp`만 다시 컴파일해 공용 라이브러리를 연결한다.
이미 `runtime/`이 있으면 덮어쓰지 않고 중단한다. 모델 평가가 실행 중일
때에는 빌드하지 않는다.

측정에 사용한 것은 이 방식으로 만든 분리된 런타임이다. 새 패치를 넣은
전체 CMake 재빌드는 이번 단계에서 검증하지 않았다. 다른 기반 커밋,
컴파일러 또는 GPU에 적용할 때에는 별도 빌드·검사가 필요하다.

지원 API는 thinking을 끈 현재 프로필의 required/auto/none 도구 선택,
단일 도구 호출, 별도 JSON 스키마 응답이다. 호출 도구를 이름 객체로 지정하는
형식, assistant prefill, 활성 도구와 response_format의 동시 사용은 이번
프로필의 지원 범위에 포함하지 않는다.

Qwen 비교 런타임의 추가 패치는 `qwen-parser/qwen-handler-only.patch`에 있다.
이는 Motif 후보 소스 위에 적용하는 별도 옵션 파서다. 실제 측정에 사용한
Qwen 빌드도 기존 통합 빌드의 객체 파일을 재사용한 분리된 공용 라이브러리다.
