# Fresh external44 revision 13: stopped after known-terminal rejection

The fresh G6-07 validation started from zero against the unchanged frozen runtime. It submitted 24 of 44 requests and captured 23 usable replies. One request returned a trusted completed terminal without usable visible output, so the frozen runner stopped and quarantined the entire revision. There were zero new UNKNOWN outcomes, retries, resends or replacement requests. Twenty turns were not submitted.

All four criteria for every captured reply were independently reviewed and quote-bound: 92 of 176 reviewed, comprising 79 PASS, 8 FAIL and 5 UNCLEAR. The remaining 84 criteria are unreviewed: four belong to the unusable response and 80 to unsubmitted turns. The unusable response itself received no semantic verdict.

The review retains two MAJOR findings: a recurrence of premature candidate closure across reasoning domains, and unsupported implementation attribution. One MINOR finding concerns overcertain audience reaction, and one MINOR item retains unresolved quoted-addressee ambiguity. Candidate Closure is FAIL. The semantic gate fails, G6-07 is STOPPED and incomplete, and G6-08 remains LOCKED. No later gate ran.

The user explicitly retained the frozen model-switch protocol: 42 planned DeepSeek Pro turns and two DeepSeek Flash continuation turns. The actual 24 submitted requests all used DeepSeek Official deepseek-v4-pro, Responses, max reasoning, DIRECT_NO_PROXY and streaming; neither Flash slot was reached. No alternative provider was used.

The existing runtime source freeze PROVIDER2_REMOTE_RUNTIME_20260919_01 remains unchanged, including Candidate Closure semantics. Ten targeted offline modules passed 223 checks. Existing legacy compatibility evidence was revalidated against unchanged source, retaining its original 450 denominator, 449 compatible passes and one expected historical identity sentinel. None of those engineering results count as semantic passes.

Historical revisions and findings, including R12-N02-01, remain intact. This publication contains only this summary, aggregate public audit metadata and their public hash manifest. Provider wire data, hidden reasoning, private dialogues, private mappings, databases, heldout material, credentials and spend ledgers remain local. All paid processes have exited. Further repair or recovery requires a separate task; this revision cannot be resumed or replayed.
