# DGX Spark 한 대에서 Motif-3 315B 구동하기

**2026-09-10: 탐색 연구를 마무리했습니다.** 내부 NVMe에서 전문가 가중치를
읽는 Q4 후속 실험은 1,024토큰 생성에서 평균 2.81토큰/초를 기록했습니다.
지속 3~5토큰/초 목표에는 못 미쳤고, BF16과 Q4의 동일 조건 품질 비교는
미완료입니다. 아래 IQ2 다운로드와 기존 측정값은 그대로 유지합니다.

**[최종 회고](docs/FINAL_REPORT.ko.md) · [Q4 코드와 측정 기록](experiments/ssd-offload/README.md)**


[English](README.md) | [한국어](README.ko.md)

![DGX Spark 한 대에서 구동한 Motif-3 315B: 83.56 GiB, 프롬프트 처리 316.71 tok/s, 생성 16.49 tok/s](assets/motif3-dgx-spark-result-card.png)

[Motif-3](https://huggingface.co/Motif-Technologies/Motif-3)의 3,147억
파라미터 핵심 모델을 혼합 IQ2_XXS GGUF로 압축해, 128 GB NVIDIA DGX
Spark 한 대에서 구동한 프로젝트입니다. 최종 파일은 83.56 GiB이며 모든
모델 레이어를 GPU에 올렸습니다.

정확한 원본 모델 리비전, Motif를 지원하는 고정 llama.cpp 런타임,
토크나이저 수정 패치, 벤치마크 원본, 체크섬과 재현 절차를 함께
공개합니다.

**[GGUF 다운로드](https://huggingface.co/jhkim55/Motif-3-Direct-IQ2-XXS-DGX-Spark)**
· **[런타임 안내](docs/RUNTIME.md)**
· **[측정 결과](docs/RESULTS.md)**
· **[케이스 스터디](docs/CASE_STUDY.ko.md)**

## 한눈에 보기

| 항목 | 결과 |
|---|---:|
| 원본 | 공식 BF16 `883d5c441fe3bb994c7b57e60f49e26147f85512` |
| 파라미터 | 314,701,772,930 |
| 최종 파일 | 89,720,474,560 bytes / 83.56 GiB |
| BF16 대비 크기 | 7.02배 축소 |
| 실효 저장 밀도 | 원소당 2.2805비트 |
| pp512 | 316.71 tok/s |
| pp2048 | 312.76 tok/s |
| tg128 | 16.49 tok/s |
| pp2048 + tg128 | 149.33 tok/s |

성능 수치는 깨끗한 공개 빌드에서 각 항목을 다섯 번 측정한 평균입니다.
전체 결과와 별도로 진행한 세 번의 안정성 측정은
[측정 결과](docs/RESULTS.md)에 정리했습니다.

> [!IMPORTANT]
> 이 GGUF는 아래에 고정한 Motif 지원 런타임과 토크나이저 패치가
> 필요합니다. 패치하지 않은 upstream llama.cpp와의 호환성은 아직 확인하지
> 않았습니다.

> [!NOTE]
> 이 릴리스는 모델을 Spark 한 대에 올려 구동한 사례입니다. BF16과 같은
> 품질을 보장하는 양자화는 아닙니다. 실제 구동과 유용한 속도는
> 확인했지만, 사전에 정한 BF16 품질 유지 기준은 통과하지 못했습니다.

## GPU 없이 살펴보기

[실제 답변과 원문](docs/RECORDED_DEMO.md)에는 문서 에이전트의 답변과
그 답변이 인용한 근거를 같이 담았습니다. 올바른 숫자를 인용하고도
결론을 잘못 낸 사례까지 그대로 남겨 두었습니다. 모델을 받지 않고도
공개 기록을 확인할 수 있습니다.

```bash
git clone --depth 1 https://github.com/hebo1221/motif3-dgx-spark.git
cd motif3-dgx-spark
python3 experiments/value-v2/verify_public.py
```

검증 스크립트는 오프라인에서 파일 해시와 인용 구간을 확인하며, 모델에
요청을 보내지 않습니다. CUDA 빌드만 있으면 모델 가중치 없이 실행하는
[Q8 수치 검증 도구](experiments/value-v2/runtime/README.md)도 재사용할 수 있습니다.

## 빠른 시작

### 준비 사항

검증에 사용한 장비는 NVIDIA DGX Spark 한 대입니다. 다음 공간과 도구가
필요합니다.

- 모델 파일 약 90 GB
- 다운로드와 런타임 빌드를 포함해 최소 110 GB의 여유 디스크
- 다른 대형 GPU 작업을 중지한 상태의 128 GB 통합 메모리
- Git, CMake, C++ 컴파일러, CUDA Toolkit, `hf` CLI

다른 128 GB NVIDIA 시스템에서도 동작할 수 있지만, 이 프로젝트에서
직접 측정하지는 않았습니다.

### 1. 모델과 템플릿 받기

```bash
mkdir -p model

hf download jhkim55/Motif-3-Direct-IQ2-XXS-DGX-Spark \
  motif3-direct-iq2xxs.gguf \
  motif3-llama.cpp.jinja \
  --revision 3511f72d7ceac63e2931b27e1666766f2ad18d54 \
  --local-dir model

sha256sum model/motif3-direct-iq2xxs.gguf
```

정상 파일의 SHA-256은 다음과 같습니다.

```text
9d6f7aee57f0271223f51d69c63d8576a259809e9f05e2ac596512e940c80c5a
```

다운로드를 마친 뒤 읽기 전용 검증 스크립트를 실행할 수도 있습니다.

```bash
git clone --branch v1.2.0 --depth 1 \
  https://github.com/hebo1221/motif3-dgx-spark.git release-files

release-files/scripts/verify_download.sh model
```

### 2. 런타임 빌드하기

```bash
git clone --branch motif3-dgx-spark-v1 --single-branch \
  https://github.com/hebo1221/llama.cpp.git runtime

git -C runtime checkout cc3f13b3f172978d7b3c215780d4cc98bb0e1c80

sha256sum release-files/patches/motif3-tokenizer-exact-v1.patch
git -C runtime apply --check --unidiff-zero \
  ../release-files/patches/motif3-tokenizer-exact-v1.patch
git -C runtime apply --unidiff-zero \
  ../release-files/patches/motif3-tokenizer-exact-v1.patch

git -C runtime diff --binary --no-ext-diff | sha256sum

cmake -S runtime -B runtime/build \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_CUDA=ON \
  -DGGML_CUDA_FA=ON \
  -DGGML_CUDA_GRAPHS=ON \
  -DGGML_NATIVE=ON \
  -DLLAMA_BUILD_UI=OFF \
  -DLLAMA_USE_PREBUILT_UI=OFF

cmake --build runtime/build --target llama-server llama-bench -j 12
```

토크나이저 패치의 SHA-256은
`5eba842cd63731e3ee39c60c43134ef59a3a64c9d28c2aa58c3073225c6545cf`여야
합니다. 패치를 적용한 뒤 일반 Git diff의 해시는
`09abc52c2f7ff9f2cb3e9b8edd3af03684840969d0cdc7f24fd7aa63ca3207f3`입니다.
이 패치는 Motif 토크나이저 처리만 바꾸며, 모델 가중치나 다른 토크나이저
계열에는 영향을 주지 않습니다.

### 3. 서버 실행하기

```bash
runtime/build/bin/llama-server \
  -m model/motif3-direct-iq2xxs.gguf \
  -ngl 99 \
  -fa on \
  -ctk f16 \
  -ctv f16 \
  -b 2048 \
  -ub 512 \
  -c 32768 \
  -np 1 \
  --host 127.0.0.1 \
  --port 8080 \
  --no-ui \
  --jinja \
  --chat-template-file model/motif3-llama.cpp.jinja
```

별도 인증을 구성하지 않았다면 서버는 `127.0.0.1`에만 바인딩하세요.
모델 로딩이 끝나면 다음 요청으로 확인합니다.

```bash
curl -fsS http://127.0.0.1:8080/health

curl -fsS http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "messages": [
      {"role": "user", "content": "한국의 수도는 어디인가요? 한 문장으로 답해주세요."}
    ],
    "temperature": 0,
    "max_tokens": 24,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
```

공개 성능 기준 빌드의 간단한 확인 요청은
`한국의 수도는 서울입니다.`라고 답했고, 빌드 정보는
`b10498-cc3f13b3f`였습니다. 이 확인과 공개 속도 측정은 v1.1.0
토크나이저 패치를 적용하기 전에 진행했습니다.

## 벤치마크 재현

모델을 사용하는 다른 프로세스가 없을 때만 실행하세요.

```bash
runtime/build/bin/llama-bench \
  -m model/motif3-direct-iq2xxs.gguf \
  -ngl 99 -fa on \
  -ctk f16 -ctv f16 \
  -b 2048 -ub 512 -t 20 \
  --delay 3 \
  -p 512,2048 \
  -n 128 \
  -pg 2048,128 \
  -r 5 \
  -o jsonl
```

정규화한 결과는
[`evidence/clean_runtime_benchmark.jsonl`](evidence/clean_runtime_benchmark.jsonl),
빌드 정보와 서버 확인 결과는
[`evidence/clean_runtime_verification.json`](evidence/clean_runtime_verification.json)에
있습니다.

## 양자화 구성

이 파일은 순수 2비트 모델이 아니라 혼합 정밀도 GGUF입니다. 파라미터의
대부분을 차지하는 expert 텐서는 IQ2_XXS로 줄이고, 임베딩·출력·
어텐션·라우팅·제어 텐서는 더 높은 정밀도로 남겼습니다.

| 저장 형식 | 텐서 수 | 데이터 크기(bytes) |
|---|---:|---:|
| IQ2_XXS | 306 | 78,631,821,312 |
| BF16 | 424 | 7,252,475,904 |
| Q8_0 | 2 | 1,916,272,640 |
| Q2_K | 6 | 1,357,676,544 |
| F32 | 1,424 | 552,591,880 |

변환 경로는 다음과 같습니다.

```text
공식 BF16 -> BF16 GGUF -> IQ2_XXS
```

Q5 중간 모델이나 `--allow-requantize`는 사용하지 않았습니다. 원본과 텐서
구성은 [변환 방법](docs/METHOD.md)에 정리했습니다.

## 검증 범위

공개된 근거로 다음 항목을 확인할 수 있습니다.

- 54개 모델 레이어 전체 GPU 로드
- 고정한 런타임에서 정확히 같은 89.72 GB GGUF 로드
- `/health`, `/slots`, Chat Completions 요청 완료
- 공식 토크나이저와 말뭉치 115,618개 토큰 ID 및 고정 퍼즈 테스트
  318,951개 토큰 ID 일치
- 확장 토크나이저 실험에서 4,164,390개 토큰 ID 일치
- 토크나이저 회귀 테스트 16개 통과
- 모델·템플릿·원본 샤드·텐서·벤치마크 기록의 SHA 고정

토크나이저 근거는
[`evidence/tokenizer_exact_v1.json`](evidence/tokenizer_exact_v1.json)에
있습니다. 이 패치는 입력 토큰 ID를 바로잡는 작업이며 IQ2 가중치의 품질을
높이지는 않습니다.

## 품질과 알려진 한계

고정한 49,152토큰 검증 세트에서 BF16 대비 퍼플렉서티 비율은 1.4115배,
평균 KL 발산은 0.4541이었습니다. 사전에 정한 기준인 1.10과 0.10을
모두 넘었습니다. BF16의 대체재보다는 로컬 시스템 연구와 실험용 모델로
보는 편이 맞습니다.

그 밖의 한계는 다음과 같습니다.

- 다운로드 가능한 GGUF에는 Motif-3의 네이티브 MTP 헤드가 없습니다.
- 원본 모델은 256K 컨텍스트를 제시하지만, 이 릴리스에서는 256K 검색·생성
  품질을 검증하지 않았습니다.
- 이 비트레이트에서는 도구 호출이 불안정합니다. JSON 검증으로 형식은
  바로잡을 수 있지만 도구를 호출할지 말지에 대한 잘못된 판단까지 고칠
  수는 없습니다.
- 서버의 `-c`는 병렬 슬롯 전체가 나눠 쓰는 값입니다. 요청 하나의
  컨텍스트로 간주하지 말고 `/slots`를 확인하세요.
- 내부 평가 세트의 결과는 진단 지표이며 공개 리더보드 점수가 아닙니다.
- 양자화 생성 이력 필드 두 곳에 로컬 빌드 경로가 남아 있습니다. 추론에는
  쓰이지 않으며 공개 SHA는 현재 파일 그대로를 고정합니다.
- 처리량 수치는 토크나이저 패치 이전의 고정 v1.0.0 런타임에서 측정했고,
  현재도 그 조건으로 표시합니다.

부모 모델의 특성과 양자화 손실을 어떻게 구분할지는
[Discussion #1](https://github.com/hebo1221/motif3-dgx-spark/discussions/1)에서
논의하고 있습니다. 동일 문항을 사용한 BF16/Q5 비교, 혼합 정밀도 제안,
다른 Spark의
재현 결과를 환영합니다.

## 프로젝트 상태

집중적인 연구 단계는 마친 상태입니다. 공개 모델, 토크나이저 패치,
수치 검증 도구와 에이전트 실패 기록은 시스템 케이스 스터디와 로컬
실험의 출발점으로 계속 유지합니다. 새 모델 학습이나 범용 에이전트 개발은
현재 예정하고 있지 않습니다.

재현 가능한 결함, 독립적인 Spark 측정, 범위가 명확한 실제 사용 사례는
후속 작업의 근거가 될 수 있습니다. 자세한 유지보수 기준은
[프로젝트 상태](docs/PROJECT_STATUS.md)에 정리했습니다.

## 재사용 가능한 후속 실험

[v1.3.0-rc.1](https://github.com/hebo1221/motif3-dgx-spark/releases/tag/v1.3.0-rc.1)에는
모델 가중치 없이 돌릴 수 있는 Q8 배치 일관성 검사, 두 파일로 구성된
선택형 참조 패치, 그리고 프로젝트 자료와 원문 인용을 사용하는 문서
에이전트가 들어 있습니다. 참조 경로는 더 느리고, 에이전트는 여전히 사실
오류를 낼 수 있습니다. 두 결과와 검증 기록을 모두 공개했습니다.

자세한 내용은 [후속 실험 안내](experiments/value-v2/README.md)와
[한국어 결과](experiments/value-v2/README.ko.md)에서 확인할 수 있습니다.

## 실험적 네이티브 MTP 후속 작업

v1.2.0에는 Motif-3의 1개 레이어 MTP 헤드를 위한 선택형 소스 패치가
추가되었습니다. 공개 GGUF와는 바이트가 다른 별도 기준 모델에서
기준 모델/MTP/기준 모델 순서의 A-B-A 실험을 진행했고, 두 비교 구간 모두
그리디 토큰 5,120/5,120개가 일치했습니다. 서버가 보고한 디코드 속도는
앞뒤 기준 모델 측정 평균 14.5872 tok/s에서 17.5565 tok/s로
**1.2036배** 높아졌고 draft 토큰 채택률은 47.11%였습니다.

이는 새 모델 업로드가 아닙니다. 512 MB MTP 사이드카는 재배포하지 않았고,
다운로드 가능한 GGUF도 바뀌지 않았습니다. 따라서 이 수치를 공개 GGUF의
성능으로 해석하면 안 됩니다. 패치, 사이드카 생성법, 근거와 제한사항은
[실험적 네이티브 MTP](docs/MTP_EXPERIMENTAL.md)에 정리했습니다.

## 문서

- [엔지니어링 케이스 스터디](docs/CASE_STUDY.md) · [한국어 회고](docs/CASE_STUDY.ko.md)
- [실제 답변과 오프라인 검증](docs/RECORDED_DEMO.md)
- [프로젝트 상태와 완료 기준](docs/PROJECT_STATUS.md)
- [변환 방법과 원본 고정](docs/METHOD.md)
- [측정 결과와 한계](docs/RESULTS.md)
- [후속 실험에서 얻은 점](docs/ENGINEERING_FINDINGS.md)
- [런타임과 문제 해결](docs/RUNTIME.md)
- [실험적 네이티브 MTP](docs/MTP_EXPERIMENTAL.md)
- [기계 판독형 지표](evidence/public_metrics.json)

## 재현 결과 공유

다른 DGX Spark나 비슷한 128 GB NVIDIA 시스템에서 실행했다면
[벤치마크 양식](https://github.com/hebo1221/motif3-dgx-spark/issues/new?template=benchmark.yml)으로
결과를 남겨 주세요. 최고 수치 하나보다 전체 실행 명령과 원본
`llama-bench` JSONL이 더 유용합니다. 설치 질문이나 초기 결과는
[Discussions](https://github.com/hebo1221/motif3-dgx-spark/discussions)에
올리면 됩니다.

## 라이선스

저장소의 코드와 직접 작성한 문서는 MIT License로 배포합니다. 파생 모델은
원본 Motif-3의 라이선스와 출처를 유지합니다. Motif Technologies의 모델,
llama.cpp, Chrono의 Motif 포트와 문서에 명시한 GQA-5 작업을 기반으로 했으며,
개발과 분석에 Codex의 도움을 받았습니다. 자세한 내용은 [NOTICE](NOTICE.md)를
확인하세요. 이 프로젝트는 Motif Technologies, NVIDIA 또는 llama.cpp의
공식 릴리스가 아닙니다.
