#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
out="output/xu-b41-20261112/official32/source"
files=()
while IFS= read -r f; do files+=("$f"); done < <(find "$out/rtl" -type f \( -name '*.v' -o -name '*.sv' \) | sort)
incs=()
while IFS= read -r d; do incs+=("-I$d"); done < <(find "$out/rtl" -type d | sort)
verilator --binary --timing -Wno-fatal --build-jobs 2 \
  --top-module tb_e203_soc32_functional -DXU_MATRIX_DMA \
  "${incs[@]}" "${files[@]}" \
  output/xu-b41-20261112/official32/tb_e203_soc32_functional.sv \
  -Mdir output/xu-b41-20261112/official32/obj_func
output/xu-b41-20261112/official32/obj_func/Vtb_e203_soc32_functional
