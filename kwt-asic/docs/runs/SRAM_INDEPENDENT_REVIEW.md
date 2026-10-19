# SRAM subsystem independent review — 2026-10-17

## Result and scope

**Source/functional-evidence review: PASS.** No blocking latency, multiple-driver,
bank-selection, or memory-collision defect was found in the current
`kwt_sram_bank` / `kwt_linear_engine_rowpair_sram` candidate. This review reads
root-authored RTL, testbenches, runners, raw completion logs, and stored input
hashes. It does not accept physical SRAM timing, area, power, or the official
E203 platform. Those remain **BLOCKED** on official files.

The reviewer independently checked the bank/core/runners. The reviewer also
authored the primitive wrapper and its unit runner; unit results are regression
evidence here, not a claim of an independent implementation review of those
same authored files.

Machine-readable evidence is
[`artifacts/reviews/20261017-sram-independent-2091f455/review.json`](../../artifacts/reviews/20261017-sram-independent-2091f455/review.json).
It binds the reviewed sources, accepted engine results, and unit result by SHA256.

## Storage latency and ownership

- A primitive captures read address at a rising edge and updates its registered
  Q during the following cycle. Bank `returned_tile` is captured on that same
  edge, so the combinational tile selection follows the requested read. No read
  request means neither primitive Q nor bank selection changes.
- At request edge `t0`, SRAM Q and `read_valid/first/last` become available. With
  `PIPE_MUL=0`, accumulation consumes them at `t1`. With `PIPE_MUL=1`, product and
  metadata registers capture at `t1`, and accumulation consumes them at `t2`.
  Bias Q holds after the first read of a tile. The drain/store sequencing waits
  for the final accumulation before taking the result snapshot. No extra
  `READ_WAIT` is needed for this preserved one-cycle interface.
- X loads are allowed only while inactive; active X/W/bias reads therefore do
  not overlap payload loading. Result writes target the compute buffer before
  it is marked full; result reads require a full output buffer. The final
  output handshake releases that buffer before reuse. Current generated banks
  are used as 1RW, not as undocumented dual-port macros.
- Returned result data and `rd_buffer/rd_index/rd_pending` advance together.
  Queue credit includes the outstanding read, preventing a third resident or
  pending word from exceeding the two-entry queue. Completion is the final
  accepted external output, followed by invalidation of task-load counters.
- Each output word/array element has one generated storage driver. Width
  slices drive disjoint bit ranges. Bank and primitive validity registers are
  distinct nets. No multiple-driver structure was found by source inspection.
- Reset clears valid/occupancy/control but preserves payload and the simulation
  written bitmap. This does not permit an engine task to reuse stale input as
  fresh data; its load counters still reset and require a complete reload.

The official adapter must preserve this contract or add an explicitly verified
adapter. Actual official macro read latency, polarity, masks, and collision
rules have not been assumed.

## Bank boundaries and width coverage

The depth decomposition was checked: depth3200 uses 3×1024 + 1×128; depth3136
uses the same capacity with 64 unused words; depth2048 uses 2×1024. Width40/41
uses three 16-bit slices. Padded addresses remain inaccessible through the
logical address bounds. A depth4224 test exercises 4096 + 128 composition.

The bank test writes every logical address, reads all addresses in increasing
order, then reads all addresses in decreasing order. Thus depth3200 covers
1023/1024, 2047/2048, 3071/3072 and 3199, including back-to-back tile changes.

The first pattern had a coverage defect: bit40 stayed zero for every
depth3200 word. It still compared 41-bit values, but could not establish that
the highest slice transmitted a one. The test now XORs upper bits on alternate
addresses and accumulates `seen_zero`/`seen_one`; it requires **both values for
every WIDTH bit**, including all nine bits `[40:32]` of width41 and all eight
bits `[39:32]` of width40. The runner requires the width-coverage completion
marker in addition to the bank marker.

Only testbench/runner files changed for this correction; the active SoC source
set, SRAM primitive, bank RTL, and core RTL were not changed.

## Executed evidence checks

`make test-memory` produced **PASS: 51 cases, 7 behavioral/FF response-signature
groups**. Its current result is
[`20261017T142618.212030Z-sram-unit-6d94fd06/result.json`](../../artifacts/runs/20261017T142618.212030Z-sram-unit-6d94fd06/result.json).
All bound inputs and raw log hashes were recomputed. Positive tests require
native exit0 plus complete markers; negative tests require native nonzero exit
and their intended diagnostic. No timeout was accepted. Coverage includes
depth1/5/128/1024/4096, widths16/40/41, reset retention, continuous/direction
changes, address/control/data errors, forbidden single-port collisions,
uninitialized reads, complete/missing/short/X initialization images, blackbox
functional refusal, and missing official-adapter refusal.

The failed intermediate coverage-fix attempt is retained at
[`20261017T142552.514723Z-sram-unit-cf48f180/result.json`](../../artifacts/runs/20261017T142552.514723Z-sram-unit-cf48f180/result.json).
Its full-word inversion accidentally cancelled the original bit0 alternation;
the new full-width coverage assertion caught it. Restricting the XOR to the
upper bits resolved the test-pattern issue. This was a test-stimulus defect,
not an RTL functional failure. The older 51-case run remains historical
evidence and is superseded for current testbench identity.

Twelve current-source engine runs were independently checked against their
raw logs and source/vector hashes: the 2×2 combinations of `PIPE_MUL` and result
buffer count across both backends (six tasks each), twelve-layer replay across
both backends, and signed41 range runs across both backends. The check verified
task order, 25344 outputs/task, 22976 loaded words/task, a unique suite marker,
native exit0, no failure diagnostics, and workload SHA reconstruction. The full
configuration and paths are in the review JSON.

For the twelve-layer behavioral replay
[`20261017T142316.614052Z-sram-engine-890806dd/result.json`](../../artifacts/runs/20261017T142316.614052Z-sram-engine-890806dd/result.json),
an independent signed-integer loop recomputed **304128 output words** directly
from HEX X/W/bias, without importing the project Golden Model. Every value
matched the saved 48-bit Golden image. Together with the testbench's exact
per-output comparison, this supports bit agreement for those replayed layers.
The fixture remains one waveform/silence smoke, not full-dataset accuracy.

## Runner and SoC checks

`run_sram_engine.py` uses explicit source sets, selects only behavioral or FF
for functional tests, records source/model/vector/tool identities, and checks
input hashes again after execution. Its comparator rechecks original logs and
workload hashes instead of trusting a stored PASS field. The omitted opaque
module file does not cause a missing functional dependency for these two
unselected blackbox branches.

`run_sram_soc.py` copies/rebinds only the two generated integration sources in a
fresh run directory. It preserves the prepared E203 tree. The source set
includes all E203 `.v` files, including `e203_defines.v`; the actual candidate,
adapter, checked shared-memory model, firmware sources, compiler, and vector
provenance are bound and rechecked. No missing active source was found.

The SoC testbench checks all 50688 aligned output stores/task against Golden,
including order and write mask. It requires 22976 engine-load commits,
software WRITEBACK_ACK completion, inactive engine, task completion flags, and
the final shared-bus response before the suite marker. The runner checks one
marker/task in order, positive transaction counts, one suite marker, and the
suite-cycle sum. These conditions do not reduce task completion to MAC done.

At this review boundary, the twelve-layer SoC run
`artifacts/runs/20261017T142439.193514Z-sram-soc-2ef93db7` was still executing.
Its final result is **NOT_RUN / not yet independently accepted by this review**.
Do not infer SoC PASS from the source review.

Two limitations remain explicit:

1. The SoC result currently records ELF/HEX hashes but does not record the
   generated simulation executable or `firmware.bin`. Add a separate immutable
   output-artifact manifest after the active run, or record them in the next
   runner revision. This does not require interrupting the valid running test.
2. The TB starts `full_window_cycles` at the first shared X read. HOST_FLAG
   polling and initial LOAD_KIND/LOAD_ADDR configuration precede it. The value
   includes the main task load/CPU/compute/writeback interval, but is **not the
   complete official competition window**. Future contest timing must use the
   official boundary and include initial configuration as required.

## Acceptance boundary

Functional bank/core evidence is accepted for the reviewed identities and legal
1RW contract. Final SoC functional acceptance still needs the completed raw
log/result check. Official SRAM area, delay, dynamic/leakage power, full-system
150 MHz timing, and official-platform compliance remain BLOCKED. Blackbox
timing without macro arcs must not be reported as full timing closure.
