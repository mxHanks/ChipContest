# Next-bias demand: isolated implementation and scheduler verification

The SRAM implementation of `LinearAutoGroupCore` now presents the next bias demand during the current MAC RUN period. The request is allowed only when `active && running && !takeBias && produced < 31`; its tag is `produced + 1`. The compute group's selection still uses `produced`, and its INIT edge still consumes the original demand one edge after compute launch. The pending handshake prevents duplicate acceptance. The last group cannot wrap to tag 0. The manual path and register-cache elaboration do not use the lookahead condition.

The existing SRAM module, compute core, CPU, bus, firmware and numerical model were not changed by this subtask. The additional take assertion checks both valid and exact tag. This implementation was made only inside `prototype-repo`; the root agent owns integration and SoC campaigns.

## Generation

Command, run once from `prototype-repo`:

```sh
scala-cli run . --server=false --jvm system -M GenerateRTL -- LinearAutoGroupCore
```

`generate-command-01.json`, `generate-01.log`, and `generated-hashes-01.json` record the invocation and comparison. Only `LinearAutoGroupCore.sv` changed; the other 11 generated dependency files are byte-identical. Only that top was copied into the isolated E203 installation. Final top SHA256 is `7d3c0f9acb6adc19c65c35360f9595fd625a68764560322c1fd3900cb650f18a`.

## Real RTL schedule test

The new `tb_bias_demand_schedule.sv` instantiates the generated top and its actual SRAM/MAC dependencies. All W, X and bias data are uploaded through the real ports, and an independent signed64 multiply-add oracle checks every result. No force, backdoor memory initialization or mock done signal is used.

The same testbench is compiled once against the candidate and once against the SHA-pinned original top from the frozen packed-clear campaign. `schedule-run4` passes both versions:

- Seven complete rows, 224 groups per version, including adjacent rows with changed bias and all 32 exact ordered demand/launch/take/done tags.
- In each candidate row, exactly 31 next-group demands are accepted while RUN is active, two edges after the preceding launch and after its INIT take. Bias data is unchanged from launch through the real INIT sampling edge.
- Original launch interval 69 edges; candidate interval 68 edges. Both assert MAC done at launch + 67. The removed request handshake bubble is **one edge per inter-group transition**. The earlier two-edge hypothesis was incorrect.
- Two-slot FIFO backpressure retains the head, stops the producer at two results, and resumes without a duplicate or missed tag.
- Resets at INIT, after an accepted lookahead with an outstanding SRAM return, and with full FIFO/pending demand. Fresh rows after each reset pass.
- After final group 31 and its POP, no wanted demand remains. A ten-edge quiet interval rejects any wrapped tag-0 request, and real clear readiness is checked.
- A subsequent real clear writes all 768 SRAM words in exact address order with zero data before done. Refresh, manual cached START, and another full row then pass.

The Python runner accepts an optional persistent log directory. Without it, temporary logs are cleaned automatically. Optional baseline replay requires the original exact RTL SHA `ebc9c411a6318000369f6c466381767a469bb9d33454e4c955df713c728f9ab4`.

## Preserved diagnostics

- `schedule-run1`: compile failed because firtool eliminated the unused `io_groupReqReady` port. The test now observes the real internal `groupFire` handshake. No production edit was needed.
- `schedule-run2`: both real simulations passed, but Python expected a two-edge improvement. RTL edge analysis and both traces prove one edge; the final expectation was corrected.
- `schedule-run3`: the candidate passed, but the selected baseline filename referenced the parent tree after the root agent integrated the candidate. The test correctly rejected its RUN-time request under baseline semantics. The final run uses the frozen campaign top and pins its SHA.

These failures remain intact and are not counted as passing evidence. No synthesis, area, timing or energy conclusion follows from this scheduler verification. The root agent's independent single-layer/full12 campaigns determine actual end-to-end benefit.
