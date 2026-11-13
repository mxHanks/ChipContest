# Opt-in X SRAM candidate

This directory prepares and verifies an isolated64PE B41 core overlay. It does
not install production RTL. The shared512KiB SRAM, W16 macros, bias1 macro,
CPU, arithmetic engines and MAC state sequence are unchanged.

The selected branch uses16 known1024x16 single-port SRAMs, one per X set/row.
Logical X remains2KiB; physical X is32KiB. Internal SRAM count rises17→33.
All16×1024 physical addresses are cleared on every task clear, concurrently
with the existing1024-step W clear. Complete physical work is33536 words;
the existing W-plus-X-only MMIO counter reports32768 words.

Both defines are required:

```text
XU_MATRIX_DMA_SYSBUS32
XU_MATRIX_X_SRAM
```

Every other combination retains the original B41 top verbatim and the original
`TileXRowBuffer`, including packed writes. The new module has the distinct name
`TileXMacroRowBuffer` and accepts scalar16 writes. Current32-bit DMA already
ties packed=0. The new X synchronous request uses weightRen/weightReadK so X
and W arrive together without changing INIT/RUN/CAPTURE/DONE or MAC count.

Prepare a new isolated directory and inspect fallback identities:

```sh
python3 -B experiments/s3-y32-compliant32/x-macro/prepare_candidate.py --out build/NEW/candidate
python3 -B experiments/s3-y32-compliant32/x-macro/verify_overlay.py --candidate build/NEW/candidate --out build/NEW/overlay-review.json
```

Run the complete module campaign. The vector root must contain layer_00 through
layer_11, each with x/w/bias/y/y32 memory files. `--smoke-only` uses rows8/stall0;
the complete campaign also uses rows1/3 and stalls31/255.

```sh
python3 -B experiments/s3-y32-compliant32/x-macro/run_core.py --candidate build/NEW/candidate --vectors build/area-opt-20261111/cpu/b-full12-r1/vectors --out build/NEW/core --tasks 12 --jobs 2
python3 -B experiments/s3-y32-compliant32/x-macro/run_dma.py --candidate build/NEW/candidate --vectors build/compliant32-20261113/numeric/dev-vectors-r1 --out build/NEW/dma --jobs 2
```

`run_dma.py` copies the existing32-bit fixtures into its new source directory.
It changes only the W-plus-X counter expectation, adds the new overlay defines,
and adds a passive real-macro observer. It retains full12 output, read/write
fault recovery, command/response stalls, rows1, final-Y-response hold and common
reset recovery. The observer requires prior public dirty data after a completed
task; an aborted/reset task may leave some categories clean. All physical zero
write/address coverage is required on every clear. The strict module campaign
separately proves every used X address had public nonzero data before clearing.
Some reused fixture JSON scope strings still describe their historical source;
the new receipt pins the actual33-internal-macro overlay and defines the scope.

The observer generator is self-contained and may be copied into a CPU source
snapshot. Its interface matches the existing CPU observer generator:

```python
generate(output, mode='cpu', core='`CORE', clock='shared_mem_clk',
         owners_idle='...', snapshot_zero='...', warmup='warmup_active')
```

It writes the requested instance include and adjacent
`tile_physical_observer.sv`. `mode='bind'` writes the module and local bind.
It observes actual CEN/GWEN/WEN/A/D/RET1N of W/bias/X macros, keeps the original
ACC/result/FIFO/bias-cache zero checks, and replaces register-X enumeration with
all physical SRAM write-address coverage. Unused physical words are never
claimed to have public dirty prestate. SRAM Q is not claimed to reset on writes.

Validated evidence on2026-11-13:

- `build/compliant32-20261113/x-macro/candidate-r2`: final conditional overlay.
- `overlay-review-r2.json`: default/one-define fallbacks equal original core
  preprocessing tokens; six unchanged dependencies match original bytes.
- `core-r3`:60 cases across12 layers,1520640 regular raw48/Y32 exact outputs,
  plus endpoints, reset/abort and dirty/full-physical-clear checks.
- `dma-r2`:304128 full12 Y32 outputs,76032 postreset outputs, fault/stall/rows1
  and97-edge final write response hold checks,289 functional macros including
  shared SRAM. Full12 local DMA cycles608358 equal the original32-bit unit.
- `observer-api-r1`: copied-generator API and tested bind byte identity.

These are functional generic models. They provide no vendor timing, area,
power,600-audio accuracy or achieved150MHz qualification. The new macros must
be counted and priced in a fresh matching synthesis result.
