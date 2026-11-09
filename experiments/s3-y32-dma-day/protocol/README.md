# Actual DMA protocol and numeric screen

This harness instantiates the production candidate `xu_matrix_dma`, generated
`LinearRowPairDmaCore`, the production peripheral `xu_dma_shared_arb`, existing
registered/throttled `xu_shared_icb_sram`, and actual `sirv_sim_ram` storage RTL.
The generated compute SRAM models implement the same synchronous 1024×16 macro
interface as the prior row-pair harness. All Chisel assertions remain enabled.

The configuration master exercises public MMIO at `0x10042300`. A second public
ICB master initializes source storage, poisons output storage, optionally contends
with DMA, and reads every output back after completion. It never accesses
compute memories hierarchically. Hierarchical reads observe protocol state and
actual SRAM/X write pins; there are no force/deposit calls, hierarchy writes,
result preloads, or bypass of shared storage.

This is **peripheral-block evidence, not CPU instruction execution or full12
throughput**. Its timing cannot replace CPU task measurements. Clock stimulus is
6.666 ns; no implemented frequency, area, STA, or formal qualification is claimed.
Initial reset-state physical clear is address/data proven; nonzero-prestate
coverage for every internal location is provided by the separate core observer,
not inferred from this initial clear.

## Reproduce

```sh
python3 experiments/s3-y32-dma-day/protocol/run_protocol.py \
  --repo /home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest \
  --vectors /home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/bias-demand-20261109/full12/task-00/vectors/layer_00 \
  --out /tmp/s3-dma-protocol-replay
```

Use a fresh output directory. The runner freezes every compiled RTL source, its
own tools and the testbench; copies and hashes vectors; independently recomputes
all speech and synthetic outputs with signed INT16 products, signed40 bias and
round-to-nearest-even; generates a read-only physical observer; records compiler
and exact commands; runs 21 jobs; and rejects source drift. `--build-jobs` and
`--run-jobs` default to two.

## Sealed result

`build/dma-day-20261109/protocol-r4/result.json`: **PASS, 21 jobs, no source drift**.
Prior `protocol-r1` records a runner source-extension compile failure; `r2` is a
passing 16-job subset and `r3` is the passing 21-job set before the explicit cfg
response-hold addition. Neither earlier artifact was overwritten.

Each successful job checks the full 99×256 = **25,344 Y32 outputs** on accepted
DMA writes and then **25,344 physical shared-memory word readbacks** through
public ICB. It checks exactly 8,192 W + 512 bias + 6,336 X reads, 25,344 Y writes,
40,384 DMA responses, 3,168 POPs, and 102,400 dual-row / 202,752 single-row MAC
steps. Source addresses must each appear once and every output address once,
including row98 and the interleaved two-row destinations.

The 21 jobs cover:

- Speech task0 in both modes; synthetic full-size endpoint/RNE dataset in both
  modes. Synthetic values include raw48 endpoints −618,473,193,472 and
  +618,475,290,623, 3,936 positive halfway results and 3,904 negative halfway
  results. Both independent Python arithmetic and RTL Y32 must match.
- Start before clear; cfg misalignment and unsupported registers; partial write
  masks; invalid/unaligned/range-overflow/overlapping descriptors; descriptor,
  clear and start writes while busy. Rejected busy writes leave the descriptor
  intact.
- Saturated CPU-side arbitration contention with periodic command and response
  backpressure. Commands, responses and cfg responses must hold stable while
  stalled. A CPU-owned shared response may remain live after DMA completion;
  DMA's own requests and core/result ownership must be empty.
- First/last W read errors at source ordinals0/8191; bias low/high errors at
  8192/8193; first/last X errors at8704/15039. Each first error aborts the task,
  reports error code1, drains ownership, reports no completion, then recovers via
  physical clear and a complete fresh correct run.
- Y write errors at accepted write ordinals0/12672/25343. Each targeted write is
  deliberately held for five cycles before acceptance, then its error response
  must retire before abort reports idle. No automatic retry or false completion
  is allowed; a separate explicit clear/start performs the verified recovery.
- Shared reset with W response held, bias host commit pending, X prefetch response
  held, first/middle Y response held. Each next epoch has no stale response or
  completion and produces every output correctly after clear.
- Clear interrupted after100 cycles: `clear_done` remains false after reset;
  only a fresh complete clear can permit a successful new task.

Every completed clear checks every physical address and zero write data for
**16,384 W + 768 bias + 256 X = 17,408 writes**. The public DMA clear counter is
correctly scoped to W+X (**16,640**), and is never used as a total including bias.
Clear duration is 2,050 cycles. The 16 W SRAM macros and one bias macro remain
unchanged; four X buffers together store512B.

Uncontended peripheral timing for speech task0 is124,148 payload +2,050 clear =
126,198 cycles in dual-row mode; single-row is232,116 +2,050 =234,166 cycles.
Initial cfg testing deliberately holds the first response briefly; these figures
are block counters for this harness and must not be treated as CPU throughput.

## One-inflight coverage boundary

With this candidate, `locked` implies `!pending`. A next DMA offer while pending
is enabled only on `rsp_fire`; `fault` suppresses a new unlocked offer on an
error response. A stalled offer can become locked only as the old response
retires, clearing pending. Accepting the locked offer clears locked and sets
pending. The harness asserts this invariant and rejects any command offered
while a first DMA error retires.

Therefore a *held next DMA command concurrent with a previous owned DMA error
response* is unreachable with the legal one-outstanding interface. The test does
not manufacture an unowned response to claim that scenario. It verifies the
reachable boundary: a held command is eventually accepted, its own injected
error response drains, no later work is issued, and a new task starts only after
explicit physical clear. A future multi-outstanding variant requires new tests
for simultaneous held-next-command and old-error retirement.
