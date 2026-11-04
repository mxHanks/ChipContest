# xu S2e local screening

This archive preserves local development evidence. Paired-HI completed all12 layers in10,827,459 cycles; the old autogroup schedule on the same physical RTL completed in12,158,052 cycles, a10.94413% reduction. [The CSV](per-layer-comparison.csv) records each layer. All304,128 results and608,256 canonical Y writes were checked in each run; actual result MMIO reads are38,016 versus50,688 per task.

These runs use GCC14.2 and Verilator5.032. Their actual main metadata are respectively `b01a895de807751879bb6b5421d6724fa7d77434` and `a5446640d4236df9a05458d127d5989e2797a58e`: the latter adds only the server entry, its tests and documentation. Actual compiled RTL, runner, contract, simulator binary, vectors, tool identities and child `a0767db69628ef30e53de2d1e93dd0360c0ccf76` are identical. These facts establish local screening with the documented metadata difference; the server entry requires both runs at the same full frozen main commit. The interrupted old control output is retained; the completed control uses a fresh directory and did not replace the original paired result.

Local host checks pass64 tests and numerical checks pass42. The real direct wrapper test uses Chisel compute/SRAM/FIFO for2 rows,64 groups and512 results. Four behavioral RTL mutations (swapped HI halves, zero odd-lane HI, accepting an unaligned read, accepting a packed write) each compile and then fail the original direct test; its unchanged positive control passes. Separate forced-FIFO extreme patterns are labelled as interface diagnostics rather than MAC arithmetic evidence. All192 old configurations (8 schedules ×3 optimization levels ×8 experiments) have identical original/current compiler definitions and exact load images under the local compiler; the strict server entry repeats that test with GCC10.2 before VCS.

No Chisel or generated compute SV changes are present. The production hardware change is handwritten E203 `rtl/e203/perips/accel_icb_slave.v`; firmware `tests/e203/firmware/accel.c` selects the new transport and restores canonical signed64 Y words. Original signed16 operands, signed40 bias, signed48 arithmetic, old ABI addresses, old HI zero-extension, SRAM geometry and FIFO ownership remain fixed. The additive capability and packed HI aperture are described in [the experiment document](../../xu-s2e-paired-hi.md).

This does not establish server VCS acceptance, full nominal150MHz/clear activity, mapped equivalence, area, whole-SoC energy, official floating-point accuracy or retention. No S2c area/energy result is assigned to the changed wrapper.

```bash
cd /home/mxhanks/Projects/ChipContest-xu-s2e-paired-hi
python3 docs/validation/xu-s2e-paired-hi-local-20261104/check-evidence.py
python3 -m unittest discover -s tests/e203 -p 'test_*.py' -v
python3 -m unittest discover -s tests/numeric -v
python3 tools/scripts/e203_soc.py --mode real --tasks 12 --sim verilator \
  --firmware-schedule bias-hw-autogroup-paired-hi-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out build/xu-s2e-paired-reproduce-fresh
python3 tools/scripts/e203_soc.py --mode real --tasks 12 --sim verilator \
  --firmware-schedule bias-hw-autogroup-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out build/xu-s2e-control-reproduce-fresh
# On the original server, using a fresh deployment/output:
python3 tools/scripts/xu_s2e_server_accept.py --expected-main "$XU_MAIN_SHA" \
  --expected-e203 a0767db69628ef30e53de2d1e93dd0360c0ccf76 \
  --cross-prefix "$XU_RISCV_PREFIX" --out "$XU_FRESH_SERVER_OUTPUT"
```

`manifest.json` binds every original raw file's bytes and SHA256, including both simulation logs/results, full192-configuration build products, exact load images, direct checks, mutants, earlier failed entry probes and the final independent review. `raw.tar.xz` preserves those bytes; `check-evidence.py` checks every member and parses the complete results. Old failed probes remain evidence of the corrected defect and are not promoted into passes.
