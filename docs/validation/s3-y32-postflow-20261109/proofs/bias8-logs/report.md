# Independent bias SRAM streaming experiment, 2026-11-08

## Result

8 PE + direct drain8, layer 0: development PASS, 25,344 exact Y32 outputs.

| Metric | 8 PE direct baseline | Streaming bias candidate | Delta |
|---|---:|---:|---:|
| Payload cycles | 453,259 | 451,866 | -1,393 (-0.3073%) |
| Physical parameter clear | 198,403 | 198,403 | 0 |
| Payload + clear | 651,662 | 650,269 | -1,393 (-0.2138%) |
| Compute-wait phase | 24,552 | 22,770 | -1,782 |
| Writeback phase | 193,252 | 193,641 | +389 |
| Shared stall | 14,122 | 14,511 | +389 |
| Status polls | 5,049 | 4,752 | -297 |
| Result MMIO reads | 0 | 0 | 0 |
| NICE requests/responses/retirements | 3,168 each | 3,168 each | 0 |
| Direct snapshots/POPs | 3,168 each | 3,168 each | 0 |
| Y32 shared writes | 25,344 | 25,344 | 0 |

The reduction in local fill latency is mostly hidden by the original overlap. This is a small positive candidate on 8 PE; it does not establish a benefit for a combined 16 PE design or an area/energy benefit.

Baseline: `build/writeback-v2-20261108/direct-full12/result.json`, layer 0. Candidate: `build/postflow-20261108/bias8-task0/result.json`. Candidate `source_drift=[]`; loaded firmware image identical. ELF differs solely in non-loaded `.strtab` (flags 0), with every other ELF section identical; see `elf-section-comparison.json`.

## Mechanism

Only `groupFill` changes. A separate `groupStream` state issues 24 SRAM reads on consecutive edges, and captures the one-cycle synchronous response while issuing the next read. The final drain edge receives word 23 and publishes the slot only after all 24 words are present. Each uncontended fill uses exactly 25 stream cycles, versus 24 issue/capture pairs (48 cycles) before.

An issue index, a return index, and a return-valid bit track the one outstanding synchronous pipeline stage. An invalidate or obsolete fill epoch suppresses a new memory issue and discards the outstanding return, then retries the existing accepted demand from IDLE. Host reads/writes, byte masks/RMW, descriptor capture, response backpressure, host/fill grant alternation, group ownership, and physical clear semantics retain their original logic. The single 1024x16 1RW memory and 24 physical reads per group are unchanged. The extra control register count is six bits before synthesis; no mapped area claim is made.

Generated from the repository's cached Scala 2.13.18 / Chisel 7.16.0 / CIRCT firtool 1.160.0 configuration. All 11 other generated SV dependencies have identical hashes; see `generated-hashes.json`.

## Validation

1. `tests/e203/test_bias_sram_wrapper.py`: PASS. Exhaustive 8,192 byte masks over 256 entries, real asynchronous ICB wrapper and memory, read/write overlap, held responses, reset-retains-memory, runtime write protection, clear. Raw `wrapper-test.log` and `wrapper/`.
2. New `tests/e203/test_bias_group_pipeline.py` + SV: PASS. All 32 tags and signed40 endpoints, exact 24 sequential reads without issue bubbles, exact 25 stream cycles per complete fill, stable group payload while the next group prefetches, host response backpressure, host/group progress, runtime write rejection, full 768-word clear. Invalidate and reset each tested at 25 boundaries (before issue0, then each of 24 synchronous return stages). No force or memory preload. Final marker:
   `BIAS_GROUP_PIPELINE_PASS tags=32 words_per_fill=24 stream_cycles=25 invalidation_stages=25 reset_stages=25 complete_fills=149 physical_reads=4180 clear_words=768`.
3. Existing `linear.BiasSramPrefetchTest`: PASS. Exhaustive mask/readback, response retirement with new command on same edge, group snapshots, accepted-demand retry under invalidation, legal host update invalidating prefetched next tag, epoch preservation for rejected writes, reset retains storage, all-entry physical clear and all-tag readback. See `chisel-test.log`.
4. Canonical layer 0 fresh-process CPU/RTL campaign: PASS with Verilator `--assert`, 150 MHz clock stimulus, external pad double-reset profile, original integer golden output checks. See `../bias8-task0/task-00/simulation.log` and `result.json`.

An initial new-test run failed due to the test driving reset/host command and checking ready in the same simulator delta; the original log is retained as `group-test.log`. A one-time `#1` settle after descriptor drive corrected the testbench. No RTL change was required. `group-test2.log` and the final Python-runner logs pass.

Verilator results are 2-state development evidence with vendor SVA disabled and Chisel procedural assertions enabled. No synthesis, SRAM macro mapping, STA, power analysis, VCS, gate simulation, or official qualification was run. Physical zero of result-FIFO payload remains the pre-existing unproven policy item; the campaign reports this explicitly.

## Reproduction

Within `build/postflow-20261108/bias8-repo`:

```bash
scala-cli run . --server=false --jvm system -M GenerateRTL -- LinearAutoGroupCore
python3.12 -m unittest discover -s tests/e203 -p test_bias_sram_wrapper.py
python3.12 -m unittest discover -s tests/e203 -p test_bias_group_pipeline.py
scala-cli test . --server=false --jvm system --test-only linear.BiasSramPrefetchTest
python3.12 -E -B tools/ppa/s3_task_campaign.py \
  --repo /home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/postflow-20261108/bias8-repo \
  --out /home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/postflow-20261108/bias8-task0 \
  --bias-kind sram --schedule bias-hw-autogroup-y32-packed16-nice-direct-window \
  --simulator verilator --cross-prefix /usr/bin/riscv64-unknown-elf- \
  --platform-clocks 150mhz --startup-profile external-reset --layers 0
```

Generation first emits to `generated/LinearAutoGroupCore`; the checked installation copies only `BiasSramPrefetch.sv` to the E203 perips directory after verifying the remaining generated modules are identical. Use a fresh campaign output path when reproducing.

`changed-files.json`, `bias-prefetch.patch`, and `source-hashes.json` identify the exact four deliverable files. No commit or main-tree edit was made by this subtask.
