# B41 32-bit shared-memory adapter

This note records the local implementation path that restores the official 32-bit System Bus shape around the 64PE/41-bit tile compute core. It is an implementation and reproducibility record; it is not an official server result.

## Interface contract

The adapter exposes the original memory command width:

- command address: 32 bits
- write data: 32 bits
- byte mask: 4 bits
- response data: 32 bits
- one ordered outstanding transaction, with the existing `xu_dma_shared_arb` selecting the DMA or CPU requester

The accelerator remains behind the existing peripheral control ICB and writes the full output through the shared system memory path. No 64-bit external port, second SRAM write port, or public preload port is introduced by the adapter.

## Packing and transfer counts

For each B41 task, the adapter issues the following 32-bit beats:

| Region | 32-bit beats | Packing |
| --- | ---: | --- |
| X | 3,168 | two signed INT16 values per word; logical row stride is 128 bytes |
| W | 8,192 | two beats per four-lane 16-bit weight load; the second beat commits the load |
| bias | 512 | low 32 bits followed by the high 8 bits of each signed 40-bit bias |
| Y | 25,344 | one 32-bit output word per write |

Total traffic is 11,872 reads and 25,344 writes, or 37,216 memory requests per task. These counts are local adapter evidence and must be checked again in the official server run.

## Local checks

- Standalone 32-bit adapter simulation passed all 12 frozen layers with bitwise comparison of all 25,344 Y words per layer.
- Full E203 source tree, with `XU_MATRIX_DMA` set and `XU_MATRIX_DMA64` absent, passed Verilator lint and a complete `e203_soc_top` elaboration/build smoke test. The reproducible command is in `output/xu-b41-20261112/official32/build_official32.sh`.
- The smoke test output is `OFFICIAL32_SOC_ELAB_PASS`. It does not establish official firmware, timing, power, or scoring acceptance.

There is also a local diagnostic fixture, `output/xu-b41-20261112/official32/tb_e203_soc32_functional.sv`, which connects the native 32-bit `e203_soc_top` external pins to a single-response behavioral SRAM. Its current standalone AON reset sequence does not release the top-level shared-memory reset, so the run is recorded as `LOCAL_32BIT_SOC_RESET_GATE_BLOCKED` when it observes zero requests. That is a reset-environment limitation, not a transport pass; the functional regression still needs the existing project boot/reset harness or the official server environment.
