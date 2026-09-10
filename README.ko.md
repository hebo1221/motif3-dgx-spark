# Motif-3. Spark 한 대.

3,147억 파라미터를 128 GB DGX Spark 한 대에.

[모델 받기](https://huggingface.co/jhkim55/Motif-3-Direct-IQ2-XXS-DGX-Spark) · [실행하기](docs/GUIDE.ko.md#빠른-시작) · [English](README.md)

| 모델 파일 | 생성 속도 | 장비 |
|---|---|---|
| **83.56 GiB** | **16.49 tok/s** | **DGX Spark 1대** |

혼합 IQ2_XXS. 모든 층을 GPU에 올렸다. 속도는 토크나이저 패치 이전
공개 빌드의 tg128 5회 평균이다. [측정 기록 →](docs/RESULTS.md)

공식 BF16에서 직접 변환했다. 토크나이저 수정, 고정 런타임, 실험 기록을
함께 남겼다. 원본 대비 품질 유지 기준은 통과하지 못한 실험용 모델이다.

---

[만든 과정](docs/CASE_STUDY.ko.md) · [실제 답변](docs/RECORDED_DEMO.md) · [최종 회고](docs/FINAL_REPORT.ko.md)

마지막 SSD 실험은 전문가 Q4로 1,024토큰 생성 평균 **2.81 tok/s**를 기록했다.
원본과의 품질 동등성은 미검증이다. [코드와 결과 →](experiments/ssd-offload/README.md)

연구는 마쳤다. 코드와 모델, 결과는 공개로 남긴다.

<a id="빠른-시작"></a>
[설치·상세 안내](docs/GUIDE.ko.md#빠른-시작) · [프로젝트 상태](docs/PROJECT_STATUS.md) · [MIT](LICENSE) · [크레딧](NOTICE.md)
