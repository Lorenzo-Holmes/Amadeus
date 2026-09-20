# Consumer Authority Matrix

This matrix is a ceiling on allowed reads, not a grant of mutation or external publication. Same-entity authentication and purpose binding precede every permitted read. NONE of the entries permits an automatic authority upgrade.

CONTENT = exact checked/acknowledged dialogue content; CONTEXT = attributed non-authoritative payload; LINEAGE = policy/hash/reference metadata, not alternate answer bytes; PROPOSAL = explicitly pending/untrusted object; SCOPED = verified status/effect restricted to its evidence and entity; EVIDENCE_REF = independently verified certified subset plus evidence, never the bare proposed plan; OBSERVATION = proof of speech occurrence only; AUDIT/REVIEW = authorized evidence inspection, not live context; BLIND_CONTENT = approved deidentified displayed dialogue; DENY = no access for this purpose.

| Consumer | raw_provider_text | displayed_text | accepted_text | typed_plan | admission_decision | runtime_commit | event_candidate | Rule |
|---|---|---|---|---|---|---|---|---|
| Display | DENY | CONTENT | LINEAGE | DENY | DENY | DENY | DENY | Emit exact checked displayed candidate only after host selection; use acknowledgment to establish actual displayed lineage. |
| Conversation History | DENY | CONTENT | LINEAGE | DENY | DENY | DENY | DENY | Persist/replay acknowledged visible words, role, source, mode and corrections. Never substitute hidden raw drafts. |
| Next-turn Context | DENY | CONTENT | LINEAGE | DENY | SCOPED | SCOPED | PROPOSAL | Conversation uses actual displayed history; separately labeled verified state or pending proposals do not rewrite that history. |
| Working Context | DENY | CONTEXT | LINEAGE | PROPOSAL | SCOPED | SCOPED | PROPOSAL | Temporary reasoning may use labeled assumptions/proposals; it cannot write authoritative facts or silently launder source strength. |
| Memory Observation | DENY | OBSERVATION | LINEAGE | DENY | SCOPED | SCOPED | PROPOSAL | Record speech occurrence only from real transcript/delivery, then existing host admission/commit; content_is_event_proof=false. |
| Durable Memory | DENY | CONTEXT | LINEAGE | EVIDENCE_REF | SCOPED | SCOPED | PROPOSAL | Write only through authentic approved event/commit. Displayed text is payload/context, never fact authority. |
| Persona State | DENY | DENY | DENY | DENY | SCOPED | SCOPED | PROPOSAL | Only inspect explicitly governed proposal or lawful event lineage. Direct Persona/Genesis changes are not authorized in P2. |
| Relationship State | DENY | DENY | DENY | DENY | SCOPED | SCOPED | PROPOSAL | Existing permitted committed events drive reducers. Direct text, familiarity or repetition cannot write relationship or permission. |
| Responsibility State | DENY | CONTEXT | LINEAGE | EVIDENCE_REF | SCOPED | SCOPED | PROPOSAL | Bind actor/task/scope/source. Proposal, suggestion and inferred attribution cannot become assigned state; no new writer in P2. |
| Task / Execution State | DENY | CONTEXT | LINEAGE | EVIDENCE_REF | SCOPED | SCOPED | PROPOSAL | Permission, actual operation receipt, admission and commit are separate. Planned text cannot establish completion. |
| Candidate Creation | DENY | CONTEXT | LINEAGE | PROPOSAL | SCOPED | SCOPED | PROPOSAL | May propose from attributed visible context or explicit finite proposal; never auto-ADMIT, issue evidence or create authority from raw. |
| Evaluation | AUDIT | REVIEW | REVIEW | AUDIT | AUDIT | AUDIT | AUDIT | Gate A scores displayed content; Gate B scores state lineage/deltas. Raw supports diagnosis only, not replacement of the product answer. |
| Blind Package | DENY | BLIND_CONTENT | DENY | DENY | DENY | DENY | DENY | Viewer payload includes approved deidentified actual dialogue only. Restricted curator holds lineage mapping separately; no scores, model labels, expected answers or implementation notes. |
| Audit / Review | AUDIT | AUDIT | AUDIT | AUDIT | AUDIT | AUDIT | AUDIT | Authorized local audit may compare all evidence with provenance. Public export and independent blind payload remain narrower. |

## Live adapter mapping

The current accepted-output registry has nine purposes: display, history, next_turn_context, memory, evaluation, candidate, blind, audit, review. The fourteen governance consumers intentionally include state consumers implemented through other APIs; they do not demand fourteen new purpose strings.

Display/history/next_turn_context map to TranscriptStore conversation projections. Working context maps to those projections plus context routing. Memory Observation uses AdmissionController._turn/observe_turn. Durable Memory uses admitted runtime events/retrieval. Persona and Relationship retain their existing governed proposal/reducer paths. Responsibility and Task/Execution consume only supported admitted event evidence; no general writer is introduced. Candidate Creation maps to AdmissionController.propose, not the clean release-candidate operation. Evaluation/blind/audit/review use version-aware export adapters.

The internal display-selection component may inspect captured raw text to perform DISPLAY_ELIGIBILITY; it is not a display/history consumer and grants no state authority. Every selected candidate, transformation, accepted policy and actual displayed acknowledgment remains bound. No consumer may fall back to raw because a new display/accepted record is missing, malformed or incompatible.

## Required continuity behavior

History and next-turn agree about what was shown. Next-turn may append a separately marked host state update or correction, never secretly replace earlier displayed words. Summaries retain entity, speaker, report/inference/conditional status and correction links; if the bounded context budget cannot preserve those qualifications, omit the claim or reference the original, not strengthen it.

State readers may inspect conversation payload for a proposed observation or supported effect, but authority comes from their own admission/evidence/commit contract. A durable speech observation remains compatible with conversational authority for its content.

Blind packaging is not public publication. A restricted curator may verify full lineages before producing an approved blind view; reviewers receive no hidden raw/accepted alternatives or state implementation labels. State-integrity internal evidence is reviewed on its own track. This P1 public package contains no conversations.
