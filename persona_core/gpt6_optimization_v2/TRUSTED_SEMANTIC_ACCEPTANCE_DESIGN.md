# Trusted semantic acceptance: bounded executable vertical slice

The host admits a typed inventory, checks a proposed semantic plan, issues
claim/exclusion/closure certificates, renders a controlled answer, and persists
an independent accepted-output record. The same accepted record supplies display,
history, subsequent context, observed memory, evaluation, candidate inputs and
blind-review dialogues. Provider receipts remain byte-preserved audit evidence.

This implementation verifies a bounded language, not unrestricted natural-language
entailment. Free conversation remains UNPARSED unless a host-owned adapter supplies
independently trusted typed facts. It must not be described as a general Chinese
semantic parser or evidence that future model responses pass semantic review.

## Admission and proposal boundary

`TrustedAdmission` is an ordinary host configuration API, subject to the same
trusted Python/OS boundary as the existing session and event-admission APIs.
It accepts actual typed program observations, schema-bound state, independently
reviewed source mappings, and explicit finite rules. Provider dictionaries cannot
be deserialized into a trusted inventory. A digest binds a source/version; it is
not by itself a proof that a passage entails an arbitrary interpretation.

The deliberately small user-statement grammar recognizes only exact
`我计划执行「task」。` and `我已完成「task」。` forms against an existing, unambiguous
host task vocabulary. These create attributed user reports, never world-verified
external completion. Other input is retained as UNPARSED without fact authority.
The root adapter does not receive the provider answer as admission input.

`SemanticPlan` is always PROPOSED_PLAN. Strict parsing rejects unknown fields,
duplicate keys/IDs, invalid enum types, oversized envelopes, forged certificate
flags and host-authorization labels. Neither a schema nor a model confidence
field can grant authority. The structured-output capability descriptor is an
offline interface only; no provider serializer or transport hook was installed.

## Proof language

Claims contain a structured predicate, subject/object identities, relation domain,
structural scope, modality, temporal phase, attribution, source/evidence/bridge
references and unresolved conditions. Display scope names and entity labels come
from the trusted inventory, never provider-proposed prose.

The proof checker implements direct typed support and exact finite Horn-rule
instances. Same-domain inference requires matching predicates and arguments.
Cross-domain inference additionally requires the exact registered directed
bridge, its premises, rule source, scope and conditions. A rule name with matching
domain labels is insufficient. Record order, timestamp values, sampling, causality,
pairing, transformation, measurement, explanation, responsibility, execution and
speaker relations are nominal domains.

Strength is componentwise: epistemic force, candidate disposition and coverage
cannot compensate for each other. Temporal phase, attribution and modality are
separate types. Unresolved conditions remain visible. Exclusion binds a candidate,
evidence domains, rule/bridge, scope and authorized strength; ordinary support
cannot become exclusion. Contradictory admitted evidence is checked across the
inventory, including evidence omitted from the proposed support list.

A closure certificate partitions an authenticated finite universe. Every known
member needs a valid matching assessment; missing, duplicate, foreign, conditional
or unresolved members prevent closure. An open universe, null/unknown remainder,
hidden branch or wider scope cannot be certified. A nonempty remainder supports
only a finite local survivor list. EXHAUSTIVE requires no remaining or unresolved
member. Completeness is not granted by model-authored strings.

Responsibility reuses the existing attribution-state vocabulary and adds trusted
predicate verification. Actor, exact task, scope, source speaker, phase and claim
type remain bound. Assignment, completion, planning, proposal, inference and
unknown states do not inherit authority from each other or adjacent tasks.

A limitation certificate says that this inventory and rule set have not
established a proposition. It does not assert its negation or eliminate an
explanation. Existing checked support prevents a contradictory limitation.

## Renderer and acceptance

Only validated host objects enter the renderer. Every content clause maps to its
certificate and checked scope. Entity labels stay quoted as data. No provider
proposition string, connective, footer or introduction is passed through as prose.
Exact host realizations pass visible-output consistency; every other visible
draft is rebuilt from the checked plan. This explicitly avoids claiming a general
natural-language equivalence test.

ALLOW, QUALIFY, DOWNGRADE and BLOCK are structural decisions. A rejected important
proposal produces an explicit limited-support statement. When all proposed claims
fail, independently admitted referenced facts can form a separately recorded
fallback. No unsupported exclusion is rewritten into an unproved likelihood or
preference claim. Unparsed input with no useful supported facts gets a marked
fallback, and does not count as useful semantic-coverage acceptance.

## Persistence and consumers

The `semantic_acceptance_mode` feature gate is OFF by default. It can be explicitly
enabled as TRUSTED for a fresh session and is immutable within that session.
Existing displayed history is not silently migrated or certified. Historical OFF
sessions preserve their existing raw-output contract and provenance. All consumer
claims in the vertical-slice audit are scoped to TRUSTED sessions.

The original `turns.assistant_text`, ProviderJournal raw capture, wire storage and
terminal classification are unchanged. Additive tables store immutable raw copies
and independent accepted records; SQLite triggers prohibit their updates/deletion.
The accepted record binds the original provider/text hashes, proposed plan,
validation result, certificates, rendered clauses, accepted plan/text, timestamp,
session/entity/turn, submitted context, trusted inventory and runtime source hashes.
Reading a stale, mismatched or corrupted accepted record fails closed.

Chat display/check/restart inspection use accepted text. Context projection and
claim/evidence history read an explicit accepted projection. Memory receipts and
event candidates bind the accepted utterance while retaining the rule that an
utterance is not proof of an external event. Evaluation separately checks original
provider bytes and the accepted durable display, exporting both answers and the
transformation. Candidate journal readers and review-package inputs use accepted
text; audit/export retains separately labelled raw evidence. A crash before
acceptance cannot mark a strict turn displayed. A captured accepted answer is
reused after restart without generation. Ambiguous delivery remains ambiguous.

## Validation and limits

Tests include positive and negative proofs, adversarial envelopes, renderer force
and scope checks, actual ChatService admission through simulated transport,
restart/crash recovery, native evaluation validation, candidate journal reading,
memory rehydration and accepted-text blind-package construction. The previous
diagnostic pairs are reused unchanged with independently authored typed mappings;
they do not establish parsing coverage for the original free-language prompts.

All execution in this milestone is offline under a non-loopback network guard.
The provider transport, route, streaming assembly, terminal classifier and journal
core are unchanged. Historical failures/UNKNOWNs remain historical. A successful
source freeze is engineering readiness for a separately authorized fresh revision,
not a semantic PASS, production activation or downstream-gate unlock.
