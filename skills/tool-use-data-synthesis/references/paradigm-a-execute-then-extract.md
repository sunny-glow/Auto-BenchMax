# Paradigm A: Execute-then-Extract (for LLM-judged benchmarks)

Use this paradigm when the benchmark's evaluator scores a **free-text answer with an LLM judge**
(per-claim coverage, rubric score, etc.) rather than a deterministic rule. A reference implementation
lives under `services/mcp_eval/eval_scripts/synth/`.

## The core creed

**Do not trust generation, only trust execution** (execute-then-extract).

The traditional approach is "generate task + generate the gold answer," but an LLM-generated answer
hallucinates and you cannot verify the entities it invented are real. This paradigm inverts that:

```
Generation stage:   produce only prompt + available tools, NEVER produce ground-truth
  ↓ (entity hallucination allowed; don't worry about truth yet)
Execution stage:    a strong model actually rolls the task in the real environment
  ↓ (unfindable entity → model can't answer → answer is empty / contains "not found")
Extraction stage:   extract atomic facts as ground-truth ONLY from tasks that produced a real answer
  ↓ (empty answers / failure markers / too-few-facts tasks are discarded)
Survivors:          entities are guaranteed real (verified by tools), trajectory complete, answer checkable
```

Why the three gates matter: **entity realness is not guaranteed at generation time; it is enforced
by execution + filtering that auto-discards.** This directly answers the fundamental worry — "you
swapped in a different entity, does it actually exist in the environment?" — the ones that don't
exist get filtered out, so you don't have to police it. One strong model can do generation, rolling,
and extraction throughout.

## When this paradigm applies

- The final answer is **free text** and a judge model rates it (no exact target to hit).
- Your tasks depend on **external real-world state** (web pages, APIs, a filesystem), so entities
  cannot be fabricated and must be verified by execution.

If scoring is deterministic (state hash, assertion, exact/substring match), use paradigm B instead —
you cannot "roll first and see," because there is nothing to roll against until the gold exists.

## A caveat about self-scoring (be honest about what the ground-truth proves)

The claims are extracted from the model's *own* rolled answer, so scoring that same batch of answers
against them is essentially **self-scoring** and skews high. This can **only filter out the few
samples where claim and answer are mutually inconsistent; it cannot verify objective correctness of
the answer.** For SFT (which just needs successful trajectories) that's fine; to use it as a serious
benchmark for *grading other models*, add human spot-checks or a separate evaluator.

Understand the judge you're targeting: a judge model decides, claim by claim, whether the answer
covers that claim (fulfilled=1.0 / partial=0.5 / not=0.0), averages to a coverage_score, and ≥0.75
passes. Your extracted claims should match that style: single sentence, key numbers/dates/names,
independently verifiable.

## Pipeline: five stages

Scripts live under `<benchmark>/eval_scripts/synth/`.

| Stage | Output | What it does | Reference script |
|---|---|---|---|
| 0. dump inventory | `env_inventory.txt` | Export the fixed file list in the container (for local-resource tasks) | `0_dump_env_inventory.sh` |
| 1a. extract templates | `templates.json` | Extract "skeleton + quota" from reference tasks | `1_extract_templates.py` |
| 1b. generate candidates | `candidates.csv` | Strong model swaps entities per template to make prompts | `2_generate_tasks.py` |
| 2. roll trajectories | `roll_result.csv` | Strong model actually executes in the real environment | reuse the benchmark's completion script |
| 3. extract + filter | `synth_tasks.csv` | Extract claims from real answers, filter empties | `3_build_dataset.py` |
| 4. convert to SFT | `sft.jsonl` | Convert to training format | reuse the benchmark's convert script |

### Stage 0: dump the environment inventory (only for local-resource tasks)

If the benchmark has tools operating on fixed files, export the real inventory first:

```bash
cid=$(docker ps -q --filter ancestor=<env-image> | head -1)
docker exec "$cid" find /data -maxdepth 3 > eval_scripts/synth/env_inventory.txt
```

### Stage 1a: extract templates

Read the reference task set; parse each task into one template:
- `ref_task_id` / `enabled_tools` (inherited verbatim) / `servers`
- `prompt` (original, as an example for the generator)
- **atomic_actions**: the ordered `(tool_name, arguments)` sequence pulled from the reference
  trajectory — this is the task's "skeleton," telling the generator "which tools, and which entities
  fill which slots."
- `gtfa_claims` (original, so the generator sees what a "good answer" looks like).

**Quota allocation (weighted by server rarity)**: common servers (used by many reference tasks) get
more generations; rare servers get fewer. But note — **cap the quota**: if one template uses several
rare servers, the weights stack and blow up out of control. Use `--quota-cap` (e.g. 45) to bound the range.

### Stage 1b: generate candidate tasks

For each template, use the strong model to generate N candidate prompts. Hard constraints in the
system prompt:

1. **Keep the same toolset/difficulty**; don't introduce a tool the reference didn't have.
2. **Swap entity/parameter + change wording**; no trivial rewrites.
3. Make entities plausibly real and discoverable (truth is enforced by stage 2, so no pre-validation
   here — saves a layer of code).
4. Prompt must be **self-contained** — the solver is instructed to never ask the user for
   clarification, so the task must contain every needed detail.
5. Ask for a **concrete, checkable final answer** (number/date/name/difference).
6. Maximize **diversity** across candidates (different entities, different domains).

**Special case for local-resource templates**: when a template uses a local filesystem-type server,
inject `env_inventory.txt` into the system prompt and append the constraint "do not invent paths;
vary only the question over real files in the inventory."

> Generation, rolling, and extraction can all use the **same strong model** — no need to mix models.

### Stage 2: roll trajectories (the "execute" of execute-then-extract)

Reuse the benchmark's existing completion / agent-loop script, feed in `candidates.csv`, and run it
with the strong model. Produce a result CSV with the full trajectory (`raw_conversation_history`)
and final answer (`script_model_response`).

**This is the crucial closed loop of the method**: tasks whose entity can't be found → the model
can't reach a definite conclusion → answer empty / contains "not found" → discarded in stage 3.
Realness is enforced automatically here.

**Budget time for environment wiring, not just data quality.** Tool-use environments have runtime
gotchas (system-proxy interception of local calls, servers whose User-Agent gets rejected by target
sites, stale connections after a container restart, individual servers that time out on complex
queries). Nearly every one first *looks like* "the synthetic data is low-quality" when in fact the
environment isn't wired up. Before a full run, sanity-check the plumbing: confirm a single task rolls
end-to-end and returns a real answer. Two recurring lessons: (a) if local service-to-service calls
fail while a direct `curl` succeeds, suspect a system proxy and bypass it for localhost; (b) drop or
isolate any server that reliably times out rather than letting it stall whole batches.

### Stage 3: extract claims + filter (the "extract" of execute-then-extract)

For each task that produced an answer, use the strong model to extract 3–6 atomic-fact claims from
`prompt + final answer` (matching the benchmark's existing claim style: single sentence, including
key numbers/dates/names, independently verifiable).

**Two filter gates**:
1. **Answer validity**: empty/too-short (<20 chars) → drop; contains a failure marker (`not found` /
   `does not exist` / `无法找到` etc.) → drop.
2. **Claim count**: fewer than a threshold (e.g. 3) claims extracted → drop (the answer lacked enough
   checkable facts).

**Engineering note**: extraction is an independent LLM call per task, so it **must be concurrent +
flush-per-row** (`ThreadPoolExecutor` + flush). Serial is unusably slow. Flush-per-row also gives you
resume for free.

### Stage 4: convert to SFT

Reuse the benchmark's convert script to turn `(prompt, trajectory, tool definitions)` into SFT
messages format.

**A self-consistency insight about tool definitions** (to avoid deleting data by mistake): every tool
the model actually called is guaranteed to have a definition in the final tools field. Because of the
containment: **tools the model can call ⊆ servers actually deployed online ⊆ the full tool-definition
snapshot.** A reference task's `ENABLED_TOOLS` may list tools the environment never deployed (the
benchmark assumed them; your environment didn't bring them online); the convert script silently
ignores those undefined tools (only a warning) — **this is harmless, do not drop samples over it.**

## Quick start (end-to-end, worked example: MCP-Atlas)

The commands below are the concrete MCP-Atlas implementation of this paradigm — a real LLM-judged
tool-use benchmark. Treat it as a filled-in template: the stage structure transfers to any benchmark,
only the script names / service commands change.

```bash
# Prereq: start environment + completion service (always add NO_PROXY when a system proxy is on)
make run-docker                                                    # environment container
NO_PROXY="localhost,127.0.0.1" make run-mcp-completion            # agent-loop service

cd services/mcp_eval
export LLM_API_KEY=sk-xxx

# 0. dump the environment inventory (needed for local-resource tasks)
bash eval_scripts/synth/0_dump_env_inventory.sh
# 1a. extract templates (with a quota cap)
uv run python eval_scripts/synth/1_extract_templates.py --quota-cap 45
# 1b. generate candidates (drop --limit for a full run; resume supported)
uv run python eval_scripts/synth/2_generate_tasks.py --output eval_scripts/synth/candidates.csv
# 2. roll (always add NO_PROXY; resume supported)
NO_PROXY="localhost,127.0.0.1" uv run python mcp_completion_script.py \
  --model "openai/GPT-5.5" --input eval_scripts/synth/candidates.csv \
  --no-filter --concurrency 5 --output synth_roll.csv
# 3. extract claims + filter (concurrent + flush-per-row)
uv run python eval_scripts/synth/3_build_dataset.py \
  --roll-result completion_results/synth_roll.csv \
  --output eval_scripts/synth/synth_tasks.csv --concurrency 8
# 4. convert to SFT
uv run python convert_csv_to_sft.py --input <merged>.csv \
  --tools ../../list-tools.json --output training_data/sft.json --system-prompt
```

**Always smoke-test first** (`--limit 2 --per-template 5`): run all five stages, inspect the outputs
by hand, then go full. In the smoke test, spot-check: is the prompt self-contained? are entities real
(manually look up 2–3)? did the trajectory actually call the right tools? does each claim match the
answer?

## Reference scripts

See the reference scripts under `services/mcp_eval/eval_scripts/synth/{0_dump_env_inventory.sh, 1_extract_templates.py,
2_generate_tasks.py, 3_build_dataset.py}` as directly adaptable templates. This paradigm provides
methodology only; the executable scripts vary with each benchmark's interface.

## Don't forget the overriding principle

Even in paradigm A, **distribution alignment** (see the main SKILL.md) still governs quality. The
quota-by-server-rarity allocation in stage 1a exists precisely so your candidate distribution across
servers/tools matches the reference set rather than over-representing whichever templates are easiest
to generate. After generation, diff your candidate histogram (tasks per server, tools per task)
against the reference set and treat large gaps as bugs.
