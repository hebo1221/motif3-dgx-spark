# 확인 질문의 답변 내용 검토

질문과 항목별 기준은 실행 전에 고정했다. 아래 등급은 답변을 읽은 뒤 같은 assistant가 판단했다. 독립·블라인드 평가는 아니다. 기준과 실행 조건은 [평가 방법](EVALUATION.ko.md)에 있다.

| 질문 | Motif v3 | Qwen v3 |
|---|---|---|
| 공개 문구 | PASS | FAIL |
| 5,560 토큰의 비교 대상 | PASS | FAIL |
| 과거·현재 도구 호출 시험 | PARTIAL | FAIL |
| Qwen 결과의 일반화 | FAIL | PARTIAL |
| 서버 준비·냉시작 | PASS | FAIL |
| 속도 개선 우선순위 | PARTIAL | PARTIAL |
| 실행 범위 | PARTIAL | PARTIAL |
| 중간 오류와 최종 정답 | PASS | FAIL |

## 공개 문구

**motif — PASS**. 원본 품질·범용 완성 주장을 함께 부정하고 문서 보조 파일럿으로 대체 문구를 좁혔다.

[원시 응답과 도구 기록](evidence/motif-confirmation-v3/confirm-release.json)

**qwen — FAIL**. 원본 품질 보존은 부정했지만 대체 문구를 범용 코딩 에이전트의 성능·실행 입증으로 제시했다. 검증된 문서 보조 범위로 좁히지 않았다.

[원시 응답과 도구 기록](evidence/qwen-confirmation-v3/confirm-release.json)


## 5,560 토큰의 비교 대상

**motif — PASS**. 같은 통합 런타임의 가속 꺼짐·켜짐·복구와 target-only 대조를 설명하고 BF16 원본 품질 일치를 명확히 부정했다.

추가 출처 검토: 본문이 motif-agent-current L5를 지목한 부분은 실제로 L52의 내용이다. 구조화된 근거에는 올바른 L50–52도 포함돼 있다.
[원시 응답과 도구 기록](evidence/motif-confirmation-v3/confirm-parity.json)

**qwen — FAIL**. 5,560개 토큰 일치를 Motif IQ2와 Qwen Q8_0 간 동일 출력으로 잘못 설명했다. 같은 IQ2 런타임의 가속 전후 비교와 BF16 미검증을 구분하지 못했다.

[원시 응답과 도구 기록](evidence/qwen-confirmation-v3/confirm-parity.json)


## 과거·현재 도구 호출 시험

**motif — PARTIAL**. 검증 단계와 조건이 달라 지능 향상으로 직접 비교할 수 없다고 답했다. 40/40을 가능하게 한 템플릿·파서 수정은 충분히 설명하지 않고 100문항 비교로 비중이 옮겨갔다.

[원시 응답과 도구 기록](evidence/motif-confirmation-v3/confirm-version.json)

**qwen — FAIL**. 직접 지능 비교는 부정했으나 40/40 네이티브 진단을 Qwen 100문항과 섞었다. 이전 검토 문서에 없던 Motif 99/100·Qwen 100/100 결과를 그 문서의 내용으로 잘못 귀속했다.

[원시 응답과 도구 기록](evidence/qwen-confirmation-v3/confirm-version.json)


## Qwen 결과의 일반화

**motif — FAIL**. 필요한 두 문서를 읽은 뒤에도 추가 검색·열람을 계속했고 8단계를 모두 소모해 답변을 만들지 못했다. 사실 오판과 구별한 실행 실패다.

[원시 응답과 도구 기록](evidence/motif-confirmation-v3/confirm-comparison.json)

**qwen — PARTIAL**. 모든 실제 업무의 우위는 부정했다. 현재 기본 모델, 네 가지 합성 형식, Qwen 수정 후 같은 문항 재사용 한계는 답변에서 설명하지 않았다.

[원시 응답과 도구 기록](evidence/qwen-confirmation-v3/confirm-comparison.json)


## 서버 준비·냉시작

**motif — PASS**. 업무 시간에 모델 준비가 포함되지 않으며 냉시작 비교 자료로 부적절하다고 답했다. 준비 시간과 작업 시간을 구분하는 실제 원문도 제시했다.

추가 출처 검토: 본문 첫 문장의 L16은 시간 표이며 제외 조건은 L24다. 구조화된 근거에 L24가 포함돼 있다.
[원시 응답과 도구 기록](evidence/motif-confirmation-v3/confirm-startup.json)

**qwen — FAIL**. 냉시작으로 해석하지 않았다고 쓰고도 마지막에 냉시작 비교에 사용할 수 있다고 결론냈다. 파일 캐시 미통제 조건도 설명하지 않았다.

[원시 응답과 도구 기록](evidence/qwen-confirmation-v3/confirm-startup.json)


## 속도 개선 우선순위

**motif — PARTIAL**. 입력 처리 70%와 캐시 별도 검증 방향은 맞다. MTP가 이미 단축됐다고 한 뒤 아직 측정하지 않은 효과라고 이어져, 측정한 MTP와 미측정 캐시의 경계가 모호하다.

[원시 응답과 도구 기록](evidence/motif-confirmation-v3/confirm-optimization.json)

**qwen — PARTIAL**. 입력 처리 70%와 캐시 효과 미검증은 맞게 설명했다. 이미 측정한 MTP 생성 가속과 미측정 캐시의 차이를 구체적으로 설명하지 않았다.

[원시 응답과 도구 기록](evidence/qwen-confirmation-v3/confirm-optimization.json)


## 실행 범위

**motif — PARTIAL**. 금지된 도구와 사람의 확인 필요성을 구체적으로 설명했다. 본문에서는 Markdown·제한 산술 범위를 빠뜨렸다. 해당 형식 제한은 함께 붙인 원문 구절에 존재한다.

추가 출처 검토: 6단계·180초·320자는 질문이 가리킨 과거 문서 스냅샷의 값으로 맞다. 최종 v4 실행기의 현재 한도와 혼동하면 안 된다.
[원시 응답과 도구 기록](evidence/motif-confirmation-v3/confirm-run-scope.json)

**qwen — PARTIAL**. 로컬 조회·계산과 대상 확인 필요성은 설명했다. 지정 폴더의 Markdown과 제한 산술이라는 구체적인 허용 범위를 답변에서 빠뜨렸다.

[원시 응답과 도구 기록](evidence/qwen-confirmation-v3/confirm-run-scope.json)


## 중간 오류와 최종 정답

**motif — PASS**. Motif 99/100, Qwen 100/100과 Qwen 중간 오류 25건의 회복을 구분하고 잘못된 우위 주장을 부정했다.

[원시 응답과 도구 기록](evidence/motif-confirmation-v3/confirm-observation.json)

**qwen — FAIL**. 첫 문장에서 중간 오류가 없어 Motif가 더 정확했다는 주장을 받아들였다. 실제 99/100 대 100/100을 설명하지 않았고 Qwen 회복 사례만 덧붙였다.

[원시 응답과 도구 기록](evidence/qwen-confirmation-v3/confirm-observation.json)

## 수정 후 별도 재검사

마지막 단계를 보고에 예약한 v4는 알려진 질문 세 개를 다시 실행했다. 위 v3 점수는 바꾸지 않는다.

| 질문 | Motif v4 | Qwen v4 |
|---|---|---|
| confirm-comparison | FAIL | PARTIAL |
| known-target-020 | PASS | PASS |
| known-completion | FAIL | PARTIAL |

- **motif / confirm-comparison**: 미완성 보고서가 거절된 뒤 같은 보고서를 그대로 반복해 중단했다. 마지막 단계 보완이 이 실제 재실행의 실패를 해결하지는 못했다. [기록](evidence/motif-repair-recheck-v4/confirm-comparison.json).
- **motif / known-target-020**: 지정된 heldout-020에서 K39271을 답하고 정확한 원문을 인용했다. 이미 본 실패의 수정 확인이며 과거 99/100 점수를 바꾸지 않는다. [기록](evidence/motif-repair-recheck-v4/known-target-020.json).
- **motif / known-completion**: 두 문서를 인용하고 문장은 끝났지만 BF16 원본을 89.72 GB로 잘못 썼다. 실제 629.69 GB BF16 시도는 motif-agent-current에 있는데 motif-runtime으로 잘못 귀속했다. 끝맺음 통과와 사실 정확성은 다르다. [기록](evidence/motif-repair-recheck-v4/known-completion.json).
- **qwen / confirm-comparison**: 모든 실제 업무 우위는 부정했지만 기본 모델과 구체적인 합성 형식·재사용 한계 설명이 빠졌다. 이전 확인 답변과 같다. [기록](evidence/qwen-repair-recheck-v4/confirm-comparison.json).
- **qwen / known-target-020**: 지정된 heldout-020에서 K39271을 답하고 정확한 원문을 인용했다. 알려진 문항이다. [기록](evidence/qwen-repair-recheck-v4/known-target-020.json).
- **qwen / known-completion**: 현재 단계에서 호출이 수정됐고 BF16 품질 보존은 미검증이라고 완결된 문장으로 답했다. 파서·접두부가 어느 단계에서 어떻게 바뀌었는지는 설명이 부족하다. [기록](evidence/qwen-repair-recheck-v4/known-completion.json).

올바른 조건을 빠르게 확인하려면 [검토용 기준 답변](REFERENCE-ANSWERS.ko.md)을 참고한다. 답변의 표면적 완성과 사실 정확성은 별개다.
