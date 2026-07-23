# Operational Playbook (both paradigms)

Cross-cutting, hard-won operational lessons for running synthesis + rollout at scale. Read this
before any full run.

## 1. Save the EXACT payload sent to the API — that is the only complete data.

This is the single most important thing to get right, and the easiest to get subtly wrong.

Your training data must be **byte-for-byte what the model actually saw**: the exact `messages` array
and the exact `tools` array that were passed to the API call. Most benchmark runners do **not** hand
you this. What they persist is a *reconstructed* view — a `conversation_history` / trajectory object
they rebuild for logging — and that reconstruction routinely diverges from the real request:

- The **system prompt / policy** is prepended inside the client wrapper and often omitted from the
  logged history.
- **Tool schemas** are assembled (merged, filtered, reordered, JSON-serialized) right before the
  call; the logged view may show a different or partial list.
- Messages get **normalized** for display (roles renamed, `tool_call`/`tool_result` blocks reshaped,
  content flattened), so the logged text is not the wire format.
- Multi-turn state (assistant `tool_calls`, the matching `tool` responses, ordering) can be
  **lossily summarized**.

If you train on the reconstructed view while the eval feeds the real payload, the train/eval input
formats diverge and the score drops for reasons that look like "bad data" but are actually a
**capture bug**.

### What to do

**Find the exact line where the request is built and sent, and persist its inputs there** — not
after the fact, not from a downstream log. Concretely:

1. **Locate the API boundary.** Grep the runner for the call site, e.g.
   `client.chat.completions.create(`, `litellm.completion(`, `acompletion(`, `messages=`, `tools=`.
   That call receives the two arrays you need.
2. **Capture `messages` and `tools` at that point**, before any post-processing, exactly as passed:
   ```python
   # right where the request is issued
   payload = {"model": model, "messages": messages, "tools": tools}
   record_api_payload(task_id, turn_idx, payload)   # append-only, one record per API call
   resp = client.chat.completions.create(**payload)
   ```
   Save every turn's payload (a multi-turn task issues several calls); the final training sample is
   the last turn's `messages` + the shared `tools`, but keeping all turns lets you reconstruct or
   debug any step.
3. **Persist the raw request, then normalize as a separate step.** Keep the untouched payload on
   disk (JSON), and do any format conversion (→ SFT messages) downstream from that saved copy. Never
   let the only surviving copy be a normalized one — you can always re-normalize from raw, but you
   can't recover raw from a lossy view.
4. **Verify capture == wire.** Diff one saved record against the real request: same message count,
   same roles/order, `tool_calls` paired with their `tool` responses, and the `tools` array
   identical to what the environment exposed for that task. If the system/policy message is supposed
   to be message[0], confirm it's actually there.

Rule of thumb: **the API call site is the source of truth.** Capture there, store raw, convert later.

## 2. Checkpoint / resume discipline.

- New task set → new save name (reusing one silently skips the new tasks as "already done").
- Checkpoint **per completed item**, not at the end of the run. A crash, timeout, or Ctrl-C at hour 3
  of a long roll must lose one item, not the whole batch.
