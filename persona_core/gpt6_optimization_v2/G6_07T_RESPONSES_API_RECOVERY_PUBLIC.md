# G6-07T — DeepSeek Responses API alternate transport evidence

The current DeepSeek V4 Pro model was tested through DeepSeek's official `/responses` interface without changing the model, Persona Core, Claim/Evidence semantics, Reasoning Scope semantics, heldout data, rubric or thresholds.

Two independent synthetic requests completed with explicit terminal events and zero automatic retries. The short probe returned HTTP 200, first event at 219 ms and `response.completed` after about 1.4 seconds. A transport-equivalent probe used `deepseek-v4-pro`, `reasoning=max`, streaming and `max_output_tokens=32768`; it ran for about 251 seconds, produced 27,930 monotonically ordered SSE events, and ended with `response.completed` plus usage.

This is evidence for a viable alternate official transport path. It is **not** evidence that the historical Chat Completions stream recovered, and it does not close any semantic finding. The four historical `SUBMITTED_STATUS_UNKNOWN` requests remain quarantined and non-replayable.

The next implementation step is to add Responses API as a separate versioned provider transport, preserve the exact existing message roles and accounting boundaries, reject incomplete/failed terminal responses as non-accepted replies, and keep partial streams non-displayable. After complete offline regression and a new source freeze, a new validation revision must rerun the full G6-07 denominator from zero before heldout or later gates may start.

Official references:

- `https://api-docs.deepseek.com/api/create-response/`
- `https://api-docs.deepseek.com/guides/responses_api/`
