# What these checks establish

This is a private, reproducible readiness experiment for a bounded, read-only
document agent on one DGX Spark. It is not a model leaderboard or a production
certification. Results are in `evidence/validation-summary.json` and the accompanying
Korean report.

## Candidate and controls

- Target: the released direct IQ2_XXS Motif-3 artifact, 89,720,474,560 bytes,
  SHA-256 `9d6f7aee57f0271223f51d69c63d8576a259809e9f05e2ac596512e940c80c5a`.
- Draft: the existing linked BF16 MTP sidecar, 512,363,040 bytes,
  SHA-256 `d813251f1b7e8158399352af6e44c92df2445cd807fda1a869d2247279806f81`.
- Base source: llama.cpp `cc3f13b3f172978d7b3c215780d4cc98bb0e1c80`, with the
  existing final tokenizer and Motif MTP integration patches.
- This experiment changes only the common chat library. Existing tensor,
  tokenizer, CUDA, and MTP arithmetic components are copied unchanged.
- The Motif handler is selected only by the explicit
  `motif3_agent_profile_v1` marker in `motif3-agent.jinja`.
- Live agent configuration: one slot; GPU layers 99; FA on; f16 KV;
  context 22,016; batch 2,048; ubatch 512; 20 threads; thinking disabled;
  temperature 0; top-k 1; seed 42; prompt cache disabled; at most 192 generated
  tokens per model turn. The selected Motif arm uses MTP draft length 1.

The practical alternative is official `Qwen/Qwen3-8B-GGUF`, Q8_0,
revision `7c41481f57cb95916b40956ab2f0b139b296d974`.
Its 8,709,518,112-byte file was checked against the Hub LFS SHA-256
`408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6`.
It uses the same host, agent, cases, and request limits with its own chat
template and no Motif sidecar. The initial run used its unmodified embedded
template. Two development tasks produced unstructured text and hit the output
limit despite required tool choice. The automatically following comparison
was stopped and preserved. A separate opt-in Qwen handler was then built using
the same bounded native-call approach as Motif, with the official template's
message rendering preserved. The repair was based on those development
trajectories and model-vocabulary parser tests, not factual held-out answers.
The repaired configuration is evaluated on the same fixed case set for paired
comparison. Because an earlier partial run exists, its confirmation score is
not described as pristine first exposure to that set. The original Motif live
runtime, client, and score are unchanged. This compares deployed configurations;
it does not isolate quantization, parameter count, or the underlying training.

## Separation of development and evaluation

`fixtures/freeze.json` fixes all documents and labels before inference. The
eight development tasks could be used to repair implementation errors.
`pre-heldout-source-freeze.json` pins the final agent, runner, template, patch,
and fixture manifests before the 100-case held-out run. Each final model
configuration gets one pass over those same 100 cases. Results must not be used
to tune this candidate and then reported as a fresh held-out score.

The live paired evaluation uses client SHA-256
`37f01fae7fb9f010bed86bd02f5d9d23f6646f9f0236180e6a155ba4fb7c8dd8`,
preserved with its runner and fixtures in `evaluation-source/`.
A separate static review found that malformed arithmetic such as `1 +` raised
an uncaught Python `SyntaxError`. The delivered client converts this into an
explicit calculator error; its SHA-256 is
`3e7ac1ca52c5a077b6cfb9c0afc3544d7f7d3bb25d0e99422e3350703176d908`.
This error-path change was developed without held-out answer feedback, and the
running evaluation source was not edited. Its verification is recorded
separately: malformed-expression tests, offline replay of recorded trajectories,
and the final one-shot smoke. Replay checks code behavior using existing model
responses; it is not an additional live accuracy or timing measurement. Do not
attribute the earlier full live run to a different client hash.

The 100 cases are **four task forms with 25 synthetic variations each**:
find a code; calculate a total; recognize a missing date; retrieve two facts.
They have different facts from the development cases, but do not test 100
different workflows. A high score supports those specific operations only.
The initial 90/100 target is an internal pilot gate, not an estimate of success
on real customer work. Do not compute a population confidence interval by
treating these related variants as independent, representative user requests.

`fixtures/additional-freeze.json` separately fixes three adversarial documents
and two tasks over a real project report. These five checks are not included in
the 100. The three adversarial cases cover an embedded instruction, literal chat
role markers, and a forged tool result; they do not establish general prompt
injection resistance.

## Scoring

The 40 native API diagnostics comprise eight variations of five forms:
required weather calls, automatic calculator calls, choice between two tools,
automatic mode with no tool, and copying a mock tool result into schema JSON.
They check exact tool name and parsed arguments, or the expected text/JSON.
The mock weather tool is not a real weather service.

Agent scoring is deterministic and external to the model: expected report
status, required answer strings, expected document citation, and, for arithmetic,
an actually executed calculator result. The missing-date tasks must read the
relevant document and return `insufficient_evidence`. Exact result values are
not supplied as enums to constrain the model into the correct factual answer.

`answer_produced` is a protocol/provenance state. It means the agent produced
a complete report with permitted citations, not that the report is factually
correct. The evaluator's `score.pass` is a separate field. The report counts
incorrect factual reports and explicit execution failures separately.
String-based checks cannot rule out every contradiction or irrelevant extra
claim; representative answers and all failed cases should be inspected.

One Motif case illustrates this distinction: `heldout-020` asked about project
020, but the model searched for a broad phrase, read project 002, and returned
that project's code. The tools ran and the citation was real, but it answered
the wrong question. The frozen score is 99/100, with one incorrect answer.
The failing case has not been repaired and rerun as a new held-out success.
Task-to-document subject matching is a remaining pilot requirement.

The client rejects truncated or multiple calls before executing a tool. It also
rejects unknown tools, extra/duplicate JSON fields, and unread citations.
Tool receipts record actual execution and read-document hashes. These controls
provide an audit trail, not proof that every generated sentence is true.

## Timing

Task wall time starts immediately before the agent loop and includes actual
search, read, calculator, and local HTTP work. Model startup is reported
separately. The task p50 and p95 are descriptive quantiles of this fixed set,
not service-level estimates. Timings are sequential, on one host and one slot,
with no concurrent model server.

MTP-off and MTP-on development runs are small exploratory comparisons. Earlier
development used a slightly older client revision. Native tool call IDs are
generated by the server and retained in subsequent messages, so multi-turn
prompt bytes can differ between runs. Do not describe these agent runs as an
exact token-level parity test. The previous integration's token comparison
remains a separate experiment under its recorded configuration.

## Preserved failures and remaining gaps

- The original generic parser passed 17/23 model-vocabulary checks. The opt-in
  candidate passed those 23 plus one full agent-schema initialization check.
- The first live agent development run failed all eight tasks before inference:
  a report field allowing 2,000 characters exceeded this grammar engine's
  repetition-complexity limit. The field was reduced to 320 characters using
  only development feedback. The failed run is retained.
- A BF16 reference canary used the existing 629,689,477,760-byte original,
  mmap and CPU MoE offload, with a 300-second startup limit. It did not reach
  readiness, made zero inference requests, and its owned process was stopped.
  This establishes only that the bounded attempt did not start in time. It is
  not a BF16 quality score, an OOM diagnosis, or proof that longer offloading
  could never work.
- Therefore IQ2 quality retention against the original precision remains
  unmeasured here. Qwen is not a substitute for that precision reference.
- General coding, long conversations, concurrency, external actions, and
  production uptime remain outside this experiment. Earlier repetition issues
  on unconstrained code generation are not resolved by this parser patch.

## Rebuild scope

The measured runtime is an isolated overlay: recompile `common/chat.cpp` with
the existing CMake flags and relink `libllama-common`, reusing the existing
verified build's other objects. The original runtime is left intact.
`build_overlay.py`, the exact modified `chat.cpp`, the patch, compile/link receipt,
and linked-library hashes document that operation. A fresh full CMake build of
this new patch was not performed. Set `LD_LIBRARY_PATH` to the candidate `bin`
directory so the copied server's original RPATH does not select old libraries.
