# Local input-bound proof audit

Task: `G6-07-INPUT-BOUND-PROOF-TO-FRESH-SUCCESSOR-VALIDATION-V1`.

Result: **INPUT_BOUND_PROOF_NOT_READY**. No exact count or conservative bound has been certified for the frozen request. The limit remains 28,672 input tokens; the certified value is **NONE**. No Provider, readiness, count or paid generation request was sent, and no fresh revision was allocated.

## What was established

The current source freeze `OPENAI_FORMAL_SUCCESSOR_BINDING_20260921_01` matches all 184 members. The archived parent matches 182 members. The entry audit verified the prior closeout seal, state receipts, contract, configuration, policy, component source identities and original test evidence. Production source and the immutable proof registry were not changed.

The active Python environment had OpenAI SDK 1.70.0, tokenizers 0.21.1 and transformers 4.53.1, but no tiktoken. The Python launcher listed this interpreter and the inspected conda environment directory contained no additional environment. This is a bounded environment inspection, not a claim that every file on the computer was searched.

The current public package metadata identified tiktoken 0.14.0. Its Python 3.12 Windows wheel was downloaded into `work/input_bound_proof`, checked against the published SHA-256 and extracted into an isolated directory. The global environment was not changed. The actual installed package was imported with network access denied for the local lookup:

| Frozen model | Actual local lookup | Qualification |
|---|---|---|
| `gpt-6-astra` | KeyError; no exact entry and no matching prefix | No model encoding established |
| `gpt-5.6-sol` | `o200k_base` through generic `gpt-5` prefix; no exact entry | Prefix result alone does not establish the required exact-model identity |

An intentionally nonexistent local control name beginning with `gpt-5` produced the same mapping. No control model was submitted anywhere. The tokenizer's own mapping implementation documents this prefix behavior. The downloaded main-branch map and wheel map have different byte hashes but equal text after newline normalization; both lack an explicit entry for either frozen model. No adjacent-model encoding was installed in the production proof registry.

The [official token-counting guide](https://developers.openai.com/api/docs/guides/token-counting) separates plain-text tokenization from model input formatting, including message roles and boundaries. The inspected guide and [PRIMARY](https://developers.openai.com/api/docs/models/gpt-6-astra) / [SECONDARY](https://developers.openai.com/api/docs/models/gpt-5.6-sol) model pages provide no audited local framing template or constant that proves the requested bound. The current SDK's documented count implementation performs a remote POST; it is not a local encoding function. It was inspected as source and never invoked.

Public source URLs, retrieval timestamps and exact content hashes are preserved in `PUBLIC_SOURCE_RECEIPTS.json`; wheel identity and actual lookup results are in `LOCAL_TOKENIZER_AUDIT.json`. The inspection supports evidence insufficiency for this exact contract. It does not establish that an offline certificate can never exist.

## Why the conservative alternatives do not close the proof

For a tokenizer whose ordinary tokens partition the original UTF-8 byte string into nonempty pieces without expansion or extra tokens, the content-only inequality is:

`number of content tokens <= number of UTF-8 content bytes`.

This follows because each nonempty token consumes at least one byte, and merging adjacent pieces cannot increase the number of pieces. It is a conditional mathematical statement about that algorithm. Applying it to either frozen server model still requires evidence that the actual tokenizer and preprocessing satisfy those premises. It does not establish any message-boundary or implicit-control overhead.

The frozen local serializer independently establishes that canonical JSON message bytes do not exceed 24,576. JSON escaping and structural syntax do not give the remote message representation. A complete conservative proof would need an independently justified rule such as:

`U(messages, controls) = text_bound(messages) + role_and_boundary_bound(messages) + implicit_control_bound(controls)`

and a proof that actual input tokens are at most U for **every** permitted input, followed by a deterministic check that U is at most 28,672. No finite, model-bound role/boundary/implicit-control rule was established in the inspected evidence. The extra 4,096 tokens are an allowance, not evidence for that rule. Tokenizing the JSON wire body would count a different representation and does not fix the missing premise.

Message count is not fixed by the array format. Even empty messages incur structure; the exact host-only minimum-size and maximum-count calculation is recorded in `PROOF_OBLIGATIONS.json`. Many-message, maximum-byte and overflow checks pass, but they cannot reveal the server's hidden framing cost. A context-window ceiling is also not the required per-request bound under 28,672.

No method A (exact tokenizer), B (tokenizer plus proven framing), or C (complete conservative envelope) therefore meets all acceptance conditions. Samples, fuzzing, prior usage and model capacity do not fill these proof gaps. A certificate was not manufactured, and a mock calculator was not promoted into production.

## Coverage and verification

42 new offline evidence/rejection checks passed. They include both exact model lookups, a prefix counterexample, the immutable empty registry, forged proof declarations, byte overflow, many empty messages, invalid roles, multimodal rejection, and the actual preflight prerequisite gate. For both frozen model IDs, neutral fixtures exercise system content, user content, assistant history, multiple turns, Chinese, English, CJK punctuation, emoji, ASCII, combining marks, line breaks, Markdown, JSON-like text, long URLs, code blocks, unusual whitespace, control characters, noncharacters, special-token spellings and empty content. Lone surrogates are rejected at UTF-8 serialization rather than normalized. The valid fixtures are preserved exactly and blocked at the missing-proof gate before transport.

The original 40 binding tests also passed in a fresh sequential run. Their authored proof fixtures remain test doubles. Network access was denied in test processes and inherited Python subprocesses. No real model quality was assessed.

The 821 component tests and the legacy result were not rerun because production source did not change. Their original receipt, log hashes and component source identities were reverified. Legacy remains **449 compatible passes + 1 expected historical source-identity sentinel + 0 unexpected failures**; its original exit code 1 and raw failed status are preserved. It is not 450/450 PASS.

## Execution and recovery

The actual formal entry returned NOT_READY at its prerequisite gate, with `formal_preflight_executed=false`. The complete ZERO_PROVIDER_FORMAL_BINDING_PREFLIGHT was not run because proof readiness is a prerequisite. No diagnostic or historical READY was inherited.

The historical R16 failure, permanent quarantine, open Major and seven stored UNKNOWN records remain unchanged. The successor is VALIDATION_PENDING: 0/44 submitted, 0/44 provider-valid, 0/176 reviewed, 176 unreviewed. Both validation gates are incomplete. G6-08 and G6-09 remain locked; all current build/product/activation completion flags remain false.

One stale nested `G6-07.current_source_freeze_id` pointer was found in the task graph. The top-level source and all actual source bytes were correct. Reconciliation preserves the old R16 validation identity, labels the historical gate source, and sets the current source pointer to the verified 184-member freeze. This is a metadata correction, not a new source freeze or a change to a historical verdict.

The next useful input is new auditable evidence for both exact model encodings and the frozen Responses framing, or a mathematically complete alternative envelope. Without such evidence, repeating the same local audit or installing the same package will not advance readiness. The existing budget authorization remains valid; it is not the blocker. The remote count API remains prohibited by this task. Once a sufficient local proof exists, perform only necessary integration, relevant regression and a new source freeze if source changes, then the complete zero-provider preflight. Only actual READY permits the already-authorized sole fresh validation.
