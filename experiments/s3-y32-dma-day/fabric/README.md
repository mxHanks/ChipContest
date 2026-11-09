# Independent peripheral DMA shared-port preflight

This probe exercises the exact new `xu_dma_shared_arb` RTL attached to the
existing `tools/ppa/xu_shared_icb_sram.sv` and `sirv_sim_ram` storage RTL. The new
DMA ingress is after the unchanged CPU `e203_subsys_mems` output and before the
shared external memory port. Its complete ingress path is therefore this arbiter
and this endpoint. Neither the CPU core nor LSU/BIU internal control or its
outstanding configuration changes.

This is **not a CPU-executed task**, and it does not measure unpacking or commit
into accelerator W/bias SRAMs. It establishes service available to a correctly
streamed peripheral master. Actual firmware/CPU integration and complete
accelerator-load timings remain separate gates.

## Interface and reset contract

`e203_subsys_main.v` has `dma_cmd_valid/ready/read/addr/wdata/wmask` and
`dma_rsp_valid/ready/err/rdata` local wires connected to new ports on
`e203_subsys_perips`. Only the periphery drives this master. The original memory
subsystem connects to `cpu_sysmem_icb_*`; the arbiter connects its output to the
original external `sysmem_icb_*` port.

The arbiter has one downstream outstanding request with a registered owner. A
response can retire simultaneously with a new accepted command, allowing
one-cycle intervals. Round robin advances on accepted commands, and a selected
command holds its grant during downstream backpressure. There is no data FIFO;
state consists of five one-bit registers (`inflight`, `owner_dma`, `prefer_dma`,
`grant_locked`, `locked_dma`). No shared SRAM or compute SRAM macros are added.

The arbiter and shared endpoint must share the subsystem reset. Independent task
abort must continue receiving an outstanding response before starting another
task; it must not reset only the owner tracking. The protocol probe resets both
while a response is held and confirms no old response appears in the next epoch.

## Reproduce

Use a new output directory; the runner refuses overwriting evidence:

```sh
python3 experiments/s3-y32-dma-day/fabric/run_probe.py \
  --repo /home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest \
  --out /tmp/s3-dma-fabric-replay
```

The runner freezes five sources, hashes them, compiles with Icarus, records tool
identities and exact commands, and writes `result.json`, `compile.log`, and
`simulation.log`. Sources are never initialized or inspected through hierarchy.
Initial source words are written through CPU-side public ICB transactions; Y is
read back through the same interface.

## 2026-11-09 preliminary result

Frozen evidence: `build/dma-day-20261109/fabric-preflight/`.
Clock stimulus: 6.666 ns period (nominal 150 MHz); no STA or frequency claim.
Endpoint: one registered response, one throttle bubble every seven cycles.
Each measured window is first DMA command acceptance through final DMA response
retirement, inclusive.

| DMA sequence | CPU traffic | Response stalls | Cycles | Cycles per DMA word |
| --- | --- | --- | ---: | ---: |
| 8,704 W/bias source reads | none | none | 10,155 | 1.16670 |
| 6,336 X reads + 25,344 Y writes | none | none | 36,960 | 1.16667 |
| 8,704 W/bias reads | saturated public master | none | 20,309 | 2.33330 |
| 6,336 X reads + 25,344 Y writes | saturated public master | periodic CPU/DMA holds | 140,938 | 4.44880 |

Uncontended request acceptance intervals are 1–2 cycles and response latency is
one cycle. The stress case reaches 12 cycles between DMA accepts and six-cycle
DMA response latency. Max outstanding occupancy is exactly one. `result.json`
contains interval/latency sums and individual arbitration, endpoint, request,
and response stall counts. Saturated CPU traffic deliberately halves DMA
service; firmware should avoid sustained shared-memory polling.

The output path is verified by **50,688 public physical Y word readbacks** across
two runs. Read and write errors (range and alignment), per-response ownership,
response data, command/response stability under backpressure, simultaneous
retire/accept, and reset with one held response pass. There are 186,885 accepted
commands, 186,884 retired responses, and one intentionally cancelled response
under shared reset. No testbench array bypass, hierarchy writes, result preload,
ideal endpoint, or synthetic completed-task throughput is used.

The standalone ingress bandwidth is sufficient for the initial ≤20,000-cycle
W/bias and ≤3-cycle X/Y service budgets without deeper downstream outstanding
queues. Accelerator unpack, storage commit, compute overlap, CPU synchronization,
and complete tasks still need measurement; these numbers are not those results.
