# Responses terminal classification

A validated Responses terminal could be incorrectly recorded as an unknown transport outcome when its answer failed local text or usage checks. The parser now separates terminal certainty from answer usability. A completed response with no usable assistant text, an incomplete response, or a failed response produces `RESPONSE_REJECTED_TERMINAL_KNOWN`. Missing or untrusted terminal evidence still produces `SUBMITTED_STATUS_UNKNOWN`.

Known rejections consume the slot, stop the batch, and never trigger an automatic retry. They carry no assistant text or semantic verdict. Valid token usage remains available for estimation; malformed usage remains unestimated with its reservation retained. Reasoning, summaries and partial output never become a character answer, conversation history or memory.

The parent binds the normalized receipt to its original wire before journal admission. Successful normalization retains its prior bytes. Existing journal statuses remain readable without a historical status migration. Evaluation reporting distinguishes known rejections from unresolved remote outcomes; candidate and blind-review gates continue requiring captured and displayed replies.

The design follows the final-event and token-budget contracts in the [official Responses guide](https://api-docs.deepseek.com/guides/responses_api/) and [API reference](https://api-docs.deepseek.com/api/create-response/). It does not establish why a provider might omit final text, and it does not claim that an empty completed result is a normal usable answer.

Validation: 23 new neutral authored mechanism tests, 25 component modules / 395 passing tests, and the fixed legacy denominator of 450: 449 compatible passes plus the preserved expected historical source-identity sentinel, zero unexpected functional failures. No historical source-identity evidence was changed to obtain a green result. Runtime, tests and private audits are bound by the `RESPONSES_TERMINAL_CLASSIFICATION_20260919_01` freeze. These are engineering results, not semantic or product acceptance.

This public change contains source, authored tests and this summary only. Private journals, wire captures, dialogue, accounting records, credentials, heldout material and reviewer mappings are excluded.
