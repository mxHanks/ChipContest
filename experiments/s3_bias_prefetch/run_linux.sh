#!/usr/bin/env bash
# Run only in the authorized Linux verification environment; never touches RTL.
set -euo pipefail
prototype_dir=$(cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(cd -- "$prototype_dir/../.." && pwd)
output_dir=${1:-"$prototype_dir/build"}
mkdir -p -- "$output_dir"
python3 -B "$prototype_dir/reference.py" --out "$output_dir/vectors"
python3 -B -m unittest discover -s "$prototype_dir" -p 'test_reference.py' -v
iverilog -g2012 -s tb_bias_sram_prefetch -o "$output_dir/tb.vvp" \
  "$repo_dir/third-party/e203_hbirdv2/rtl/e203/perips/Sram1024x16.sv" \
  "$repo_dir/third-party/e203_hbirdv2/rtl/e203/perips/mem_1024x16.sv" \
  "$prototype_dir/bias_sram_prefetch.sv" "$prototype_dir/tb_bias_sram_prefetch.sv"
vvp "$output_dir/tb.vvp" "+VECTORS=$output_dir/vectors"
