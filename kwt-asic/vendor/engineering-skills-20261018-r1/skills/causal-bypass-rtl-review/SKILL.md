---
name: causal-bypass-rtl-review
description: Review or validate RTL optimizations that bypass, skip, mask, suppress, early-exit, or fast-path work in a ready/valid pipeline. Use for causal-mask bypasses, all-masked tiles, discarded transactions, counter-preserving skips, or equivalent control-path optimizations in Verilog/SystemVerilog. Do not use for unrelated general RTL style review.
---

# Causal Bypass RTL Review

Review the bypass as a protocol transformation, not merely as a mux or performance shortcut. The optimized design must suppress only unnecessary data-plane work while preserving externally observable behavior and required bookkeeping.

## Establish the contract

Inspect the implementation, instantiation parameters, producer/consumer interfaces, focused testbench, integration tests, counter contracts, and any golden/reference model. Run `python scripts/scan_bypass_surfaces.py <project-root>` when relevant logic is distributed across the repository.

State explicitly:

- the exact bypass predicate and the cycle on which it becomes known;
- what work is suppressed;
- what state, handshakes, queues, coordinates, counters, and output obligations still advance;
- behavior when the optimization is disabled;
- reset, clear, abort/flush, end-of-frame, and backpressure semantics;
- the equivalence oracle: output bytes, ordered transactions, numerical tolerance, protocol assertions, counter equations, or a combination.

Do not infer "fully masked" from a partial sample unless the implementation has consumed or otherwise proven the complete required unit.

## Review in dependency order

Read [references/review-checklist.md](references/review-checklist.md) for the full checklist.

1. Qualification: prove the predicate cannot fire early, late, or on a boundary/diagonal/partially valid unit.
2. Ownership: identify which stage owns dequeue, coordinates, row/tile completion, last, error, and counters.
3. State progression: compare bypassed and normal paths for every state variable that must advance.
4. Handshake safety: check stable payload under stall, no combinational ready/valid loop, no double accept, no dropped drain.
5. Output invariants: preserve output count/order/metadata or explicitly prove that no output is owed.
6. Accounting: derive expected counter deltas and conservation equations.
7. Recovery: exercise reset, clear, abort, protocol error, and mode changes near a bypass decision.
8. Equivalence and performance: prove functional equivalence first; measure saved work separately.

When assertions would materially improve confidence, read [references/assertion-patterns.md](references/assertion-patterns.md). Adapt patterns to the actual clock/reset and sampling semantics; they are not drop-in code.

## Required tests

Prioritize a compact but discriminating matrix:

- bypass disabled;
- no eligible unit;
- exactly one eligible unit;
- first, middle, and final eligible units;
- diagonal/boundary and partially masked unit;
- consecutive eligible units;
- randomized upstream and downstream backpressure;
- reset/clear/abort immediately before, during, and after eligibility;
- minimal and non-multiple dimensions when parameters allow them;
- counter overflow/width assumptions for full workload;
- reference comparison between optimized and non-optimized paths.

Use self-checking TBs. A waveform screenshot is supporting evidence, not acceptance evidence.

## Report or fix

For a review request, return findings first with precise file/line evidence, severity, violated invariant, and a minimal reproducer. Do not modify code unless asked.

For a fix request, change the smallest ownership point that restores the invariant. Run the focused TB first, then the narrowest affected integration/numerical checks. Interface or hierarchy changes also require elaboration or OOC evidence. Clearly distinguish `PASS`, `FAIL`, `NOT RUN`, and tool/environment blockers.
