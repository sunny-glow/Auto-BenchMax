# Paradigm B: Construct-then-Verify (for rule-based benchmarks)

Use this paradigm when the benchmark's evaluator scores by a **deterministic rule** — a final-state
hash, an assertion over environment state, an exact/substring match, or unit tests — rather than an
LLM judge. The examples below come from a rule-based benchmark with two task domains: a **retail**
domain (DB-hash + substring scoring) and a **telecom** domain (env-assertion scoring). Your benchmark
will differ; keep the method, adapt the specifics.

## The core creed

**Build the ground-truth first, then prove it scores by replaying it through the evaluator's own
interface.** You cannot "roll first and see" — with a rule-based evaluator there is nothing to score
against until the gold exists. So construction and verification happen *before* any rollout:

```
Construct stage:   sample legal real entities → assemble gold action sequence (+ expected answer)
  ↓ (every parameter must satisfy the tool's preconditions, or replay throws)
Verify stage:      replay the gold through the SAME environment interface the evaluator uses
  ↓ (assert final state changed / hash differs / assertions pass → task is scorable)
  ↓ (also build a NEGATIVE trajectory and assert it scores 0 — proves the check discriminates)
Phrase stage:      turn the gold facts into a first-person user prompt (LLM or template)
  ↓ (must preserve EVERY concrete detail the gold action needs — see "self-contained prompts")
Roll stage:        run the task with the solver model; SFT keeps reward==1 trajectories
```

The difficulty of this paradigm is **not writing scoring rules** (the benchmark already has them) —
it is **guaranteeing the gold actions are legal** so that replay produces a definite, scorable state.

> Validated on a rule-based benchmark: a retail domain (DB-hash + substring scoring) and a telecom
> domain (env-assertion scoring), with positive/negative construct-time checks passing and a high
> rollout pass-rate.

## Step 0: read the evaluator so you know what "scorable" means

For each task type, find exactly what the reward compares. Two worked examples (yours will differ, but ask
the same questions):

- **retail**: `reward_basis = ["DB", "COMMUNICATE"]`. DB check replays the gold `actions` on a clean
  DB to get a target hash, replays the agent's actions to get an actual hash, and compares. COMMUNICATE
  checks each string in `communicate_info` as a **substring** of an assistant message
  (`info.lower() in msg.content.lower().replace(",","")`). **Read-only tools (`calculate`, `get_*`)
  are NOT scored** — retail's basis has no ACTION dimension.
- **telecom**: reward is driven by `env_assertions` (functions like `assert_internet_speed(excellent)`
  run against the *post-repair* device state). `reward_basis` is either `["ENV_ASSERTION"]` or
  `["ACTION","ENV_ASSERTION"]`. For pure-ENV_ASSERTION tasks the gold actions don't even score —
  only the final device state does.

Two consequences you must encode:
- **Legality is everything.** A gold action with a bad `order_id`/`item_id`/`payment_method_id` throws
  at replay → target state unchanged → task is void. So every parameter must be sampled from real
  entities that satisfy that tool's preconditions.
- **Formatting must match the check's normalization.** The substring check strips commas and
  lowercases, so numbers must be emitted **without commas** and in the format the environment itself
  produces. In the reference benchmark prices render trailing-zero-trimmed (`180.1`, `481.5`), so gold must emit `180.1`,
  not `180.10` — otherwise a correct rollout that says `180.1` fails the substring match.

## Two ways to build gold; prefer reusing an official generator

### Option 1 — reuse the benchmark's own task generator (best when it exists)

Some domains ship a self-verifying compositional generator. The **telecom** domain had one
(subtask "blocks", each with a break-fn / fix-fn / env-assertion),
a `compose_tasks` that enumerates legal permutations, and a `TaskManager.create_task` /
`verify_task` that executes and self-checks in the real environment. **Reuse it** — do not rebuild.
The full composition produces far more tasks than the official set, which is a subset. To synthesize
*new* tasks, run the generator and **exclude the official set**, then sample.

Practical notes when reusing:
- The generator may **print** large `task_instructions` to stdout; wrap it in
  `contextlib.redirect_stdout(io.StringIO())` to keep your stats output clean.
- Some sub-types are **intrinsically scarce** (telecom `service_issue` at high subtask counts simply
  doesn't exist in the full combination). Do not force a strict per-bin quota that the data can't
  satisfy — fall back to "exclude base, random-sample from the new pool" (a real distribution
  constraint you cannot exceed).

### Option 2 — write a block/compose/verify generator (when there is none)

The **retail** domain had no official generator, so a v2 generator was written in the same three-layer
style as the telecom one:

1. **Blocks.** Each atomic write operation is a `Block` dataclass carrying its own sampler + the
   `actions` it emits + a deterministic `effect` (e.g. refund amount, qty, attribute options). This
   makes consistency automatic — the block knows exactly what it changed.
2. **`compose_for_user`.** Combine 1–N *non-conflicting* blocks on the **same user** (conflict rule:
   two writes can't touch the same order). Compound multi-write tasks fall out for free. **This is
   the layer a naive v1 generator lacks** — and its absence is why v1 was all single-write (see the
   distribution-drift failure in the main SKILL.md).
3. **Construct-time verify.** Right after building a task, replay it through `get_environment()` (the
   same interface the evaluator uses) and assert the state actually changed / hash differs.

Per-write-tool preconditions you must respect when sampling (retail example — read your tools.py for
the real ones):
- `cancel_pending_order`: order `status=="pending"`; reason ∈ a fixed set.
- `return_delivered_order_items`: order `delivered`; payment original method or gift card.
- `exchange_delivered_order_items`: order `delivered`; new item same product & `available`; gift-card
  balance covers the difference.
- `modify_pending_order_items`: order `pending`; new item same product, available, ≠ old.
- `modify_pending_order_address` / `modify_user_address`: existence checks only; borrow a real
  address from another user.

## Construct-time verification: the lifeline (and its sharp edges)

The verification replay is what guarantees 100% scorability. Two mistakes cost real time:

1. **`SimulationRun` has required fields.** When you hand-build a "perfect" trajectory to verify, it
   needs `start_time` / `end_time` / `duration` — supply placeholders
   (`start_time="1970-01-01T00:00:00", duration=0.0`).
2. **Tool-message content is replay-validated.** The evaluator's `set_state` replays the trajectory
   and checks **each `ToolMessage` content** equals the recomputed tool result. You cannot fill a
   placeholder like `"ok"` — you must call the environment's real tool and use its actual return:
   ```python
   env = get_environment()
   for i, a in enumerate(task.evaluation_criteria.actions):
       tc = ToolCall(id=f"tc_{i}", name=a.name, arguments=a.arguments)
       messages.append(AssistantMessage(role="assistant", content=None, tool_calls=[tc]))
       messages.append(env.get_response(tc))   # real return value
   ```
   For a **negative** check, don't post-edit a tool_call (that breaks content consistency and throws);
   instead corrupt the action *first*, then build a consistent trajectory around it.

Verify **both** polarities for **every** sub-type you generate: a positive trajectory that states all
required info must score reward=1, and a negative one that omits it must score 0. If a new
communicate/answer sub-type doesn't have a passing positive AND a failing negative, it's not proven.

## Distribution control: cover every sub-type at the target ratio

This is where paradigm B most often goes wrong, and it directly serves the overriding principle
(align to sub-type granularity). Three hard-won pitfalls from tuning a retail domain's `communicate`
sub-type mix (target ratios set to match the official base):

1. **A "universal" sub-type will drain the quota.** `count` (total item qty) can be supported by
   almost any write, while `amount_sum` needs a refund-bearing write. A naive per-candidate random
   draw with fallback dumps everything into the universal bucket. **Diagnose by scripting
   "which sub-types can each candidate support"** — the histogram instantly reveals the universal
   bucket and the scarce one.
2. **Allocate scarce-first, and bound the fallback.** Fill the scarcest sub-type first from its
   eligible candidates; when a quota can't be filled, let the leftover fall back **only to related
   types** (amount_sum → amount_per_order), and if nothing qualifies, **leave it blank** rather than
   dumping into the universal bucket. Purity beats volume.
3. **Purity can starve total volume — compensate the ratio.** After restricting fallback, the clean
   distribution's total communicate-rate drops below target (the scarce sub-type has few eligible
   candidates). Fix: raise the `--communicate-ratio` knob so the losses are absorbed and the final
   rate lands on target.

General rule: **allocate from the scarcest sub-type first; bound every fallback bucket; compute
"per-sample supportable sub-types" before tuning parameters** — it's far faster than trial-and-error
on knobs.

## Phrasing: turn gold facts into a self-contained prompt

The user prompt must contain **every** detail the gold action needs, or the solver cannot possibly
reproduce it. The single biggest real bug here: a full address's `address2`/`Suite` line was dropped
from the prompt, so a whole batch of address tasks scored **0%** — the agent had no way to know
"Suite 327". Fix was two-fold and both are general lessons:
- Format the **complete** entity into the ask (a `_fmt_addr` that includes the suite/apt/unit line;
  every product option/variant spec verbatim).
- If an LLM rewrites the phrasing, give it a hard command: *"preserve EVERY concrete detail verbatim
  — full street address including any suite/unit line, and every product specification/option. Do
  NOT drop, summarize, or abbreviate."* LLMs love to "tidy" and will silently drop specifics.

By sub-type, have the simulated user explicitly ask for the info the check wants (so the golden
assistant naturally states it): count → "tell me how many items total"; attr → "confirm the new
color/material"; per-order → "tell me each order's refund separately". The positive-check
`_perfect_sim` then states ALL required values in the final message.

If the domain's prompts are already rich and rewriting risks breaking a key constraint (telecom's
"user only accepts 'excellent' speed"), **skip LLM rewriting** — a template is safer and needs no
network calls.

## Teaching tool use even when the tool isn't scored

Read-only tools may not affect the reward, but including them in the golden trajectory still teaches
the behavior via SFT. Real failures showed the model **mentally computing amounts instead of calling
`calculate`**, then getting the number wrong (a COMMUNICATE failure). So for amount tasks, insert a
`calculate` action before the writes even though `calculate` doesn't score — the SFT trajectory
teaches "use the tool to do arithmetic." Generalize: if failures trace to a skill the benchmark
doesn't directly score but the golden path should model, put it in the trajectory anyway.

## Registering the synthetic task set

A rule-based benchmark usually loads tasks by a **registered name**, not a file path. To roll your
synth, register it — typically a small loader + a registration call in the benchmark's registry:
```python
registry.register_tasks(_load_synth_tasks("retail", filename="tasks_synth_v2.json"), "retail_synth_v2")
```
Don't touch existing registrations. Confirm the new set lists and loads before rolling.

## Quick start (end-to-end, worked example: tau2-bench)

The commands below are the concrete tau2-bench implementation of this paradigm — a real rule-based
benchmark (retail + telecom domains). Treat it as a filled-in template: the construct → verify →
phrase → roll structure transfers to any rule-based benchmark, only the generator / runner change.

```bash
# 1. Synthesize + construct-time verify (no network if --no-llm; fast, seconds–minutes)
python synth_retail_tasks_v2.py --num 3000 \
  --multi-write-ratio 0.48 --communicate-ratio 0.46 --llm-workers 16 --verify \
  --out tasks_synth_v2.json \
  --phrase-cache tasks_synth_v2.json.phrase_cache.json
#    (telecom variant: python synth_telecom_tasks.py --num 456 --verify)

# 2. Roll trajectories, keep reward==1 for SFT (resume built in; mind the rate-limit ceiling)
#    Use the benchmark's own runner against the registered synth task set, at the safe concurrency.
```

**Smoke-test tiny first** (`--num 300 --no-llm --verify`): diff the structural histogram (multi-write
%, mixed-mode %, communicate sub-type mix, calculate presence, number formatting) against the target,
and confirm positive checks reward=1 / negative checks reward=0 for each sub-type. Only then scale.

## Reference scripts

- `synth_retail_tasks_v2.py` — block/compose/verify generator with communicate sub-type
  control, `_fmt_num` trailing-zero-trim, LLM phrasing + phrase cache, construct-time positive/negative
  verification.
- `synth_telecom_tasks.py` — reuse-the-official-generator variant (exclude base, sample new
  pool, replay-verify).
- The benchmark's task registry — how a synthetic task set is registered.
- The benchmark's SFT export util — `only_successful=True` keeps only reward==1 trajectories in SFT.
