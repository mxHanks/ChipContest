# B41 official32 build manifest

This directory is a reproducible local build copy. It does not claim official server acceptance or score.

## Source and integration

- Source base: `docs/validation/xu-b41-handoff-20261112/reports/s3-y32-portable-software-design-20261110/hardware64-r1/b41-strict-input-r1/source`
- Copied source tree: `source/`
- Adapter: `source/rtl/perips/xu_matrix_dma32_tile.sv`
- Integration point: `source/rtl/subsys/e203_subsys_perips.v`, `XU_MATRIX_DMA` branch instantiates `xu_matrix_dma32_tile` when `XU_MATRIX_DMA64` is absent.
- Frozen evidence was not modified.
- Unused legacy DMA64 and old DMA module files are omitted from this official32 copy so an accidental width-expanded build cannot be selected from the package.

## Defines and top

- Compile define: `XU_MATRIX_DMA`
- `XU_MATRIX_DMA64`: deliberately absent
- SoC top: `e203_soc_top`
- Smoke parameter: `EXTERNAL_SYSMEM=1`
- External memory interface remains native 32-bit (`wdata[31:0]`, `wmask[3:0]`, `rdata[31:0]`).

## Reproducible checks

From the repository root:

```sh
out=output/xu-b41-20261112/official32/source
files=(); while IFS= read -r f; do files+=("$f"); done < <(find "$out/rtl" -type f \( -name '*.v' -o -name '*.sv' \) | sort)
incs=(); while IFS= read -r d; do incs+=("-I$d"); done < <(find "$out/rtl" -type d | sort)
verilator --lint-only --timing -Wno-fatal --top-module e203_soc_top \
  -DXU_MATRIX_DMA "${incs[@]}" "${files[@]}"
```

The lint completed with warnings from historical peripherals and one existing combinational-loop warning around the external shared-memory handshake; there were no errors.

A full elaboration/build smoke test used `tb_e203_soc32_compile.sv` and completed with:

```text
OFFICIAL32_SOC_ELAB_PASS
```

This smoke test only proves complete source elaboration and a 32-bit port shape. It does not replace an official firmware run, timing signoff, power run, or server acceptance.

## Local functional transport smoke

`tb_e203_soc32_functional.sv` connects every required top-level reset/clock and pad input, drives a single outstanding native 32-bit external-memory response, and checks that the 32-bit write data/mask pins stay known. The reproducible command is:

```sh
./output/xu-b41-20261112/official32/build_functional_smoke.sh
```

Observed result:

```text
LOCAL_32BIT_SOC_RESET_GATE_BLOCKED commands=0 shared_rst=0
```

The isolated top-level run did not release `shared_mem_rst_n`, so the endpoint never reached an active transaction window. This is a blocked reset-gate diagnostic, not a transport pass; it provides no performance, output, or DMA-traffic claim. The next step is to reuse the proven board reset/clock harness before interpreting any SoC traffic.

```text
94f0f5ba952b97d1a2719387f0c057ba30c72fc3a8ca8c6f5e005ca6c758e0f3  build_functional_smoke.sh
389ae31b1656f9483aef7d6d19b5ea8f29fba44a2d58cfb16aa1759829c2680a  tb_e203_soc32_functional.sv
```

## Adapter hash

```text
c8e8d785fa6859cb6b0bc74f65c7551288541bc5c1fdfd68b9ef583611b6d0f9  source/rtl/perips/xu_matrix_dma32_tile.sv
```

## Reproducible packing

`output/xu-b41-20261112/tools/pack32.py` performs only the approved offline
representation conversion. For layer 00 it produced 3,168 packed X words,
8,192 packed W words and 256 signed40 bias pairs, and checked the supplied
`w_packed16.mem` against `w.mem` pairwise. The script SHA256 is recorded in
`manifest-sha256.txt`.

A one-command rerun is available at `build_official32.sh`; it rebuilds the complete source list and runs the same elaboration smoke test.
