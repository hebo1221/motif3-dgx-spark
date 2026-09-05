# Project status

**Research complete; maintenance only. Updated 2026-09-06.**

This project is maintained as a reproducible systems engineering case study
and an experimental local-inference artifact. The active scope is documentation,
reproduction fixes, evidence corrections, and independent results.

## What is complete

- A downloadable 83.56 GiB mixed-precision Motif-3 core, a pinned runtime,
  tokenizer patch, model checksums, and reproduction instructions.
- Recorded Spark speed and memory measurements with their exact scopes.
- Experimental MTP source and evidence, plus a model-free Q8 numerical probe.
- A bounded document-agent client and inspectable useful and failed answers.
- An [English case study](CASE_STUDY.md), [Korean case study](CASE_STUDY.ko.md),
  and [offline evidence tour](RECORDED_DEMO.md).

The BF16 quality-retention gates failed. General-purpose autonomous-agent
readiness is not established. Closing this project does not resolve every
research question or rank the parent model against alternatives; it fixes the
scope of what this project has demonstrated.

## What would justify more work

| Trigger | Bounded response |
|---|---|
| A reproducible defect in the documented setup | Fix the smallest cause and verify the reported reproduction |
| An incorrect claim or broken evidence link | Correct the claim and preserve the original measurement |
| An independent run on a Spark or other hardware | Add a separately labeled result with exact settings and raw repetitions |
| A real user task for which a specific change could help | Define a baseline, task-success measure, time/memory budget, and stopping criterion before one scoped experiment |

An untested repair idea, a small change to an internal score, or a desire for
another release is not enough to reopen broad research. There is no scheduled
training campaign, general agent roadmap, or continuous benchmark campaign.
The published model bytes and historical experiment bundles remain versioned.

For a defect, provide a minimal reproduction in
[Issues](https://github.com/hebo1221/motif3-dgx-spark/issues).
For independent measurements, use the
[benchmark form](https://github.com/hebo1221/motif3-dgx-spark/issues/new?template=benchmark.yml).
Maintenance is best effort; this is not a hosted service or a support SLA.

## 한국어 운영 기준

목표는 기술적으로 흥미롭고 일부 실험에 쓸 수 있는 공개 작업물을 남기는 것이다.
모델의 보편적인 성능 개선을 계속 약속하지 않는다. 구현한 내용과 측정한 결과를
빠르게 이해하고 직접 확인할 수 있도록 정리한 상태에서 탐색 연구를 마무리한다.

추가 작업은 재현 오류, 근거 정정, 독립 재현, 구체적인 사용자 과제가 생겼을 때
범위를 정해 진행한다. 새 실험이 필요하면 비교 대상·성공 조건·시간과 메모리
한도·중단 기준을 먼저 적는다. 기존 실패를 다른 이름의 성공으로 바꾸거나,
다음 실험의 가능성만으로 작업을 이어가지 않는다.
