# Paired NICE strided-transfer RTL experiment

This is an optional, isolated 2-row × 8-column transfer experiment. It is not
installed into the measured E203/accelerator, an independent DMA bus master,
a CPU/SoC campaign, a synthesis result, or a claimed task speedup.
The pinned development baseline is parent `e984bad936855debfc5fa01f04bcbc6252d59ecc`
and E203 `dba1b5f82395b762f126387a1840e6a843e3a01a`.

## Run

Generate `LinearRowPairPrototype` from the adjacent rowpair experiment, then:

```sh
python3 /path/to/paired-nice/run_probe.py \
  --repo /path/to/ChipContest \
  --generated-rowpair /path/to/generated/LinearRowPairPrototype \
  --vectors /path/to/task-00/vectors/layer_00 \
  --out /path/to/new-proof-directory
```

The testbench stores the `--vectors` absolute path in1024bits; use a path of
at most128ASCII bytes. The validated path is106bytes. Longer paths are not
qualified by this frozen fixture and must be shortened before running.

The baseline repository is read only. Its `e203_defines.v`, original legacy test
fixtures and SRAM/core dependencies are used for compatibility tests. The NICE
variant and both new fixtures come from this directory. The generated pair RTL
must be the same source revision as the separately delivered rowpair source.
The runner records commands, raw logs, return codes, all used source identities,
before/after source drift and an explicit PASS/failure result. Icarus 4-state RTL
simulation keeps the Chisel procedural assertions. No synthesis or PPA tool runs.

The matrix separates synthetic corner values (`vector_mode=0`) from published
speech task0 (`vector_mode=1`). Both execute all 99 rows and all 25,344 Y32 values.
Speech results are checked against both `y32.mem` and a separately written signed
64-bit MAC + sign/magnitude nearest-even oracle. The synthetic fixture reaches
signed16 extremes, signed40 biases and positive/negative ties. Inputs reach the
real SRAM/compute load ports; no forced/preloaded FIFO payload is used.

## Experimental ABI

`xu_nice_drain8` adds `PAIR_ENABLE`, default0. With `DIRECT_ENABLE=1` and
`PAIR_ENABLE=1`, `funct7=0x25` / `funct3=7` / `custom3=0x7b` supports:

| Operand/field | Meaning |
| --- | --- |
| rs1 | First row's current group base;32-byte aligned, Y address range only |
| rs2[4:0] | First group0..31 |
| rs2[9:5] | Group count minus1; requested span must fit in this row |
| rs2[10] | Second row present; zero for odd tail row |
| rs2[31:11] | Nonzero READY wait budget per8-lane bundle |
| live status[31] | Existing live READY protocol available |
| status[30] | Pair-producer route, mutually exclusive with old drain opcodes |
| status[11] | FIFO row identity:0 first row,1 second row |
| status[10:6] | Existing group tag, unchanged |

The FIFO order is `(g,row0),(g,row1),(g+1,row0),(g+1,row1),...`. A second-row
bundle writes `rs1+1024`; the first-row base advances32 only after both bundles'
last write responses retire. Tail mode never issues a second-row POP or write.
Both row spans are checked by a33-bit end calculation before any side effect.
A tag mismatch returns `ERR_ROW_ID=10`; the old errors1..9 remain unchanged.

`bit30=0` preserves the old0x20/0x23/0x24 descriptor semantics. New0x25 on the old
wrapper rejects before any snapshot/POP/Y write. Conversely,0x20/0x23/0x24 on a
pair route reject upfront, avoiding partial row0 writes before encountering a
same-group row1. The measured production wrapper does not advertise bit30, and
its NICE instance does not enable `PAIR_ENABLE`.

The bridge converts8 signed48 values through one RNE path over8 capture edges,
then publishes a stable256-bit bundle and frozen row/group metadata. NICE
captures all eight lanes before its later commit edge. Commit validates both
row and group against the still-owned FIFO head. Neither bus command nor POP is
issued during READY wait. Payload, commands, and completions hold under stalls.
A first error stops the full instruction. A POP cannot be rolled back; software
must abort the full task, not retry a partially written descriptor.

## Evidence and interpretation

The31-run runner includes613 unit cases, all64 count/tail combinations, all512
post-POP write-response error positions, live/captured row mismatch and capability
loss,13 reset events across READY/capture/commit/command/outstanding/completion,
compile-time disable, legacy direct/READY real-wrapper backpressure and reset
regressions,10 full99-row runs, and real-MAC write errors at15 and511.
Some reset cases intentionally abandon an accepted bus transaction when the
whole fixture resets; aggregate unit write/response counters therefore differ.
Each non-reset completion asserts that all its accepted writes retired.

Measured compute-to-last-write-response intervals from the module fixture:

| Synthetic sink command period / response delay | One-row mode | Two-row mode | Reduction |
| --- | ---: | ---: | ---: |
|1 /0 |221,760 |119,840 |45.960% |
|1 /3 |224,136 |195,128 |12.942% |
|1 /5 |250,272 |245,568 |1.880% |
|3 /2 |224,136 |195,130 |12.941% |
|Speech task0,3 /2 |224,136 |195,130 |12.941% |

All successful rows execute25,344 serial32-bit writes and their25,344 responses,
3,1688-lane snapshots and POPs. Only descriptor requests fall from99 to50. Slow
shared-memory service hides most compute parallelism; widening/duplicating MACs
does not remove output traffic. These intervals exclude X/W/bias loading,
physical clear, CPU instruction retirement, actual LSU/fabric service and error
checks in firmware. They must not be compared numerically with422,768-cycle
payload or489,570-cycle inclusive-clear SoC measurements.

## Why this is not an independent DMA

The unchanged E203 LSU has CPU AGU and NICE requesters on the existing arbiter.
`nice_mem_holdup` blocks AGU requests while NICE owns the LSU
(`e203_lsu_ctrl.v`207..218); the NICE/AGU input count is fixed at2(223..225).
This variant issues one32-bit command, waits for its response, and then issues
the next. It cannot add fabric bandwidth, permit CPU/LSU concurrency, or bypass
that arbiter. Baseline speech task0 has25,344Y writes,196,614 writeback cycles,
17,681 shared-stall cycles,99 NICE requests and zero status/result MMIO reads;
the existing internal channel already removed those reads.

A separate DMA requires a new shared-memory ingress or arbiter client, response
ownership/routing, cancellation and reset of in-flight transactions, and a
firmware visibility/completion contract. Those are CPU/fabric integration changes
outside this round's fixed LSU/BIU/arbitration/outstanding constraint. This round
therefore stops at a tested strided NICE transfer prototype and a concrete DMA
integration boundary. No independent-master RTL was connected, no area/timing
qualification was run, and the production8PE baseline remains the measured best
candidate until a separately authorized integration campaign proves otherwise.

The published runner rejects non-ASCII or over-128-byte vector paths before creating its output directory. This preflight guard leaves the measured RTL unchanged.
