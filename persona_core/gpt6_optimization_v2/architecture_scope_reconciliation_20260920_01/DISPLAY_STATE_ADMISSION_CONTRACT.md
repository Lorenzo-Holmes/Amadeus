# Display Eligibility / State Admission Contract

Version: `APCORE_BOUNDED_ARCHITECTURE_CONTRACT_1`. Effective with the completed P1 adoption record. MUST/MUST NOT are normative. The following record requirements are the P2 target contract, not claims that the current implementation already emits them.

## Distinct decisions

| Decision | Object | Possible result | Authority granted |
|---|---|---|---|
| DISPLAY_ELIGIBILITY | A specific candidate visible text, mode, identity and context | ELIGIBLE / WITHHOLD / SAFE_ALTERNATIVE_REQUIRED | Permission to deliver that exact text in this conversation only |
| Bounded semantic verification | Selected claim/plan plus independently bound typed evidence | Existing finite validator decisions/certificates, or UNPARSED | Support for only the certified claim within its scope |
| STATE_ADMISSION | One candidate effect, entity, evidence, permission and policy | ADMIT / HOLD / REJECT | Permission for only the approved payload/effect; no commit yet |
| STATE_COMMIT | An authentic admitted effect and its still-valid evidence | Committed receipt / idempotent existing receipt / failed or uncertain operation | Only the persisted event/effect established by the receipt |

`DISPLAY_ELIGIBLE != FACT_TRUE != STATE_ADMITTED != STATE_COMMITTED`. Absence of a detected display violation is not proof of factual correctness. A semantic certificate does not replace an AdmissionDecision, permission or execution receipt.

## Display inputs and rule order

The host verifies session/entity/mode, captured response lineage, source/policy identity and the actual context first. A broken binding, cross-entity disclosure, missing required permission, source identity mismatch or corrupted evidence withholds the affected output and effect. Such failures MUST NOT be relabeled UNPARSED.

The host then applies the mode-appropriate Response Check and existing source/capability/privacy constraints. Known fabrication of a memory, real-world tool action, completion, ownership, exclusion or exhaustive conclusion is not made permissible by declining to store it. Direct, high-authority claims about permission, binding responsibility, completed execution or persisted state require the corresponding host evidence. An unavailable bounded proof or receipt cannot be replaced by model self-certification.

Ordinary explanation, reasoning from explicitly stated assumptions, suggestions and questions may be displayed after these checks regardless of whether a typed plan exists. No global typed-plan coverage threshold is a display requirement. The response remains at its actual conversational/reported/inferred authority.

A high-authority claim is selected by its semantics and requested effect: e.g. asserting an action completed, a binding assignment exists, a state was persisted, a closed finite universe was exhaustively excluded, or that a governed source event is a personal memory. It is not selected by benchmark IDs or by arbitrary assertive tone. Ordinary factual prose does not all become a strict typed claim. Known factual errors still fail review; the finite checker is not a universal truth proof.

For mixed content, the safe portion may be used only if a host-produced alternative preserves the user's task and passes the same display checks with a recorded transformation. P2 does not gain authority to invent a free-text semantic rewriter: otherwise withhold the unsafe answer and provide a truthful, scoped clarification. No hidden repair call or automatic paid retry. A generic fallback is not automatically task completion, naturalness or usefulness PASS.

## State admission rule order

For each proposed effect: authenticate identity and entity → validate supported effect kind and scope → bind candidate/payload/source/evidence → verify host authority and required permission → decide ADMIT/HOLD/REJECT → revalidate on atomic commit → retain receipt and idempotency identity. Missing evidence for a supported permissible effect means HOLD; forbidden effect, wrong entity or forged/tampered authority means REJECT. No state attempt means NOT_REQUESTED in audit, not an invented ADMIT.

Only existing supported event kinds are in P2 scope. Source/Genesis writes and direct Persona, permission or Relationship writes remain forbidden. Existing legal derived relationship/affect changes may occur only through admitted event reducers; conversation cannot bypass those reducers. A general executor or new user-fact writer is not authorized. Unsupported requested effects remain rejected, even with fluent natural-language support.

`UTTERANCE_OBSERVED` can be admitted from a real display acknowledgment and host-bound transcript. Its payload must keep `described_events_proven=false` and `content_is_event_proof=false`. Its durable storage does not promote embedded propositions. A user report can support “the user reported X”; any stronger fact requires its own evidence class. Real-world completion needs the real controlled action receipt; a text-check receipt proves only the specified local text check, never an external action.

## Raw, displayed and accepted lineages

| Name | Frozen meaning | Prohibited interpretation |
|---|---|---|
| raw_provider_text | Immutable provider-origin text/envelope, bound to captured raw bytes and request | User saw it; host admitted its claims |
| displayed_text | Exact host-selected text delivered with acknowledged display lineage | Everything in it is true or durable |
| accepted_text | Text approved under an explicitly named policy, purpose and version | Universal proof of all content or permission to mutate state |
| typed_plan | Proposed finite semantic structure; accepted subset identified separately | Model-supplied authority |
| admission_decision | Host-issued decision for a candidate effect | Commit receipt or permission for unrelated effects |
| runtime_commit | Verified event/state commit receipt | Evidence that every sentence in the turn is true |

The new conversation policy accepts a display candidate under purpose DISPLAY. Its `accepted_text` may equal `displayed_text` only when that exact candidate was acknowledged. State admission remains an independent lineage through candidate/decision/commit, not a second name for the entire displayed answer. Optional strict typed claim realization has purpose BOUNDED_CLAIM and its own certificate references. Missing strict output is permitted when no strict claim/effect is requested.

Legacy `TRUSTED_SEMANTIC_ACCEPTANCE_1` accepted text retains its exact historical policy meaning, including fallback outcomes. Do not rewrite it into new displayed records or claim all its content was proven true. Legacy OFF remains explicitly legacy and uncertified. Only new sessions may opt into the P2 bounded policy; existing sessions cannot silently change mode.

## Frozen prospective version names

The new host-selected session mode is `BOUNDED`; display policy is `BOUNDED_CONVERSATION_1`; combined record schema is `RAW_DISPLAY_ACCEPTED_IDENTITY_2`; formal binding schema is `FORMAL_BOUNDED_BINDING_1`; evaluator contract is `DUAL_GATE_DISPLAY_STATE_1`. These are reserved P2 contract identifiers, not presently installed code values. Authority Ladder labels remain governance views, not a new enum.

BOUNDED always requires DISPLAY_ELIGIBILITY. It does not change the default or reinterpret old OFF/TRUSTED sessions. The optional bounded-claim path retains `TRUSTED_SEMANTIC_ACCEPTANCE_1` proof semantics; operational state effects retain `admission-46.2` and its existing allowed kinds. Host-selected claim verification may be requested independently of ordinary displayed prose. An ordinary BOUNDED response is plain conversation, not a required JSON envelope. Strict malformed-envelope handling applies only to a selected strict request; missing coverage on another portion cannot grant a strict claim or block all safe speech by itself.

The new formal binding retains source manifest/runtime hashes, provider configuration identity and dataset/rubric identities, and additionally binds this architecture contract, routing hash, display-policy version, state-admission-policy version and consumer authority matrix hash. A routing hash is evaluation provenance only; production semantic code MUST NOT read the routing content. Record schema and evaluator identity distinguish display-purpose acceptance from finite claim acceptance. This adds no provider transport field or permission.

## Required persisted audit fields

Each new policy record binds: record/schema version; policy ID, version and purpose; session/entity/turn; request/context digest; source/runtime identity; raw-byte and raw-text hashes; candidate visible-text hash; display decision, reason and guard version; actual displayed-text hash and acknowledgment status; authority/modality/attribution metadata or explicit absence; proposed and accepted typed-plan references if present; candidate, admission and commit references if applicable; transformations and timestamps. No field is inferred from “text exists.”

Display intent, display acknowledgment, provider capture and commit acknowledgment remain different events. DISPLAY_INTENT without acknowledgment remains DELIVERY_STATUS_UNKNOWN. No automatic redisplay/resubmit; next-turn shared history must not falsely claim the user saw it. An acknowledged display followed by a crash before observation may resume only the idempotent observation/commit step, never the provider or display operation.

## Consumer and evidence discipline

The consumer matrix is authoritative. Display/history use identical acknowledged displayed bytes; context uses those bytes or a traceable bounded projection retaining speaker, entity, uncertainty, conditions and correction status. State consumers require the appropriate candidate/decision/commit lineage. Source objects and host EvidenceToken/receipts are auxiliary evidence, independently authenticated; their omission from the seven text/record columns does not remove their requirement.

P2 must record finite checker limitations. Semantic quality is tested separately against actual displayed content. A routing contract or a missing pattern match cannot claim complete factual, privacy or persona validation.
