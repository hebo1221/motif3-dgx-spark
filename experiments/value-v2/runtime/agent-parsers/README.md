# Optional native-tool parser profiles

The measured document runs used these profiles with thinking disabled and
single native tool calls. They are scoped experimental handlers, not changes
to every model's default template.

Start from the pinned public base
`cc3f13b3f172978d7b3c215780d4cc98bb0e1c80`. The earlier Motif tokenizer and
MTP patches in the repository root are needed to reproduce the corresponding
Motif runtime configuration. In that separate checkout, apply:

1. `motif3-agent-parser-v1.patch`;
2. `qwen3-agent-parser-v1.patch` if using the optional Qwen profile.

The profiles are selected by the templates in `../../client/`:
`motif3-agent.jinja` and `qwen3-agent.jinja`. Set `--jinja`, the appropriate
`--chat-template-file`, and `--chat-template-kwargs '{"enable_thinking":false}'`.

The public Qwen patch removes one unrelated thinking-flag hunk from the
historical combined diff. Its Qwen function and registration match the measured
source exactly. Patch application and that comparison were checked against the
public base during publication. No fresh full common-library or runtime build
was performed in the publication step. The historical measured runtime reused
existing objects and rebuilt its common chat library separately.

The required/auto/none tool-choice profile is bounded. Named-tool choice,
assistant prefill, and simultaneous active tools with a response-format schema
are not qualified. A valid native call is not a guarantee that its answer is
correct. Do not combine the small Q8 reference patch with the larger MTP patch
as part of these parser instructions.
