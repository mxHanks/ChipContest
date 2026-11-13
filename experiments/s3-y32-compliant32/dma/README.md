# 64PE B41 over the32-bit System Bus DMA boundary

`xu_matrix_dma_sysbus32.sv` keeps the published64PE B core, INT16 X/W,
INT40 bias and Y32/RNE9 semantics. Its configuration ABI remains the64PE ABI,
with capability `0x00082001` (8 rows,32-bit data, original X32 slots).
Control=1 performs physical clear,0x802 starts8-row tiles and2 is one-row mode.
The final tile has3 rows. All memory requests have32 data bits/four mask bits;
there is at most one ordered outstanding request, with stalled commands locked.

Per full task:8192 W reads +512 bias reads +6336 X reads =15040 reads,
25344 Y32 writes,40384 requests and retired responses,3168 POPs,26624 MAC
steps in8-row mode. Source/destination layouts and MMIO offsets are unchanged.
The frozen core loads four16-bit W banks at once, so the peripheral stages the
first32-bit W word, then loads four banks when the second32-bit response
retires. This internal pairing never widens the external32-bit request/response.
Bias likewise joins two32-bit responses into40 bits. X uses unpacked single
low16 loads, while all eight Y32 values are emitted as separate32-bit writes.
Staging payloads reset and physically clear. A response error aborts the task,
retires every promised/inflight transaction, prohibits automatic retries and
cannot produce completion. Common reset cancels DMA/arbiter/endpoint ownership.

Run from the repository worktree with a fresh output directory:

```sh
python3 experiments/s3-y32-compliant32/dma/run_dma.py \
  --vectors build/area-opt-20261111/cpu/b-full12-r1/vectors \
  --out build/compliance-64pe-20261113/dma/NEW_RUN
```

The runner freezes the actual input sources, uses at most two compile workers,
and exercises the original32-bit `xu_dma_shared_arb` and `xu_shared_icb_sram`.
The endpoint's `sirv_sim_ram` interface is implemented by256 functional
`RAMSP1024X16` instances through `xu_sirv_sram_adapter`; tensors are only written
and read through accepted public32-bit transfers. No DUT array backdoor or ideal
sink is used. Tests cover task0,12 independent layers, response backpressure,
one-row comparison, first read/write errors, final response held97 cycles,
and common reset followed by complete execution of a different parameter task.

This unit harness does not execute the CPU or the full original System Bus.
Its CSR/source-to-response timings exclude fixture loads and are diagnostic
regressions, never the official task throughput. The root CPU integration
must use the original System Bus and count from the first X/W/bias loading
request to the final Y response. No area, STA, power or official600-sample
qualification is implied by these functional simulations.

Address-targeted staging-error extension, reusing the exact frozen RTL model:

```sh
python3 experiments/s3-y32-compliant32/dma/run_fault_staging.py \
  --model build/compliance-64pe-20261113/dma/UNIT_RUN \
  --vectors build/area-opt-20261111/cpu/b-full12-r1/vectors \
  --out build/compliance-64pe-20261113/dma/NEW_FAULT_RUN
```

This extension injects an error at W low/high, bias low/high, X, first Y and
last Y addresses, then fully checks a different parameter layer after clear.
It pins every reused model archive/object/header and each source/vector input.
The initial unit run is retained with its frozen driver; the extension adds an
address selector only in its newly compiled C++ driver, without changing RTL.
