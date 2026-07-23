---
name: tool-use-data-synthesis
description: >-
  Synthesize training data for ANY tool-use / agentic benchmark, in ANY repo. Given a handful of
  runnable reference tasks, produce thousands of "same-distribution, different-entity" tasks, roll
  out real trajectories, and emit SFT, RL data. Use this when: you have a tool-calling / MCP / agentic
  benchmark and want to expand a few dozen tasks into thousands of
  in-distribution training samples without changing the environment or tools; when synthetic data
  mysteriously LOWERS the benchmark score and you need to diagnose why; or when you must produce
  checkable ground-truth for agentic tasks and cannot trust an LLM to fabricate facts. The first
  decision is set by the benchmark's SCORING MECHANISM (rule-based vs LLM-judged), which picks one
  of two synthesis paradigms. The overriding principle throughout is DISTRIBUTION ALIGNMENT.
---

# Tool-Use Data Synthesis

## Overview

This skill is a **generic recipe** for synthesizing training data inside any **tool-calling
environment**, validated end-to-end on two very different benchmarks (one LLM-judged, one
rule-based). The
concrete goal: you have N runnable benchmark tasks and want to expand them into K×N "same-pattern,
different-entity" tasks, then roll out real trajectories for SFT.

What makes tool-use synthesis different from **plain-text QA synthesis**: the entities in a tool-use
task must **really exist in the environment and be reachable by the tools**, and the task must be
**scorable** by whatever mechanism the benchmark uses. You cannot swap in a book/repo/order that
doesn't exist — the task becomes unsolvable and the trajectory is garbage. And you cannot invent a
"gold answer" for free — how the benchmark scores decides *how* you must produce ground-truth.

Two things carry the entire skill. Internalize both before touching code:

1. **The scoring mechanism dictates the paradigm.** Read the evaluator FIRST. It splits the world in
   two (see the decision below). Choosing the wrong paradigm wastes days.
2. **Distribution alignment is the whole game.** Synthetic data that is *structurally simpler* than
   the target benchmark does not "clean up" the distribution — it **shifts** it, and training on it
   **lowers** the score. This is not a corner case; it is the single most common way tool-use
   synthesis silently fails. See "The overriding principle" below.

## The first decision: read the evaluator, pick the paradigm

Before generating anything, find and read the benchmark's scoring code. Ask one question: **is the
final reward computed by a deterministic rule, or by an LLM judge?** The answer picks the paradigm.

```
                      ┌─────────────────────────────────────────────┐
                      │  Read the benchmark's evaluator/scoring code  │
                      └─────────────────────────────────────────────┘
                                          │
            ┌─────────────────────────────┴─────────────────────────────┐
            ▼                                                             ▼
  Reward is RULE-BASED / deterministic                     Reward is LLM-JUDGED / free-text
  (DB-state hash, exact/substring match,                   (a judge model rates the answer,
   env-state assertions, unit tests)                        per-claim coverage, rubric score)
            │                                                             │
            ▼                                                             ▼
  PARADIGM B: construct-then-verify                        PARADIGM A: execute-then-extract
  Ground-truth must EXIST BEFORE the rollout               Ground-truth is EXTRACTED AFTER the rollout
  (you build gold actions/answer, then replay              (generate prompt only, roll it, then pull
   through the evaluator to self-check it scores)           atomic-fact claims from the real answer)
            │                                                             │
            ▼                                                             ▼
  → references/paradigm-b-construct-then-verify.md         → references/paradigm-a-execute-then-extract.md
```

Why this is the root fork, in one sentence each:

- **Rule-based evaluators score against a pre-existing target** (a target DB hash, an assertion over
  final device state, an expected string). You therefore must **produce the ground-truth up front**
  and prove it is valid by replaying it through the *same* evaluator interface at construction time.
  You cannot "roll first and see" — there is nothing to roll against until the gold exists.
- **LLM-judged evaluators score free-text answers**, so there is no pre-existing target to hit. You
  **roll first**, then extract checkable claims from the answer the strong model actually produced.
  Realness of entities is enforced by execution + filtering (unreal entity → empty answer → dropped).

A benchmark can even mix both across task types (e.g. one task type scored by DB-hash + substring,
another by env-assertions within the same benchmark). Classify **per task type**, not per benchmark.

Quick evaluator-reading checklist (do this for every new benchmark):
- What is the top-level reward function, and how does it combine sub-scores (product? mean? min?)?
- What is each task's `reward_basis` / enabled dimensions? Which sub-scores actually count?
- For rule-based: what exactly is compared — a state hash, a substring, an assertion function? Are
  read-only tool calls scored at all? (Often not — e.g. a benchmark may not score `calculate`/`get_*`.)
- For substring/text checks: is there normalization (lowercasing, comma-stripping)? That dictates
  number/string formatting in your gold (e.g. `1,234.5` must be emitted as `1234.5`).

## The overriding principle: align the distribution — to sub-type granularity

This principle governs **both** paradigms and is the highest-leverage thing in the skill.

Synthetic data must match the **structural distribution** of the target benchmark. A distribution
that is *simpler* than the target is not cleaner data — it is **distribution drift** that drags the
model toward an easier behavior and **lowers** the benchmark score.

Real, measured example (a rule-based retail-style benchmark, first synth version):

| metric | official base (114) | v1 synth (1000) | result |
|---|---|---|---|
| avg writes / task | 1.56 | 1.00 | |
| tasks with ≥2 writes | 39% | 0% | |
| tasks with communicate-info | 33% | 0% | |
| → benchmark effect | — | — | **score DROPPED** |

v1 taught the model a "find user → read one order → do one step → stop" distribution and drowned out
the compound operations and information-return the benchmark actually tests. The fix was to rebuild
the generator to hit the official structural stats (multi-write %, communicate %, tool mix).

But hitting the **top-level** stats is not enough. The second, subtler lesson: **align to sub-type
granularity.** After v1's fix matched avg-write and communicate-rate, the model still scored only
65.79% on base — because the official `communicate` dimension has **four sub-types** (amount-sum,
per-order amounts, item count, product attribute) and the official write-tasks include a
**pending+delivered mixed** case, and the synth had covered *none* of those sub-types. Top-level
metric parity ≠ real parity. Enumerate the sub-types the benchmark exercises and cover each.

Practical rule: **before generating, compute the target's structural histogram** (writes/task,
tool-type mix, communicate-type mix, multi-step %, mixed-mode %), and after generating, compute the
same histogram on your synth and diff them. Treat any gap as a bug.

## Diagnose from failures: let the benchmark tell you what data is missing

The most reliable way to know *which* distribution gaps matter is not to guess — it is to **train on
your synth, run the target benchmark, and read the failure analysis.** The failures ARE the data
requirements document.

The loop:
1. Train on the current synth; run the official benchmark; collect the failing tasks.
2. For each failure, read the reward sub-scores to see *which dimension* failed (a DB/state mismatch?
   a missing communicated value? a wrong tool choice?).
3. Cross-reference three things at once: **(a) the failure analysis, (b) the official base's
   structural stats, (c) what your generator currently produces.** The gap between (b) and (c) that
   also shows up in (a) is your next batch of data to synthesize.
4. Add exactly that distribution to the generator; re-verify at construction time; re-roll; re-test.

This "failure → gap → targeted synth" loop is how one rule-based benchmark went from a diagnosis of "three
missing sub-distributions" (mixed pending+delivered writes, count/attr/per-order communicate,
`calculate` usage) to a targeted generator fix — rather than blindly adding volume.

A caution when reading failures: **low pass-rate ≠ weak model.** First bucket failures by reward
sub-score and by task type. If simple task types pass at 90%+ while one type is at 0%, the culprit is
almost always a **task bug** (missing info in the prompt, an unsolvable entity), not model weakness.
(In one benchmark, address tasks scored 0% purely because the generated prompt omitted the `address2`/`Suite`
line the gold action required — the agent had no way to know it. Fixing the prompt took it to 100%.)

## What is common to both paradigms

Regardless of paradigm, these hold:

- **Vary entities/wording, never the tool skeleton.** A synthesized task must be solvable with the
  *same* toolset as its reference. No tool recombination — that changes difficulty and breaks
  same-distribution.
- **Tasks over fixed local resources cannot swap entities freely.** Tools like `filesystem`/`git`
  operate on files mounted in the environment; their "entity" is the fixed inventory under `/data`,
  not an arbitrary real-world thing. For these, **vary the question, not the path** — dump the real
  inventory first and force generation to range only over real files.
- **Self-contained prompts.** The solver is typically told never to ask the user for clarification,
  so every needed detail (full address incl. suite, every product option, exact target) must be in
  the prompt. A dropped detail = a guaranteed failure the model cannot recover from.
- **The evaluator-interface replay is the lifeline.** Whether you verify gold up front (B) or filter
  answers after (A), you must run through the *same* interface the real evaluator uses. Placeholder
  tool outputs will fail replay checks — use the environment's real tool responses.

## Paradigm references (read the one your evaluator selected)

| Reference | When | Core loop |
|---|---|---|
| [references/paradigm-a-execute-then-extract.md](references/paradigm-a-execute-then-extract.md) | LLM-judged / free-text answers | generate prompt → roll → extract claims from real answer → filter empties |
| [references/paradigm-b-construct-then-verify.md](references/paradigm-b-construct-then-verify.md) | Rule-based / deterministic scoring | build gold actions (block + compose) → replay through evaluator to self-check → phrase → roll |
| [references/operational-playbook.md](references/operational-playbook.md) | Both — read before any full run | capturing the exact API payload (messages/tools) as the only complete data, resume/checkpoint discipline |

## Quick start (both paradigms share this shape)

```
0.  Read the evaluator → classify each task type as rule-based (B) or LLM-judged (A).
1.  Compute the target benchmark's structural histogram (the alignment target).
2.  Build the generator for your paradigm:
      A: templates → generate prompts → (roll) → extract+filter claims
      B: entity samplers / blocks → compose → construct-time verify (replay)
3.  Smoke-test tiny (e.g. --num 300, no-LLM if possible): diff your synth histogram
    vs the target; run positive/negative construct-time checks; hand-inspect a few.
4.  Scale up; roll trajectories (mind the rate-limit ceiling; resume is your friend).
5.  Run the official benchmark; read failures; feed gaps back to step 2. (Failure-driven loop.)
```

**Always smoke-test before a full run.** For paradigm A, spot-check that prompts are self-contained,
entities are real (look up 2–3 by hand), and each claim matches the answer. For paradigm B, diff the
structural histogram against the target and confirm positive checks reward=1 / negative checks
reward=0 for **each** sub-type you generate.

## Resources

- `references/paradigm-a-execute-then-extract.md` — full 5-stage pipeline for LLM-judged benchmarks
  (templates → generate → roll → extract → convert), with a reference implementation.
- `references/paradigm-b-construct-then-verify.md` — full pipeline for rule-based benchmarks (block
  samplers, `compose_for_user`, construct-time replay verify, communicate/answer typing,
  distribution control), with a reference implementation.
- `references/operational-playbook.md` — cross-cutting operational hard-won lessons: capturing the
  exact `messages`/`tools` payload at the API call site as the only complete training data, and
  resume/checkpoint discipline.

This skill provides methodology; the executable scripts vary with each benchmark's interface. Adapt
the reference implementations named in each paradigm doc.
