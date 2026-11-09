# DMA-facing shared-weight compute core

`LinearRowPairDmaCore` is a new peripheral-facing module. The installed
`LinearRowPairPrototype`, original production compute RTL, CPU, LSU and BIU are
unchanged by this implementation. This core is not itself a DMA or an end-to-end
throughput result: its caller owns the shared-memory requests and CPU protocol.

Generate from the repository root:

```sh
scala-cli run project.scala src/main/scala experiments/s3-y32-dma-day/core/GenerateDmaCore.scala --server=false --main-class GenerateDmaCore -- generated/LinearRowPairDmaCore
```

The eleven generated SV files retain assertions. Exactly two eight-lane
48-bit engines share sixteen weight SRAM macros and one bias SRAM macro. No
weight/bias capacity was added. Four register-based 64x16 X buffers form two
ping-pong row-pair sets (4096 bits = 512 B). Two pair slots hold four eight-lane
raw48 bundles (1536 bits = 192 B), plus two five-bit group tags. These payload
capacities are separate from accumulator, engine-result and bias-cache registers
already required by the reused datapath.

The original prototype IO names are retained with five additional input signals:

* `xRunSet` is captured on `start`; changes after launch do not change ownership.
  `xLoadSet` selects the destination set. During `active`, only the opposite set
  may be written. The scheduler must finish a set before starting it.
* `wLoadPacked` optionally loads two adjacent columns from one 32-bit source word:
  `wLoadData` writes the selected **even** bank and `wLoadDataHi` writes the next
  odd bank at the same `wLoadAddr`. With `wLoadPacked=0`, the original single-bank
  16-bit interface is retained. For source-word index `p`, bank is
  `{p[1:0],1'b0}` and address is `{p[6:2],p[12:7]}`.
* `abort` immediately removes active/output ownership and resets the compute and
  bias sequencers, preventing a cancelled bias demand from blocking recovery.
  It does not claim physical clear. Aborting a clear cancels that operation
  without `clearDone`; the caller must restart a complete clear before reuse.

`clearValid && clearReady` starts a physical clear. All eight independent W
banks write one 16-bit zero per cycle for 2048 cycles; the reused bias controller
writes all 768 words concurrently; all four X buffers write zero for 64 cycles.
The existing accumulator/result resets and explicit result/bias-cache payload
zeroing run at clear acceptance. `clearDone` waits for both W and bias completion.
`clearWeightWrite` describes **eight** real writes on an edge, and `clearXWrite`
describes **four** real writes. Full physical work is 16384 + 768 + 256 = 17408
16-bit writes. A normal module API clear measured 2051 cycles including its
acceptance/completion observation overhead; this is not CPU/MMIO clear timing.

Run the module campaign:

```sh
python3 experiments/s3-y32-dma-day/core/run_core.py --repo . --vectors build/bias-demand-20261109/full12/task-00/vectors/layer_00 --out build/dma-core-checks-20261109/NEW
```

The campaign uses actual generated SV with Verilator assertions. Ten cases cover
one/two rows and consumer stalls of 0, 31, 60, 80, and 255 cycles per bundle. Each
case compares all 25344 raw48 results to an independent C++ dot-product oracle
and vector truth, and separately applies C++ RNE to compare all Y32 results.
Next-pair X loads run concurrently with computation, set selection changes after
launch test latching, and row 98 exercises the odd tail. Legal signed endpoints,
three reset boundaries, three abort boundaries, aborted-clear restart, and
single-bank fallback recovery are also checked.

The bind observer is read-only: it observes actual SRAM macro write pins and X
register write ports. Dirty coverage is created only through public ports. A
full nonzero prestate is required before the second clear; all W/bias/X addresses
and the X/ACC/engine-result/FIFO/bias-cache payload are then checked zero. No
force, deposit, hierarchical write or precomputed result preload is used.

Receipts pin sources, inputs, commands, and source-drift checks. These are module
correctness and physical-clear observations. CPU execution, external request
retirement, RTL rounding, real shared-fabric timing, throughput, area and STA
must be established by the integrated candidate separately.
