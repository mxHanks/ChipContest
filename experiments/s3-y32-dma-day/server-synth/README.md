# 2026-11-09 server synthesis of the DMA candidate

The input is the **CPU full12 R2 frozen source**, not merely the installed E203 gitlink. Its three generated core overrides are pinned in source-identity.json. The server run uses a new isolated candidate flow; historical manifest gates are not overridden.

Local evidence root: `build/server-dma-synth-20261109/`.

- Parent: `66cd66da3d2416c6b2f7cc8f3f45f87aa609ffbf`.
- E203: `79c8af1cd92589ddeb3f49edb5b9e4454fcf8efa`.
- Full12 functional receipt SHA256: `47a7c6de0d16280d95d9d329114e9f117fd835d0ac83b96b22c7c7912ebec62a`.
- Top: `xu_soc_ppa_top`; defines: `SYNTHESIS DISABLE_SV_ASSERTION=1 XU_MATRIX_DMA`.
- Full digital SoC includes CPU, original peripheral fabric, independent DMA/arbiter, shared 512KiB SRAM endpoint and shared-weight two-row core.
- Expected SRAM macros: ITCM32 + DTCM32 + shared256 + W16 + bias1 = **337**.
- DC: `dc_2022.03-SP5-5`, at most two cores, preserved hierarchy.
- Standard library SHA256: `f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723`.
- SRAM library SHA256: `c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f`.
- Both library names identify SS0.99V125C. Area units and timing evidence must be read from the returned reports.

R1 and R2 stopped during source analysis, before technology mapping. R3 retains both attempts and uses declaration-only DC compatibility overlays. Independent local proofs cover 1907 DMA wrapper bits and 3519 subsystem boundary/state bits, with zero unproven bits. These proofs are not whole-SoC mapped-netlist equivalence.

The R3 full input archive is `prepare-r3/s3-y32-dma-server-synth-candidate-r3.tar.gz` (SHA256 `61953cbb970441e860d22cc1582c6a1052d3e9965c3543ab4c125da5a28a4bf0`). Extract into a new directory, verify every package-files.json hash, and invoke run_once.py with explicit standard/SRAM DB paths and hashes. Invoke the original dc_shell path, preserving its basename. The runner refuses overwriting a prior experiment.

The SDC uses a 150 MHz HF clock, 32.768 kHz LF clock, 10 MHz engineering JTAG clock and conservative divider envelope, with no false paths or clock-group cuts. DC timing is screening. Standalone STA, mapped functional equivalence, physical implementation and formal contest qualification require separate evidence.

Native returns are independently SHA256-checked over the authorized VNC session because the FTP service accepts uploads but rejects downloads. Credentials and library binaries are excluded from all delivery archives.

Read-only post-report recovery loads the exact mapped DDC, invokes no compile command, and exports native check_timing plus clock-pin inventories. Its receipt pins the original DDC/tool/libraries. This fixes report-command portability only; two AON endpoints remain unconstrained and hold/DRC violations remain. See docs/s3-y32-dma-server-synth-results.md.

Actual tool compatibility limitation: the archived synthesis flow queried design.is_black_box, which this DC version does not provide. That guard was ineffective. The executed per-leaf is_mapped/positive-area checks and exact hierarchy/macro inventory remain evidence; this flow must not be described as a clean formal qualification gate. The original run is preserved rather than silently repaired.
