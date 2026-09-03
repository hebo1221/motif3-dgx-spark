# What did not work

The direct IQ2 model remained the deployment default because each attempted
repair failed at least one task or system gate. Publishing these failures is
more useful than presenting the largest artifact as an improvement.

## 1. GEMQ-style per-expert mixed-precision overlay

An exact 14.28 GB compact expert overlay used teacher-KL allocation under a
104 GB total deployment ceiling. It also required a runtime fix for duplicate
local expert IDs in CUDA expert routing.

Outcome versus direct IQ2:

- Korean: -1 / 300;
- general: -1 / 180;
- raw tool: -4 / 30;
- schema-gated tool: -4 / 30;
- 18-20% slower across the four measured benchmark shapes;
- +13,621 MiB peak GPU/UMA allocation.

The representation was too expensive in its current kernel implementation and
generic KL selection did not protect tool-control decisions.

## 2. Causal late-block Q8 restoration

A 12.84 GB block-40 plus block-52 Q8 overlay was selected on disjoint teacher
slices.

Outcome:

- Korean: -1 / 300;
- general: +1 / 180;
- raw tool: -3 / 30;
- schema-gated tool: -4 / 30;
- 11.82% slower tg128;
- +9,270 MiB peak allocation.

Restoring selected weights did not reliably restore the error cancellation
needed by discrete tool decisions.

## 3. Terminal-KL rank-4 correction

A 16.56 MB terminal logit-curvature adapter was the most promising direction:
nearly unchanged prefill cost and only +22 MiB peak allocation.

Outcome:

- Korean: +3 / 300, exact paired p=0.375;
- general: unchanged;
- raw tool: -4 / 30;
- schema-gated tool: -6 / 30, exact paired p=0.03125;
- 5.60% slower tg128.

The Korean gain was not statistically conclusive, while the tool regression
was detectable even in the small diagnostic set. It is therefore not released
as a universal improvement.

## 4. Tool-call policy repair

A later source-disjoint 100-case policy test showed that target-tool proposal
was often correct, but call/no-call rejection and required-slot state were not.
The candidate scored 45/100 on the frozen source-policy metric versus 47/100
for the control and was retired.

The main lesson is architectural: tool applicability, typed argument
extraction, and null-tool rejection should be separate decisions. A parser can
repair malformed JSON but cannot infer that no declared tool applies.

## General lesson

Mean teacher KL is a poor sole objective for tool use. Tool behavior hinges on
a small set of high-leverage tokens: the tool opener, function name, JSON
punctuation, arguments, stop token, and the no-call branch. Future work should
constrain those margins directly and include measured decode and memory costs
inside the optimization objective.
