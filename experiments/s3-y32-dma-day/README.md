# Independent matrix DMA candidate

The published integration v1 is documented in
[the hardware/software handoff](../../docs/s3-y32-hw-sw-handoff.md). Its checked-in
DMA-only `DmaBiasSramPrefetch` keeps the legacy `BiasSramPrefetch` interface
intact. Use the handoff's sealed fabric-clock testbench to reproduce the shared
clock/reset repair; historical CPU test commands below remain prior evidence.

Build flag `XU_MATRIX_DMA` selects `xu_matrix_dma` in `e203_subsys_perips` and
`xu_dma_shared_arb` at the external shared-memory port. The candidate replaces
the historical accelerator instance, so it retains exactly sixteen weight
1024×16 macros and one bias 1024×16 macro. The default build keeps the old
accelerator, NICE path and direct sysmem wiring. No CPU, LSU, BIU or original
outstanding configuration changes are needed.

The DMA is a separate peripheral master. Every source read and Y write passes
through the shared arbiter and tested external ICB SRAM. One request may be
outstanding; a retiring response can be replaced by the next command on the same
edge. A stalled command has a locked payload and route. On the first response
error, computation is aborted and any already offered/accepted transaction is
drained. The error remains latched. A new task requires a successful explicit
physical clear, and failed partially written tasks are never retried internally.
The shared endpoint and arbiter must share reset; resetting only task ownership
while leaving a memory response live is not supported.

The core retains INT16 X/W, signed40 bias, 48-bit accumulation and existing RNE
division by 512 to Y32. It shares W/bias across two eight-PE engines. The second
engine is disabled for row 98 of a 99-row task. Four X row buffers provide
512 B ping-pong storage, two pair FIFO entries provide 192 B, and the DMA holds
one eight-Y32 snapshot (32 B). Output destinations are derived from the owned
pair row, row identity, group and lane; no matrix-sized result buffer exists.

W source data contains two adjacent INT16 columns per 32-bit word. Each response
writes the two independent even/odd bank ports on the same edge; the SRAM layout
and capacity are unchanged. Bias uses two 32-bit source words per signed40
entry, committed through the existing bias sequencer. X remains one INT16 value
per 32-bit source word, matching the 6,336-read baseline and required 31,680-word
X/Y transport work. W/bias are reloaded on every task.

## MMIO contract

Base `0x10042300`, 32-bit aligned full-word accesses. Other candidate accelerator
offsets return an error; the complete legacy ABI is provided by the default
build. Configuration writes while busy return an error and do not change the
active descriptor. Source/destination ranges must fit `0xa0000000..0xa0080000`;
Y must not overlap X, W or bias. All four bases are copied on START.

| Offset | Access | Meaning |
| --- | --- | --- |
| 00 | R | ID `0x444d4131` |
| 04 | W | `1`: physical clear; `2`: one-row START; `0x102`: two-row START |
| 08 | R | busy[0], done[1], error[2], clear_done[3] |
| 0c | R | First error code: 1 memory response, 2 bias commit |
| 10/14/18/1c | RW | X/W/bias/Y base |
| 20 | R | START→completion controller cycles, separate from measured payload |
| 24 | R | Hardware clear cycles |
| 28/2c/30/34 | R | Accepted source reads, Y writes, POPs, primary MAC steps |
| 38 | R | Actual W+X clear port writes, expected 16,640; bias is observed separately |
| 3c/40 | R | Command stall / pending response wait cycles |
| 44/48 | R | W/bias stage / compute-X-Y stage cycles |
| 50/54/58/5c | R | Frozen active X/W/bias/Y descriptor |

CPU firmware executes `fence iorw,iorw` before submission and after completion,
checks both done and error, and never retries a failed descriptor. DONE is
offered only after every output snapshot is committed, all Y responses have
retired, and internal command/response ownership is empty. The shared memory
is the existing uncached external region; no cache-coherency bypass is added.

## Evidence and reproduction

- [Single-day scope and execution record](../../docs/s3-y32-dma-day-plan.md).
- `fabric/run_probe.py`: real ingress bandwidth, contention, response and reset.
- `core/README.md`: generation, exact numerical tests, dirty physical clear,
  ping-pong, backpressure and abort tests.
- `run_soc.py`: frozen-source real-CPU single-layer and full12 runs; `--warmup`
  executes and checks one public task0 before counted tasks. `--observer` adds
  the read-only physical-clear monitor. `--replay-from` reuses the exact verified
  simulator/firmware/source identity for one-row and two-row comparisons.
- `protocol/`: independent DMA/fabric error, reset and backpressure campaign.
- `check_fallback.py`: rebuild current default RTL and reproduce the original
  8 PE CPU task0 output, payload, physical-clear and gap contract.

Every experiment writes a new directory, retains raw logs and freezes sources.
Warming up, protocol tests and module tests do not enter the 12-task performance
sum. The primary window is first DMA source VALID through final Y write response,
inclusive, plus actual clear; clear-to-source gap is reported separately and
also included in a second total. A 150 MHz clock stimulus or cycle conversion is
not STA, physical implementation or formal contest qualification.
