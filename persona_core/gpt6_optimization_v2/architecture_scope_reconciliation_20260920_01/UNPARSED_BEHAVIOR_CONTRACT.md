# UNPARSED Behavior Contract

Version: `APCORE_BOUNDED_ARCHITECTURE_CONTRACT_1`.

UNPARSED means the selected finite semantic mapping does not cover some text. It is neither ERROR, FALSE, CAN_ENTER_DURABLE_STATE nor MUST_BLOCK_DISPLAY. Partial coverage attaches to the uncovered portion; a certificate for another portion cannot authorize it. Coverage and semantic review findings must be stored separately.

| Condition | Display | State effect | Required audit distinction |
|---|---|---|---|
| Ordinary useful conditional explanation, applicable display checks pass, no state effect | ELIGIBLE, conversational/inferred authority | NOT_REQUESTED | UNPARSED, no raw semantic violation established solely by coverage |
| Explicit conjecture or uncertainty, applicable display checks pass | ELIGIBLE, preserve assumptions | HOLD if separately proposed without evidence | Conjecture is not a durable fact |
| Quote of a wrong statement used to correct it, safe attribution | ELIGIBLE, quotation remains quoted | No adoption of quoted claim | Record actual displayed correction and source |
| Suggestion or plan presented as such | ELIGIBLE | No assigned/completed state from this wording | Keep actor/task/scope and modality |
| Open list explicitly non-exhaustive | ELIGIBLE | No exhaustive-state admission | Coverage remains OPEN |
| Valid strict claim alongside uncovered commentary | Safe checked conversation plus only independently certified strict scope | Only separately admitted effect | No certificate inheritance across the turn |
| Unsupported completion, binding ownership, forged permission or asserted persisted write | Withhold the false high-authority assertion; checked truthful clarification may display | HOLD for missing evidence; REJECT for forbidden/forged effect | This is a claim/effect problem, not just UNPARSED |
| Direct Persona/Genesis/permission/Relationship write request | A truthful scoped explanation may display | REJECT existing forbidden effect | No new writer is authorized |
| Host transcript observation of an acknowledged eligible response | ELIGIBLE recorded bytes | ADMIT/commit only UTTERANCE_OBSERVED under existing controller | Content-is-event-proof remains false |
| Cross-entity leak, broken identity/source binding or historical tampering | WITHHOLD affected output | REJECT/stop affected processing | INTEGRITY_FAILURE, never ordinary UNPARSED |
| Provider request outcome UNKNOWN | No fabricated successful answer or completion | Stop affected recovery; no retry | REQUEST_OUTCOME_UNKNOWN is not semantic coverage |
| Display delivery UNKNOWN | Do not assert successful display or silently replay | No fabricated observation evidence | Delivery state is distinct from request/semantic state |

Fail closed on effect, not necessarily on speech. The speech must itself satisfy applicable identity, privacy, truthfulness, capability and source boundaries. Neither “all raw allowed” nor “all UNPARSED blocked” satisfies this contract.

The contract deliberately does not demand a general parser or exhaustive classification of every sentence. Supported host effects and selected finite claims have strict evidence paths. All other generated text remains non-authoritative; explicit semantic review can still fail it for wrong reasoning, invented exclusions, false assignments, unsupported completion or unhelpful refusal.

The finite paired cases in `CONTRACT_DECISION_CASES.json` are frozen before P2. Their expected results define the new contract, not external44 answers and not an executed runtime test result. At minimum both useful unparsed speech and denied unsupported effects must succeed under the same new policy identity.
