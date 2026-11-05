# xu private147 full-original-TB adapter

`xu_private147.py` is one foreground Python3.6+ CLI for controller150. It adapts
only observations and the original initialization tasks for the exact S2c mapped
netlist. It always retains a final qualification fatal. Preparation, local checks,
and even reaching the original EXU halt are **NOT_QUALIFIED** for full function,
150MHz/equivalent timing, activity, power, or whole-SoC energy.

The original generated TB is the 122,575-byte file
`simulator/tb_xu_s2c_task_activity.sv` from
`s2c-formal-activity12-20261103-23`, SHA256
`d39016ea50fafe7df8c97dd209702fbc3c4e7eb0e2bb8fded570e427fde6d850`.
Its frozen `result.json` SHA256 is
`6eea4bb5ebddb4e186564ba3610e69fb7a48a72b12f4f0ea777d9f33c6f96e4d`;
the configuration binds the source `accel_icb_slave.v` equations to the included
`frozen-s2c-accel.v`. The original TB header identifies its earlier source TB
`b80fa668...`; that is provenance, not the adapter's input hash. The exact target
mapped netlist is 14,199,670 bytes, SHA256
`9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892`.
`actual133-inventory.json` is the actual same-target static inventory, SHA256
`14a0aec91b4ceca013861ce7f4703142e90a8c762fe8c6da632f28a13ccdabb9`.

The generated TB retains every original statement outside these explicit changes:

- Replace the 241 reads of 72 logical references (149 reads of 60 private
  references). The 58 named private references expand to 72 native bindings;
  adding 12 public ports gives 84. `bias_regs` and `row_result` retain eight lanes.
- Rebuild `busy` and `row_start_accept` inline from the original source's
  four-state expressions. The missing mapped `busy` name is recursively expanded
  into its three bound physical operands. No sampled intermediate combinational
  register or delta-cycle shadow is used.
- At the entry of each original consumer, synchronously copy native VPI vectors
  into exact TB observation registers with `vpiNoDelay`, preserving `aval/bval`.
  All three original always blocks remain at their original edges: PLL controls
  on TB `clk`, reset observation on the real mapped accelerator public `clk`, and
  the scoreboard on TB `clk`. Calls execute before original consumer statements
  and before their NBA updates. Local mocks do not establish native VCS scheduling.
- Replace only the original ITCM and shared preload task bodies with the frozen
  111 packing/readback implementation, separated by original call site and role:
  32 ITCM macros, then 256 shared macros. All 336 native macro memories and all
  256 unique 64-bit words per macro must pass ownership/geometry checks first.
  Arbitrary X/Z initialization is retained. Writes are allowed only to these 288
  original `mem` arrays and allowlisted TB observation registers.
- Remove unused private hierarchy macro definitions/include. Add an unconditional
  qualification fatal immediately before the original `SOC_PASS` site. All 86
  original fatal checks, clear/FIFO/PLL checks, clocks, reset, and original EXU
  PC/GP halt checks remain. HOST+4 ACK continues through the original scoreboard;
  it is never a stop shortcut.

No DUT Q/FF initialization, force, replacement RTL, two-state conversion, altered
clock/reset, timing suppression, or original fatal removal is provided. Original
host-check preprocessor guards disable capture/SAIF only; this adapter produces
no activity or energy artifact. The original X/bias clear checks observe each
write-port address/byte commit plus eight legacy 40-bit bias registers. They do
not directly read all X/bias physical FF storage. Physical storage readback,
native warning/timing qualification, conditional SRAM joint-energy, and all other
unresolved gates remain explicit at the final fatal. The original 111 fatal and
128 diagnostic evidence remain separate and unchanged.

## Stable CLI and controller150 contract

Inspect the machine-readable contract without accessing runtime inputs:

```sh
python3 -B xu_private147.py --describe
```

Prepare in a fresh output directory using the existing server paths:

```sh
xu_base="$HOME/Desktop/xu-score-optimization-20261102"
python3 -B -u xu_private147.py --out "$xu_base/private147-prepared-new"
```

Compile and run the actual mapped target as one foreground process:

```sh
xu_base="$HOME/Desktop/xu-score-optimization-20261102"
python3 -B -u xu_private147.py \
  --capture "$xu_base/s2c-formal-activity12-20261103-23" \
  --macro-inventory "$xu_base/s2c-pt-macro-pin-inventory-20261103-20/inventory.json" \
  --mapped "$xu_base/s2c-ppa-campaign-20261103-01/s2c/ppa/mapped.v" \
  --vendor /storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/verilog/RAMSP1024X16.v \
  --standard "$xu_base/standard-cell-model-private-20261104-90/scc40nll_vhsc40_rvt.v" \
  --vcs /eda/synopsys/vcs/vcs_2020.03-SP2-6/bin/vcs \
  --vpi-include /eda/synopsys/vcs/vcs_2020.03-SP2-6/include \
  --preload-proof "$xu_base/vpi-vendor-preload-primitive-20261104-105" \
  --timeout 21600 --run --out "$xu_base/private147-native-new"
```

`--out` must not exist. There is no background launcher, remote access, or Git
requirement. Upload the six runtime files listed in `manifest147.json` together
into one directory and verify `UPLOAD-SHA256SUMS` before invocation. The remaining
files are local review/documentation only. All CLI paths can be overridden.

The tool freezes helper/input/output hashes and identities before use and checks
them again at exit. Native commands, process groups, return codes, and raw logs
are recorded in `state.json`; timeout/interruption terminates the tool's child
process group. Existing files and prior runs are never rewritten.

Successful preparation exits 0 with:

```
XU_PRIVATE147_TERMINAL PREPARED_FULL_ORIGINAL_TB_PRIVATE147_NOT_QUALIFIED
```

If native execution passes all original checks and reaches the original EXU halt,
the simulator must exit nonzero at the added fatal. The CLI exits 0 only after it
verifies the native fatal's exact generated file, line, message and time; all 84
binding identities; all 336 geometry tags/owners; both preload roles; and ordered
original task/clock/halt markers. Its final line and `state.json.status` are:

```
XU_PRIVATE147_TERMINAL ORIGINAL_TB_EXU_HALT_REACHED_FINAL_QUALIFICATION_GATE_PENDING_NOT_QUALIFIED
```

This is the only expected native terminal status for controller150 registration;
it is an observation milestone with zero private qualification gates discharged.
Other native outcomes, malformed evidence, changed input identities, compilation
errors, and timeouts produce `FAIL_PRIVATE147_NOT_QUALIFIED` and a nonzero CLI exit.
No mode emits a qualification PASS. Preserve the entire fresh output directory
and the controller's stdout/return-code receipt, including failure evidence.

## Local review

From the repository root:

```sh
python3 -B build/xu-mapped-private147/host_checks147.py \
  --out build/xu-mapped-private147/local-checks-new
```

The checker uses original local capture/inventory imports by default and accepts
path overrides. GCC and Icarus Verilog are required. It compiles the complete
generated TB against an explicit structural stub, checks the real generated C
against VPI headers with `-Werror`, executes the real binding/sampling/preload
functions against C VPI mocks, compares reconstructed four-state expressions, and
rejects malformed terminal fixtures. `host-review147.json` records the completed
local run. The mock/stub files never enter the native CLI's source list. These
checks cannot prove mapped behavior, actual native VCS handle availability,
native event scheduling, timing, storage readback, or energy.
