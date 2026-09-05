# 원문을 기준으로 답변 검토하기

평가 후 assistant가 작성한 검토 가이드다. 모델의 실제 답변을 바꾸거나 점수를 다시 매기는 자료가 아니다. 원문 위치는 이 패키지의 고정 문서 스냅샷에 해당한다. 문서 해시는 `workflows/source-provenance.json`과 `workflows/project-documents/document-index.json`에 있다.

## 공개 문구

“원본 품질을 유지하는 범용 코딩 에이전트가 완성됐다”는 주장은 지지되지 않는다. 근거에 맞는 문구는 “DGX Spark에서 공개 Motif IQ2의 통합 추론과 제한된 로컬 문서 보조를 검증했다. 사람이 원문을 확인하는 파일럿 단계이며, BF16 원본 품질 보존과 범용 코딩 능력은 미검증이다.”

근거: [현재 보고서](workflows/project-documents/motif-agent-current.md) 7·50–52행, [통합 보고서](workflows/project-documents/motif-runtime.md) 5–7·60·73–77행.

## 5,560개 토큰 일치

같은 통합 IQ2 런타임에서 MTP를 껐을 때·켰을 때·다시 끈 복구 실행을 비교한 결과다. Motif와 Qwen의 비교도, BF16과 IQ2의 비교도 아니다. 따라서 BF16 원본의 품질 보존을 입증하지 않는다.

근거: [통합 보고서](workflows/project-documents/motif-runtime.md) 5·53–60행, [현재 보고서](workflows/project-documents/motif-agent-current.md) 50–52행.

## 과거 도구 호출과 현재 40/40

이후 생성 접두부·required 호출 문법·도구 파서를 보완했고, 다른 시험 조건에서 네이티브 호출 형식을 확인했다. 이전 raw tool 진단과 현재의 40/40은 시험과 실행 구성이 다르므로 가중치 지능이 향상됐다는 직접 증거가 아니다.

근거: [과거 검토](workflows/project-documents/motif-historical-review.md) 18–24행, [현재 보고서](workflows/project-documents/motif-agent-current.md) 38–42행.

## Qwen의 100문항 결과

확인한 단순 문서 보조에서는 더 짧은 시간과 작은 파일을 근거로 Qwen을 기본값으로 둘 수 있다. 다만 100문항은 네 가지 합성 형식의 25개 변형씩이며 일반 업무 전체를 대표하지 않는다. Qwen은 수정 후 같은 문항을 재사용했으므로 처음 보는 독립 시험 100점으로 발표해서는 안 된다.

근거: [현재 보고서](workflows/project-documents/motif-agent-current.md) 13–26·56행, [평가 방법](workflows/project-documents/motif-evaluation-method.md) 66–73행 및 Qwen 비교 제한 설명.

## 33.4분과 10.1분

서버가 준비된 뒤 실제 문서 업무에 걸린 시간의 합계이며 모델 준비 시간은 포함하지 않는다. 운영체제 파일 캐시를 통제한 냉시작 실험도 아니므로 냉시작 성능 비교로 사용할 수 없다.

근거: [현재 보고서](workflows/project-documents/motif-agent-current.md) 16·24행, [평가 방법](workflows/project-documents/motif-evaluation-method.md) 113–119행.

## 속도 개선 우선순위

기존 Motif 100문항에서 서버 처리 시간의 약 70%가 입력 처리였다. 반복 문맥 재사용을 먼저 조사할 이유가 있지만 캐시의 실제 이득과 정확성은 따로 측정해야 한다. MTP는 이미 지정된 생성 시험에서 시간 단축을 측정했으며, 그 결과를 아직 측정하지 않은 캐시 효과로 옮겨 쓰면 안 된다.

근거: [현재 보고서](workflows/project-documents/motif-agent-current.md) 58행, [통합 보고서](workflows/project-documents/motif-runtime.md) 19–37행. 처리량 14.63→21.99 tok/s의 증가율은 약 50.3%이며 일반 요청 대기시간 감소율과 다르다.

## 문서 실행 범위

지정 폴더 바로 아래의 Markdown 파일을 읽고 제한된 산술식만 계산한다. 모델에는 파일 수정·명령 실행·외부 웹·메시지 발송 도구가 없다. 실제 원문 인용이 있어도 질문 대상, 문서 시점, 계산·해석, 답변 완성도를 사람이 확인해야 한다.

근거: [이전 사용법](workflows/project-documents/motif-client-usage.md) 51–62행, [현재 보고서 스냅샷](workflows/project-documents/motif-agent-current.md) 30–46행. 이 스냅샷의 옛 한도와 최종 v4의 한도는 다르며, 실제 실행에는 [이번 사용법](USAGE.ko.md)을 사용한다.

## 중간 오류와 최종 정답

해당 고정 표본은 Motif 99/100, Qwen 100/100이었다. Qwen의 중간 읽기 오류 25건은 모두 회복 후 정답으로 끝났다. Motif의 중간 도구 오류가 없었다는 사실만으로 최종 정확도가 더 높았다고 말할 수 없다.

근거: [현재 보고서](workflows/project-documents/motif-agent-current.md) 13–22·30–32행, [평가 방법](workflows/project-documents/motif-evaluation-method.md) 101–105행.
