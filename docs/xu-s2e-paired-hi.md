# xu S2e paired-HI readback experiment

Independent worktree `ChipContest-xu-s2e-paired-hi`, branch `codex/xu-s2e-paired-hi`, from frozen S2c main `d276b55ffecbe8d620f9a361bf5d0859299ba7b5` / E203 `49a9436e01ea8ceeead94242e4a99c16e31a0865`. This experiment preserves eight PEs, signed16 operands, signed40 biases, signed48 arithmetic/results, all numerical fixtures, original operand SRAM geometry, the two-slot FIFO, fixed shared SRAM and buses. No Chisel or generated compute SV changes: the existing eight signed48 FIFO outputs already contain the required bits. The actual hardware change is solely handwritten `rtl/e203/perips/accel_icb_slave.v` in E203; firmware, passive TB and host contracts select and verify the new transport.

All previously defined addresses and exact capabilities retain their meaning, including the old HI read's zero-extended response. New addresses previously returned the generic unimplemented response:

| Offset | Read behavior |
| --- | --- |
| `0x0e0` | exact capability `0x58480001` (writes ignored like prior capabilities) |
| `0x140+4*p`, `p=0..3` | `{row_result[2*p+1][47:32],row_result[2*p][47:32]}` from the same owned FIFO head |

Every address byte in `0x140..0x14f` belongs to the new read-only aperture. Writes, unaligned reads, an empty FIFO, inactive row/manual mode, or reads accepted on the same edge as a successful POP retires return zero with response error and no FIFO effect. Successful reads snapshot both halves into the existing response slot. Data/error/valid remain held under response backpressure. FIFO advancement remains exclusively the successful explicit POP response retirement; no packed read automatically pops. The old result windows/capabilities and all original firmware modes remain available.

New firmware schedule `bias-hw-autogroup-paired-hi-window` reuses the original full W/bias loading, packed W/X upload and row/group schedule. Each adjacent pair reads two old LO32 words plus one packed HI word, independently sign-extends each HI16 into the original signed64 two-word Y layout, and writes LO0/HI0/LO1/HI1 in the original order. This distinction matters: the **wrapper response** of an old HI read is zero-extended, while the **canonical Y memory HI32** was already sign-extended by the old firmware cast and checked by the original 64bit TB golden. Both semantics stay exact. For the final pair, all three result reads and the first lane's Y words finish before POP; POP retires before the final lane's last two shared writes. The final shared-Y response retirement remains the timing endpoint.

Per task, results remain25,344 and Y writes50,688. Result MMIO words decrease from50,688 to25,344 LO +12,672 packed-HI =38,016; all23,232 shared operand reads,15,497 MMIO writes,99 row starts,3,168 group starts/dones/POPs and1,622,016 useful lane MACs remain. Poll counts are measured, not predicted. The passive observer checks every returned result word against integer golden, response stability, complete nonduplicate logical word coverage before each POP retirement, canonical Y values/order/full masks, final retirement, and phase coverage. It prints `RESULT_TASK legacy_words=25344 packed_words=12672 logical_words=50688`; old S2c control prints50,688/0/50,688. Report readers reject missing/wrong S2e records.

The new capability probe occurs alongside previous capability probes before the first operand load. No task operands move outside the original measured interval, no prior-task weights are reused, and task clearing/nominal150MHz full-range activity qualification must be integrated with the existing strict S0 clear producer separately. Development TB acceptance does not itself claim the S0 clear/energy/STA gates.

`server_accept.py` appends an old `bias-hw-autogroup-window` real12 control on this **same new RTL** whenever the new schedule is selected. Simulator build identity is independent of the firmware schedule. The new direct helper explicitly supports VCS and fails if VCS is unavailable rather than falling back to Icarus. Full server acceptance, mapped equivalence, complete150MHz STA, library area and full-SoC energy remain required before retention/score qualification. No old S2c PPA is assigned to this new wrapper. If extra CPU operations or newly exposed producer wait make it slower, preserve the failed experiment.

Reproduction (new output directories required):

```bash
python3 -m unittest discover -s tests/e203 -p 'test_*.py' -v
python3 -m unittest discover -s tests/numeric -v
python3 tools/scripts/e203_soc.py --mode real --tasks 12 --sim verilator \
  --firmware-schedule bias-hw-autogroup-paired-hi-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out build/s2e-real12-repro
python3 tools/scripts/e203_soc.py --mode real --tasks 12 --sim verilator \
  --firmware-schedule bias-hw-autogroup-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out build/s2e-control-real12-repro
python3 tools/scripts/server_accept.py --sim vcs --cross-prefix "$XU_RISCV_PREFIX" \
  --firmware-schedule bias-hw-autogroup-paired-hi-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out build/s2e-vcs-accept-repro
```

The host actual-C macro test exercises all65,536 HI16 codes in each lane (524,288 canonical64 results), using the actual macro text rather than a mirrored conversion implementation. The direct test uses real Chisel compute/SRAM/FIFO for two rows/all64 groups/512 lane results; its isolated forced-FIFO extreme-interface phase is explicitly labelled and does not claim impossible signed48 arithmetic extrema from the restricted dot-product/bias input domain. Local numerical checks and tools are development screening, not server VCS or official floating-point accuracy evidence.

`xu_s2e_server_accept.py` is the strict server entry point. It requires full frozen main/child SHAs and clean tracked files, checks the original GCC10.2/VCS2020.03-SP2-6 versions and selected executable identities, freezes runtime source/tool files before and after, requires the mandatory VCS direct marker and all five legacy VCS tests, and checks both complete real12 runs have identical RTL/simulator/tool/vector identities. It records the measured cycle winner without promoting it to PPA/energy retention. It uses Python3.6 standard-library APIs and Git commands with `cwd`, with no `git -C` or network/credential access.

```bash
python3 tools/scripts/xu_s2e_server_accept.py \
  --expected-main "$XU_MAIN_SHA" --expected-e203 a0767db69628ef30e53de2d1e93dd0360c0ccf76 \
  --cross-prefix "$XU_RISCV_PREFIX" --out "$XU_FRESH_SERVER_OUTPUT"
```
