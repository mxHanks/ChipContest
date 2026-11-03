# S2c local real1 screen evidence

This is a local development experiment, not S0 qualification, remote VCS, PPA, energy, score or retention evidence. Main implementation `4a6aa1ae7a8ddd5b0ede15dde9359b88b3656b11`, child implementation `dd149bb34aa1c3feca066ffbf9bdd3311f4b954c`. The independent branches/worktree start from the exact frozen S2b commits. The full contract and implementation description is in [xu-s2c-autogroup.md](../../xu-s2c-autogroup.md).

The screen compares old H1/H2 firmware `bias-hw-window`, S2b firmware `bias-hw-pack32-window`, and S2c firmware `bias-hw-autogroup-window`, all on this one S2c RTL and the same simulator binary. Every variant uses the original layer_00 tensors/golden, GCC `14.2.0+19`, `-O2`, `both-unroll-no-masks`, Verilator `5.032` and host g++ `15.2.0`. These are the actual local versions; this does not claim equivalence to the intended SiFive GCC 10.2.0 server screen.

The same seven frozen firmware schedules were separately rebuilt for default `-Os`/`none` and screen `-O2`/`both-unroll-no-masks`: all 14 loadable images are byte-identical to the S2b source. `legacy-firmware-images.tar.xz` retains both sides of every comparison, including ELF/image/build logs. All 12 old Chisel-generated SV files are byte-identical to frozen S2b. The optional new generator emits 11 shared files with identical bytes and one new top; `LinearCachedCore.sv` is untouched. `rtl-compatibility.json` records each hash.

Production Chisel changes are exactly:

- `src/main/scala/GenerateRTL.scala`: optional new generator key.
- `src/main/scala/linear/LinearAutoGroupCore.scala`: new two-slot producer wrapper.

The separate Scala test adds no production behavior. No old PE, compute, controller, memory, macro, weight capacity, numerical fixture or shared signed64 Y format is modified. New generated logic is copied from the optional Chisel generation into the child, without manual edits.

`chisel-autogroup.log` records the passing two-row/all32-group numerical test. `wrapper-{compile,simulation}.log` record Icarus using the actual core/SRAM, 64 complete groups/512 signed48 lanes, two full FIFO slots with a stalled producer, real compute/readback overlap, stable read/POP response backpressure, explicit retirement, same-edge head-command rejection, reset abort and return to legacy manual START. The original scalar, packed and cached wrapper tests pass. `host-tests.log` records 57 host checks; `numeric-tests.log` records 42 unchanged numerical checks.

All three real1 runs must pass exact 25,344 outputs/50,688 shared write words. Actual core launches/done/MAC beats remain 3,168/3,168/202,752. S2c additionally requires 99 accepted STARTROWs, 3,168 successful POP response retirements, final producer/retired counts 32/32, no pending FIFO contents, and observed compute/writeback overlap. The old inclusive first-input/final-Y-response window remains the timing boundary, and all final POP responses retire before the last two Y writes.

Raw logs, result/build metadata, actual ELF/load images, lossless vectors and the common simulator binary are archived under `raw/`. `comparison.json` records the measured rows, exact common identities and arithmetic comparisons. `sha256.json` covers all other files in this evidence directory. `check-results.py` rehashes those artifacts, checks the actual source/runner/compiler/fixture identities, independently verifies vector arithmetic, reparses completion/performance/retirement records, rechecks old RTL/image compatibility, and injects malformed actual counters/records that must be rejected. It never produces DUT outputs or substitutes for CPU/core execution.

To reproduce the archived read-only check after an existing `make -C third-party/e203_hbirdv2/vsim install` (or any actual real1 run has installed the source RTL):

```bash
python3 docs/validation/xu-s2c-autogroup-20261103/check-results.py
```

To repeat the actual three-way screen, use three new output directories and the same runner arguments shown in the contract, substituting the schedules above. Do not reuse an output directory or substitute another candidate's area/energy result.

Observed complete windows: **1,387,720 cycles old ABI, 1,250,899 S2b control, 1,013,171 S2c**. S2c reduces cycles **26.990243% versus old ABI** and **19.004572% versus S2b** in this local fixed-layer comparison. All 25,344 outputs and 50,688 shared output words pass exactly in every run. S2c observes 136,125 cycles of actual compute/writeback overlap and 508,959 cycles waiting behind a full result FIFO; those measured waits remain in the full window. Its 15,497 writes and 54,648 reads are actual accepted MMIO transactions, with polling included. The old ABI and S2b control cycle totals also exactly match their frozen S2b local observations.

| Cycles / work | Old ABI | S2b control | S2c |
| --- | ---: | ---: | ---: |
| Complete task | 1,387,720 | 1,250,899 | 1,013,171 |
| W load | 299,301 | 183,516 | 183,503 |
| X load | 114,906 | 71,279 | 71,182 |
| Bias load | 7,773 | 7,773 | 7,774 |
| Compute wait phase | 218,592 | 218,592 | 48,114 |
| Writeback phase | 663,663 | 663,597 | 670,230 |
| Other | 83,485 | 106,142 | 32,368 |
| Actual busy | 215,424 | 215,424 | 215,424 |
| MAC beats | 202,752 | 202,752 | 202,752 |
| Core starts / done | 3,168 / 3,168 | 3,168 / 3,168 | 3,168 / 3,168 |
| MMIO reads | 76,032 | 76,032 | 54,648 |
| MMIO writes | 55,720 | 21,734 | 15,497 |
| Shared reads / writes | 23,232 / 50,688 | 23,232 / 50,688 | 23,232 / 50,688 |

All five unchanged full-SoC Icarus programs passed on the candidate: `rv32ui-p-add`, `accel_mmio`, `accel_compute`, `accel_multigroup`, `accel_repeat_x`; actual logs/ELFs/images are retained in `raw/legacy-baseline/`.

[independent-review.md](independent-review.md) records the separate static lifecycle review: no actionable correctness findings. Its noted nonblocking final-POP/new-STARTROW test gap was subsequently covered by an actual directed Icarus test for both rows; production and measured real1 identities remain unchanged. This is not an independent rerun or VCS claim.
