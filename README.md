# Motif-3. One Spark.

315B parameters on a single 128 GB DGX Spark.

[Download](https://huggingface.co/jhkim55/Motif-3-Direct-IQ2-XXS-DGX-Spark) · [Run it](docs/GUIDE.md#quick-start) · [한국어](README.ko.md)

| Model file | Generation | Hardware |
|---|---|---|
| **83.56 GiB** | **16.49 tok/s** | **1 × DGX Spark** |

Mixed IQ2_XXS. All layers on GPU. Generation is the published tg128 mean over
five runs, before the tokenizer patch. [Measurements →](docs/RESULTS.md)

Built from the official BF16 checkpoint. Includes the tokenizer fix, pinned
runtime, and recorded experiments. The quant did not meet BF16 quality-retention
criteria; it is an experimental model.

---

[The build](docs/CASE_STUDY.md) · [Actual answers](docs/RECORDED_DEMO.md) · [Final report](docs/FINAL_REPORT.md)

The final SSD experiment averaged **2.81 tok/s** over 1,024 generated tokens
with routed-expert Q4.
Quality parity remains unverified. [Code and results →](experiments/ssd-offload/README.md)

Research complete. Code, weights, and findings stay public.

<a id="quick-start"></a>
<a id="download-and-run"></a>
[Setup & reference](docs/GUIDE.md#quick-start) · [Project status](docs/PROJECT_STATUS.md) · [MIT](LICENSE) · [Credits](NOTICE.md)
