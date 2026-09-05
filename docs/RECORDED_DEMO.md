# Two recorded answers you can inspect without a GPU

[Case study](CASE_STUDY.md) · [한국어 회고](CASE_STUDY.ko.md) · [All recorded examples](../experiments/value-v2/examples/README.ko.md)

These are existing model answers with their source passages. No server, model
download, or account is needed to read them. Excerpts remain in the original
Korean; the English explanations below are editorial commentary.

**모델을 내려받지 않고 실제 답변과 원문을 볼 수 있습니다.** 유용한 구분을 한
답변과, 근거를 인용하고도 사실을 틀린 답변을 함께 남겼습니다. 새 평가나 실시간
시연이 아니며, 아래 설명은 모델 답변과 구분한 검토 의견입니다.

## 1. A useful distinction, with an imperfect citation

The task asked what a recorded token-agreement result establishes. Motif
correctly separated execution agreement inside one runtime from quality
preservation between BF16 and IQ2.

> 따라서 5,560개 토큰 일치는 동일 런타임 내 실행 재현성만 확인한 것이며, BF16 원본과 IQ2의 품질 일치를 의미하지 않습니다.

[Read the complete answer and its source passages](../experiments/value-v2/examples/motif-parity.md).
The conclusion is useful, but one prose line reference is inaccurate. The
structured evidence includes the relevant passages, so the answer still needs
review. The 5,560-token count belongs to the later integrated-runtime record
quoted in this example; it is separate from the v1.2 MTP study's 5,120 tokens.

**검토:** 가속 전후의 출력 일치와 원본 품질 보존을 구분했다. 본문에 잘못된 행
참조도 있으므로 답변 전체가 완벽하다는 뜻은 아니다.

## 2. A complete answer that contradicts its own evidence

Another task asked about native tool calls and BF16 quality evidence. This
excerpt contains the error:

> 원본 BF16 품질 보존은 motif-runtime에서 89.72 GB BF16 원본의 제한 검사 결과 300초 안에 서버가 준비되지 않았고 0건의 추론 요청만 수행돼, 이번 작업에서 IQ2가 원본 품질을 보존한다거나 개선했다고 말할 수 없다고 결론짓는다.

The source passage attached to that same answer begins:

> 기존 629.69 GB BF16 원본을 mmap과 CPU MoE offload로 시작하는 제한 검사를 수행했다.

| Claim to inspect | What the recorded source supports |
|---|---|
| “89.72 GB BF16” | 89.72 GB describes IQ2; the cited report describes the BF16 reference as 629.69 GB |
| The startup observation comes from `motif-runtime` | It appears in `motif-agent-current`, lines 50–52 |
| A completed report with authentic quotations is correct | The answer above contains both a size error and a source-attribution error |

[Read the complete failed answer and original passages](../experiments/value-v2/examples/motif-complete-but-wrong.md).
This answer remains a failure. The passages describe that historical bounded
startup test; they do not establish that BF16 inference is impossible.

**검토:** 답변은 BF16과 IQ2의 크기를 혼동했고 문서 출처도 잘못 붙였다. 문장이
완결되고 인용문이 실제로 존재한다는 사실만으로 승인할 수 없는 사례다.

## Verify the records locally

With Git and Python 3, starting outside an existing checkout:

```bash
git clone --depth 1 https://github.com/hebo1221/motif3-dgx-spark.git
cd motif3-dgx-spark
python3 experiments/value-v2/verify_public.py
```

The last command uses the Python standard library and runs offline. The
published evidence bundle returns:

```json
{"status": "pass", "imported_files_verified": 258, "public_fixture_files_verified": 110, "recorded_reports_checked": 29, "redacted_source_spans_checked": 56, "new_model_requests": 0}
```

This verifies published file hashes, document indexes, recorded source spans,
and review-to-response bindings. It does not regenerate an answer or certify
its meaning. The model's mistakes remain visible even when this check passes.
See [publication provenance](../experiments/value-v2/PUBLICATION.md) for the
distinction between original records and redacted public copies.

**검증 범위:** 파일과 원문 연결을 확인하는 검사다. 정답 채점이나 새 모델 추론이
아니다. 답변의 오류는 검증 통과 후에도 그대로 남는다.

For implementation, see the [bounded document client](../experiments/value-v2/USAGE.md).
For a CUDA experiment that needs no model weights, see the
[Q8 numerical probe](../experiments/value-v2/runtime/README.md); that probe
still requires its documented GPU build environment.
