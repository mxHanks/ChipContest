# Experimental 64-bit shared-memory channel

`xu_dma64_shared_arb.sv` keeps the CPU interface at 32 bits, adapts its selected
half-word lanes, and arbitrates it with an independent 64-bit DMA master. One
accepted request may be outstanding globally; a retired response and replacement
request may use the same edge. Stalled grants retain their selected owner. A
reset must be common to the arbiter and endpoint.

`xu_shared_icb_sram64.sv` exposes the existing 512 KiB capacity as 64 depth banks,
each containing four 1024x16 single-port macro instances: 256 macros total. A
64-bit access activates four lanes on one clock edge. A 32-bit access activates
only its selected two lanes. Alignment, range, and width/mask checks precede all
physical enables; an invalid write cannot partially commit. The default throttle
retains one blocked request-acceptance cycle out of seven.

The `dma_cmd_is32` metadata allows an outer copy of this exact arbiter to accept
the SoC's already adapted CPU32 transactions when a testbench public loader
shares the endpoint. A production independent DMA ties that input low. For a
size32 wide-input transaction, data and masks must already occupy the half
selected by address bit 2.

`tb_shared64.sv` initializes every address through public CPU transactions and
checks through public reads. It never writes a DUT storage array. Its read-only
macro-pin observers check exact enable, address, data, write-mask, and SRAM mode
signals. It checks all byte masks, CPU halves, bad alignment/range/mask requests,
response ownership, held requests/responses, CPU contention, backpressure, and
reset cancellation. The measured streams contain 4,352 W/bias 64-bit reads and
15,840 interleaved X-read/Y-write 64-bit transfers.

Local functional reproduction (2 build jobs):

```sh
verilator --binary --timing --assert -Wno-fatal -j 2 \
  --top-module tb_shared64 --Mdir BUILD_DIRECTORY/obj \
  experiments/s3-y32-4k/fabric/tb_shared64.sv \
  experiments/s3-y32-4k/fabric/xu_dma64_shared_arb.sv \
  experiments/s3-y32-4k/fabric/xu_shared_icb_sram64.sv \
  tools/ppa/generic_ramsp_non_ppa.sv
BUILD_DIRECTORY/obj/Vtb_shared64
```

The supplied generic macro model verifies functional pin behavior and explicit
macro geometry only. These tests do not establish foundry timing, physical area,
official platform eligibility, CPU end-to-end performance, or a 150 MHz result.
Use the actual full-CPU candidate for throughput and the final same-source PPA
flow for implementation claims.

## Local result, 2026-11-10

Native `fabric-r2` passed. Its independently checked receipt, source snapshot,
build log, and simulation log are in
`build/parallel4k-20261110/fabric-r2/`.

| Stream | DMA64 transfers | Concurrent CPU transfers | Cycles | Cycles/DMA64 transfer |
| --- | ---: | ---: | ---: | ---: |
| W/bias, uncontended | 4,352 | 0 | 5,078 | 1.16682 |
| X-read/Y-write, uncontended | 15,840 | 0 | 18,480 | 1.16667 |
| W/bias, CPU contention | 4,352 | 4,352 | 10,154 | 2.33318 |
| X/Y, CPU contention plus response backpressure | 15,840 | 15,840 | 70,468 | 4.44874 |

Uncontended acceptance gaps were 1–2 clocks and accepted-to-response retirement
latency was one clock. The last stream's response backpressure increased maximum
retirement latency to six clocks. The single-outstanding arbiter never misrouted
a response. Full geometry, 131,072 CPU initialization writes, 65,536 DMA64 public
readback beats, all byte masks, seven invalid transactions, 25,344 public Y reads,
and common-reset cancellation passed. Totals: 283,349 accepted, 283,348 retired,
one accepted read cancelled by reset, seven error responses. Observed macro-port
operations: 414,496 reads and 364,316 writes.

The preserved failed `fabric-r1` revealed testbench defects: Verilator localized
the timing timestamps, and the contention source withdrew an unaccepted CPU
offer at the end of its DMA stream. R2 makes shared timestamps observable and
drains a separately bounded CPU stream. No arbiter or endpoint RTL fix was
required. `verify_shared64.py` independently rejects incomplete logs and timing
durations inconsistent with measured acceptance intervals.
