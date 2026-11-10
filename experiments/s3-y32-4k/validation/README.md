# Isolated DMA64 / real-CPU validation

This directory owns only validation inputs. It never installs experimental RTL
in the production checkout. The runner freezes all actual RTL, firmware,
testbench, observer, vectors and executable identities in a fresh output folder.
No experiment may start after `2026-11-10T15:59:00Z` unless a later deadline is
explicitly supplied following renewed user authorization. No push is performed.

The exact operation remains signed16 X/W, signed40 bias, signed48 MAC and final
RNE(acc/512) Y32. Source layout is unchanged: X one low16 per32-bit slot, W two
INT16 per32-bit word, bias one signed40 per64-bit sign-extended source slot.

| DMA64 traffic/task | Accepted requests | Retired responses |
|---|---:|---:|
| W source reads | 4096 | 4096 |
| Bias source reads | 256 | 256 |
| X source reads | 3168 | 3168 |
| Y32 pair writes | 12672 | 12672 |
| Total | 20192 | 20192 |

Each task checks25344 independent Y32 words. All12 check304128. One-row mode
uses the same DMA64, endpoint, arbiter, source files and firmware with CTRL=2;
eight-row uses CTRL=0x802. Pure MAC-step expectations are202752 and26624,
respectively; group pops remain3168. These are logical expectations, not measured
full-task performance. The full12 target is at most450000 clear-inclusive cycles.

The real endpoint is `xu_shared_icb_sram64`, using256 physical RAMSP1024X16
instances and the existing non-PPA functional SRAM model. Both CPU32 and DMA64
pass through `xu_dma64_shared_arb`; no ideal DMA response path is substituted.
The test host uses a public host32 ingress for source/poison writes while the
real CPU waits for fixture-ready, and for output readback after the task ACK. It writes X/W/bias, poisons Y and reads Y back
through accepted/retired public transactions. Neither task tensors nor outputs
are assigned through a hierarchical memory-array backdoor. The established ELF
ITCM boot preload remains the sole program-load exception and is explicitly
outside payload timing; golden data stays in checker-owned arrays.

`dma64_main.c` adds public HOST[6] ready(call+1) to the old HOST ACK contract.
Each task waits for its own ready sequence before physical clear and descriptor
submission. Host transfer/readback is excluded from payload, but no task data
becomes visible by unobserved private writes. No next fixture may replace data
until the preceding task's Y responses and CPU ACK have retired.

Reusable read-only CPU hierarchy below assumes the top instance is `dut`:

- MAIN: `dut.u_e203_subsys_top.u_e203_subsys_main`
- CPU: MAIN.`u_e203_cpu_top`; real CPU reset: CPU.`u_e203_cpu.rst_core`
- EXU: CPU.`u_e203_cpu.u_e203_core.u_e203_exu`
- retirement: EXU.`u_e203_exu_commit.alu_cmt_i_{valid,ready,pc}`
- completion return code: EXU.`u_e203_exu_regfile.rf_r[3]`
- DMA: MAIN.`u_e203_subsys_perips.u_xu_matrix_dma`; CORE: DMA.`u_core`
- ITCM boot only: CPU.`u_e203_srams.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram.mem_r`

The core agent retains eight logical W banks/two1024x16 macros each, bias
`memory.mem_ext`, eight `engines_r` with the original PE ACC/resultReg, two sets
of eight `xs_s_r`, and `results_slot_row_lane`. Packed X writes use split even/
odd32-entry vectors; physical clear still writes every logical X address. The
read-only physical observer must check16384 W addresses,768 bias addresses and
1024 X addresses, plus64 ACC,64 engine results,128 FIFO values,16 bias-cache
values and DMA assembly/snapshot payloads. A public warmup supplies dirty state
before all counted tasks. Observer generation waits for actual generated RTL
names; a name assumption must not silently remove coverage.

Principal cycles span first source VALID through final Y response inclusive,
plus the physical-clear request through clear-done inclusive. Clear-to-source
gap is reported separately and in a second total. HF wall clock counts timing;
transaction and physical SRAM observation use the exported common fabric clock.
150MHz is a development stimulus/conversion, not a new STA or PPA result.

Integration order: source/IO preflight without unknown-RTL rebuilds; one task
exactness with public fixture transfer; complete12 with warmup and physical
clear; same-source one-row control; first-source delay/response backpressure and
failure-boundary cases; strict log parser negative tests. All prior failures and
interrupted attempts remain in distinct evidence folders.

## Reproducible local entry point

Run from the repository worktree root:

```sh
python3 -B experiments/s3-y32-4k/validation/run_cpu.py \
  --out build/parallel4k-20261110/cpu-task0-NEW \
  --tasks 1 --rows 8 --warmup --jobs 2
python3 -B experiments/s3-y32-4k/validation/run_cpu.py \
  --out build/parallel4k-20261110/cpu-full12-NEW \
  --tasks 12 --rows 8 --warmup \
  --replay-from build/parallel4k-20261110/cpu-task0-NEW
```

A fresh task0 freezes the current candidate checkout, not the published16PE
checkout. Replays inherit exact source, firmware/image and simulator hashes.
`--rows 1` selects the same-source8PE single-row control. Add
`--first-source-stall 31` to exercise the first-source VALID timing boundary.
The seven-cycle throttle is implemented in the actual endpoint (one stall per7
cycles), not as an ideal response sink. Different throttle configuration needs
a new build, not a runtime plusarg change. All commands enforce the stated
November10 deadline before new builds and simulation starts.

`check_results.py` separates functional correctness from performance selection.
The4k gate requires all12 counted tasks, every layer at most37,500 principal
cycles and sum at most450,000, including physically written clear. The runner
also independently enforces the per-layer gate when replaying an earlier
parser snapshot. The150MHz arithmetic remains unqualified until actual STA.
`test_check_results.py` contains two valid-evidence cases and15 invalid-evidence
cases; it refuses missing or malformed records, early completion, omitted
clear, wrong counts, missing public readbacks, an incorrect clock, or a12-layer total that hides one over-budget layer.

## Completed evidence before final R2 rebinding

`build/parallel4k-20261110/cpu-full12-r1` completed all304,128 counted Y32
values by both accepted DMA writes and subsequent public32-bit reads. Its
principal total is428,915 cycles: payload416,579 plus actual clear12,336.
Clear-to-source gaps total516 separately; including gaps429,431.
Individual principal cycles are35,742 for layer0 and35,743 for layers1..11.
The corresponding assumed150MHz conversions are4,196.636 and4,191.593 task/s.
An additional public warmup task0 is checked and excluded from those totals.
This R1 source predates the independent error-code classification correction;
R2 must bind the final corrected source to new CPU evidence before selection.

The same R1 binary passed the one-row control (224,994 principal cycles) and
31-cycle forced initial source stall (35,772 principal cycles). These are
single-task controls, not substitutes for complete12 evidence. No PPA/STA or
formal eligibility claim follows from these simulations.

`audit_run.py` checks the completed report, every frozen source, all vectors,
ELF/image and simulator hashes, the42 pinned CPU-core files, and reparses raw
logs through the current strict selector. Audit output is a new file; neither
original measurements nor frozen source are rewritten. Example:

```sh
python3 -B experiments/s3-y32-4k/validation/audit_run.py \
  build/parallel4k-20261110/cpu-full12-r1 \
  --baseline build/parallel4k-20261110/goal-baseline.json \
  --out build/parallel4k-20261110/another-read-only-selection-audit.json
```

Replay preflight rejects a throttle or simulator differing from the parent's
compiled executable before creating a new experiment output. Changing rows,
task count, warmup or first-source wait remains a runtime experiment. The
separate `test_replay_preflight.py` verifies allowed and rejected arguments
without running a simulator. Existing R1/R2 replays all requested7 and used the
actual frozen `D4K_THROTTLE=7` build; their original receipts stay unchanged.

## Final R2 CPU evidence

`cpu-full12-r2` nowPASS:304,128 exactY32; principal428,915 cycles,
physicalclear12,336, gap516, includinggap429,431. Everylayer35,742/35,743
is<=37,500. Firmwareinterval429,720. Assumed150MHz conversions4196.636,
4191.593 and4188.774task/s respectively. ActualSTA remains unverified.
`cpu-row1-r2` and `cpu-source-stall31-r2` pass with224,994/35,772cycles,
sharing the exact finalRTL/ELF/image/executable (SHA6d73aa52...1393b).
Independent review and golden recalc live in `independent-audit-r1`.
