#!/usr/bin/env bash
# Full original S2c mapped SoC; no simulator or wrapper replacement is used.
set -euo pipefail
if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "usage: $0 SERVER_CAMPAIGN_ROOT NEW_OUTPUT [PT_SHELL]" >&2
  exit 2
fi
xu_campaign_root=$(cd "$1" && pwd)
xu_new_output=$2
xu_pt=${3:-pt_shell}
xu_tool_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
xu_python=${XU_PYTHON:-python3}
"$xu_python" "$xu_tool_root/tools/ppa/xu_s2c_full_soc_power.py" prepare \
  --activity "$xu_campaign_root/s2c-formal-activity12-20261103-23/result.json" \
  --source-root "$xu_campaign_root/ChipContest-s2c-02" \
  --mapped-sram-inventory "$xu_campaign_root/s2c-pt-macro-pin-inventory-20261103-20/inventory.json" \
  --out "$xu_new_output"
xu_lc_args=()
if [[ -n ${SYNOPSYS_LC_ROOT:-} ]]; then
  xu_lc_args=(--lc-root "$SYNOPSYS_LC_ROOT")
fi
"$xu_python" "$xu_tool_root/tools/ppa/xu_s2c_full_soc_power.py" run \
  --out "$xu_new_output" --pt "$xu_pt" --timeout 21600 "${xu_lc_args[@]}"
