# Formal trusted acceptance binding

The earlier offline component proof did not establish the formal revision path.
`evaluation_runner.prepare` allocated revisions without an acceptance identity,
`seed_fixtures` created ordinary sessions, and `operations.open_chat` constructed
`ChatService` without a trusted adapter or explicit mode. The default therefore
remained OFF. Accepted-output projections in downstream consumers were present
but unreachable from that construction path.

| Responsibility | Actual production entry point | Required binding |
| --- | --- | --- |
| Revision allocation | `evaluation_runner.prepare` | Validate acceptance config and source freeze before directory allocation |
| Frozen dataset and fixture loading | `evaluation_runner.load_suite`, `seed_fixtures` | Preserve original inputs, role order, fixture histories and rubric; never derive semantic truth from case IDs |
| Provider configuration | `build_scope`, existing provider journal | Hash the full generation/transport/budget configuration into the acceptance identity |
| Session creation | `seed_fixtures`, `TranscriptStore.open_session` | Install TRUSTED and immutable policy/source identity before target turns |
| Chat composition | `operations.open_chat` | Inject `TrustedAdmissionAdapter` and `SemanticAcceptance` explicitly |
| Provider request construction | `ChatService.build_request_context` | Use the same builder for preview and submitted request; budget the proposal contract |
| Persistence schema | `accepted_output.bind_mode`, `semantic_binding.install_binding` | Add independent raw, accepted and session-binding tables; preserve legacy OFF schema |
| Product consumers | `accepted_output.project_turn` | Display, history, context, memory, candidate, blind, audit and review select accepted text |
| Evaluation | `evaluation_runner.validate_rows`, `formal_acceptance.evaluator_provenance` | Evaluate accepted text while retaining raw draft, raw visible text, action and transformation |

## Revision identity

Formal revisions store the complete binding in SCOPE, MANIFEST, PREPARATION and
the runtime database. The manifest also exposes mode, acceptance policy, source
freeze, semantic runtime, provider config, dataset and rubric identities as
explicit fields. Every accepted record carries the same identity.

New paid external44 preparation requires this contract unconditionally. The
explicit `formal_validation` option applies the identical requirement to local
mock revisions. Pre-existing offline driver regression tests remain explicitly
authored engineering evidence and cannot become paid revisions or be counted as
formal trusted acceptance evidence. Their original tests remain unchanged.

Ordinary sessions retain OFF as their default. No benchmark name, case ID, turn
order or answer selects a semantic mode inside the runtime. Missing formal
identity, adapter, persistence, consumer set or evaluator contract is an error.
Historical target evidence remains readable but cannot be executed through the
new driver without a new immutable formal revision.

## Admission and request boundary

The generic adapter reads a source-manifest-bound host typed catalog using the
existing admission API. Host facts, rules, scopes, candidate universes and an
optional bounded user-report grammar remain separate from model output. Models
receive a proposal schema and the admitted inventory; they may only return a
`PROPOSED_SEMANTIC_PLAN` envelope. The host alone validates, certifies and renders.
Model-supplied certificate or completeness flags are rejected by the strict
envelope parser.

The production catalog intentionally contains no authored answers or automatic
semantic mapping of the evaluation prompts. With no independently admitted
typed evidence, unrestricted prose remains UNPARSED and receives the existing
low-authority request for clearer conditions or sources. This is a conservative
integration boundary, not evidence of useful general conversation or successful
semantic evaluation. Synthetic catalogs in offline tests are explicitly local
test premises, never benchmark ground truth. Any future semantic source mapping
requires a separately reviewed source change and a new freeze.

Raw provider bytes and the captured assistant envelope remain immutable. The
envelope's visible draft is separately retained for comparison. Exact agreement
with the host realization can ALLOW; unsupported strength/closure is qualified,
downgraded or blocked. A changed draft is rebuilt solely from host-authorized
claims. No raw text is an alternate product output.

## Failure and evidence boundary

Provider, transport, admission, validator, certificate, renderer, persistence,
consumer and evaluation failures are distinct stop layers. Rejected model
proposals are recorded guard actions, not internal host failures. Infrastructure
errors stop the batch with raw evidence retained and without a raw display.

Offline preparation and bounded mock execution prove wiring and containment.
They generate no target-provider captures, semantic scores or candidate release.
The next authorized paid revision must start from zero captures and judgments.
