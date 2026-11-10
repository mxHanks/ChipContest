# Final-candidate PPA preparation, no synthesis

User order is local RTL/CPU simulation, measured bottleneck, candidate freeze,
then synthesis. This directory only prepares inputs. It contains no server
access, EDA launcher, compile/optimization call, or timing-repair exception.
The old `tools/ppa/xu_soc_ppa_top.sv` stays unchanged.

`xu_soc_dma64_ppa_top.sv` keeps every digital pad visible and preserves the
`u_soc/u_e203_subsys_top/u_e203_subsys_main` hierarchy used by clock review.
Its shared-memory data/response buses are 64 bits, its mask is eight bits, and
`ext_sysmem_cmd_is32` reaches the new endpoint. It connects that endpoint to the
SoC's exported shared-memory clock and reset, not raw external clock/reset pads.
The real shared endpoint still instantiates 256 single-port 1024x16 macros with
the same total 512 KiB capacity. It provides no host loading port or test array.

`prepare.py` accepts an immutable completed CPU result, checks every frozen
source hash, and writes a new directory. By default it requires 12 tasks,
304,128 exact outputs, physical-clear evidence, and warmup. An explicit
`--allow-partial` creates a preliminary input set from a single-layer PASS.
It never copies live production RTL over the frozen CPU snapshot.
Final mode additionally requires the committed R2 DMA hash by default. If a
later optimized DMA is selected, explicitly supply its sealed hash using
`--required-dma-sha256`; the manifest records that choice. Any invocation with
`--allow-partial` remains labeled preliminary even when given a 12-task result.

The final frozen candidate must be **CPU R2 or later**, including the qualified
memory-response error-code fix in child commit
`a80dd184536e0f2312c62768d5acf4ba1b01c34e`. The first local preparation was
explicitly preliminary from R1; its elaboration result is not final R2 evidence.

```sh
python3 experiments/s3-y32-4k/ppa/prepare.py \
  --candidate COMPLETE_CPU_R2_FULL12_DIRECTORY \
  --out NEW_PREPARATION_DIRECTORY --preflight
```

The optional preflight is local Verilator XML elaboration, not synthesis. It
checks actual elaborated instances: 32 ITCM +32 DTCM +256 shared +16 weight +1
bias =337 RAMSP macros, eight engines, 64 PEs, and unique memory scopes. It uses
the generic functional macro model only in its separate preflight command. That
model is excluded from `rtl.f` and must never be synthesized or used for PPA.

Two implementation substitutions are explicit in the manifest:

- Frozen `mem_1024x16.sv` is replaced by the existing
  `tools/ppa/xu_weight_sram_adapter.sv`, connecting its 17 instances to real
  `RAMSP1024X16` macro pins. No behavioral array is counted as a physical macro.
- Frozen `sirv_sim_ram.v` is replaced by the existing
  `tools/ppa/xu_sirv_sram_adapter.sv` for the unchanged ITCM/DTCM interfaces.
  Its tiny debug-RAM fallback remains registers, as in the existing flow.

The 64-bit shared endpoint already uses macro pins and is byte-identical to the
CPU candidate. Candidate-level functional equivalence and the selected foundry
macro model/PVT must still validate the two substitutions. XML elaboration alone
does not prove those obligations.

`hierarchy_contract.tcl` provides read-only collection checks for a future
linked/mapped same-source design. It does not call compile or timing analysis.
Retain hierarchy or replace these checks with a proven equivalent origin map;
do not silently skip missing scopes. Future leaf inventory must uniquely account
for every macro and all added logic.

For area, conservatively charge the complete DMA/core, its 17 internal macros,
the new arbiter/width adaptation, and all changed shared-endpoint standard cells.
List reused CPU, ITCM/DTCM, fixed fabric/peripherals, and 256 shared macros
separately. The 2.25 mm² contest verdict remains unavailable until library area
dimensions and organizer SRAM prices are authoritatively confirmed. A large
excluded shared SRAM must not dilute the charged accelerator area.

The copied full-SoC SDC and clock-review script are labeled **reference** only.
150 MHz system and 32.768 kHz LF are official targets; external HF/PLL startup,
JTAG, ERST/POR pulse width, and board I/O contracts remain incomplete. No new
clock group, false path, multicycle exception, ideal network, or relaxed hold/
gating/removal check is introduced. Historical pre-boundary-repair mapped timing
showed debug-clock setup, bias hold, gate hold, reset removal, and DRC violations;
those numerical reports are not timing results for this new candidate. Fresh
complete coverage and electrical checks are required on its final mapped netlist.

Current preparation status can only be `PREPARED_NOT_SYNTHESIZED`. A completed
preparation or local elaboration PASS is not a 150 MHz, area, formal-equivalence,
official-platform, or contest qualification PASS.
