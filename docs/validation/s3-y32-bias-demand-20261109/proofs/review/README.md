# Next-bias demand independent review

Status: RTL review passed; all existing regressions and the final independent dedicated schedule replay passed. No actionable findings remain.

## Scope

Reviewed the SRAM-only request scheduling change in `LinearAutoGroupCore.scala` and regenerated `LinearAutoGroupCore.sv`. Frozen before/after hashes and exact diffs are in `sourcepairs.json`, `LinearAutoGroupCore.scala.diff`, and `LinearAutoGroupCore.sv.diff`.

The change adds no register, SRAM, or FIFO storage. It requests `produced + 1` only while active, running, after `takeBias`, and before group 31. The compute selector and `biasReady` comparison continue to use the current produced group. The manual and register-cache branches are unchanged. The INIT assertion now also checks tag ownership.

## Ownership and boundary conclusions

- `groupReqReady` remains false while the current `wantedPending` demand is held. Its `groupTake` edge is the actual MAC INIT sampling edge. Excluding `takeBias` from lookahead leaves the current bias and tag intact until that edge completes.
- During RUN, changing wanted bias is safe because the MAC samples bias only in INIT. At enqueue, incrementing `produced` makes the already accepted next demand the current group.
- A demand fill may finish in either tagged slot. Existing prefetch always targets the slot opposite the current hit, and a future demand cannot replace a still-owned current demand. No slot allocation policy was modified.
- Under a full output FIFO, `launch` remains disabled. The current next demand and its speculative successor can occupy both cache slots without initiating a third MAC or changing FIFO head ownership.
- The `produced < 31` bound is essential: it prevents truncating next group 32 to tag 0. The final take leaves no required demand, allowing the next row, manual computation, and real clear.
- Reset invalidates pending demands and slot validity without claiming physical SRAM clear. The change adds no state that needs an additional reset rule.
- Host reads still use the original alternating memory arbitration. Earlier demand can change read latency but does not bypass the existing fairness, response, or clear rules. Runtime writes/configuration changes remain prohibited by the wrapper and scheduler assertions.

## Corrected launch interval analysis

The expected continuous launch interval is baseline 69 versus candidate 68 clocks, a net **one-clock** improvement between groups. If launch is edge L, done/enqueue occurs at L+67. The candidate can launch at L+68; the original scheduler first accepts its next demand at L+68 and launches at L+69. The request and launch edges must not both be counted as extra delay. An earlier informal two-clock/6,138-cycle estimate was incorrect. The simple per-layer bound is 31 x 99 = 3,069 clocks, and SoC backpressure can hide some of it.

## Independent existing regressions

All passed on candidate installed SV SHA `7d3c0f9acb6adc19c65c35360f9595fd625a68764560322c1fd3900cb650f18a`:

- Autogroup: two rows / 64 groups, numeric lanes, retirement backpressure, manual return and reset.
- Cached/manual: original cached and noncached starts and group 0/31 behavior.
- READY: descriptor/error/timeout/reset unit coverage, real MAC numeric bounds and ties, bundle/commit/write/completion backpressure, old POP race.
- Bias SRAM: 8,192 masks, host responses/arbitration, true clear, reset retaining memory, runtime write protection.
- Capability: real SRAM and real generated register-cache variants; SRAM advertises `42530001` and performs clear; register variant advertises zero and completes unsupported clear with an error.

`existing-regression-receipt.json` records four regression commands and before/after source hashes (`source_drift=[]`). `capability-receipt.json` and `capability/*/inputs.json` record both capability variants. The cached test initially passed with an unrecognized optional raw-log variable, so a second documented replay uses the correct `XU_WRAPPER_LOG_DIR` to preserve its raw log; see `cached-rawlog-receipt.json`.

## Dedicated test review

The final real scheduler test observes each accepted demand exactly once for tags 0..31, requests tags 1..31 during the post-INIT RUN window, verifies exact INIT tag/bias stability and full MAC results, stops the producer under full FIFO, checks no final demand blocks clear, repeats adjacent rows with replaced biases, resets INIT / accepted lookahead / full-FIFO state, and returns to manual START. It uses actual SRAM uploads and MAC completion, without forced data or mocked done.

The required log directory was identified as a test integration defect and changed to an optional temporary directory. The baseline comparator checks the frozen old SV SHA, rather than reading the main tree after integration. Failed preliminary test logs are preserved by the implementation agent.

Independent replay passed both frozen baseline and candidate: 7 rows / 224 groups each, exactly 32 demands/launches/takes/dones per row; candidate 31 early RUN demands versus baseline 0; six continuous rows each show 68 versus 69 clocks. Both variants execute 3 reset windows, a real manual cached computation, and 768 physical zero writes at sequential addresses followed by a new valid row. The phase-2 candidate reset explicitly requires an outstanding SRAM return. `schedule-independent-receipt.json` records full source/test pins and `source_drift=[]`; `schedule-independent/summary.json` and raw logs retain the independent result.

No synthesis, official flow, or main-workspace edits were performed by this reviewer.
