# Server DC synthesis review checklist

Input is the final R3 full digital SoC (CPU/TCMs/original fabric, new DMA/arbiter,
shared 512 KiB endpoint and two-row core). This is a **new unqualified mapping**.
The two declaration overlays have independent local equivalence evidence;
this does not establish SRAM adapter or mapped-netlist equivalence.

## Completion and identity

- Preserve R1 VER-956 and R2 VER-262 analysis failures separately; neither
  reached mapping. R3 may pass only with a real terminal return code, complete
  DC log, explicit completion marker, mapped.v/DDC/SVF and returned reports.
- Reconcile exact input manifest/library SHA/tool identity against execution;
  no source drift. Invoke the original dc_shell basename, not its resolved
  snps_shell symlink target.
- Require two exact count sets, before and after compile: ITCM32, DTCM32,
  shared256, W16, bias1, total337. CPU, peripheral fabric, arbiter, new DMA,
  core and both engines each remain; old accelerator instance count is zero.
- Distinguish an ongoing job, failed analysis, failed mapping, complete
  synthesis and incomplete report collection. A live log or directory alone
  is not terminal evidence.

## Area interpretation

- `area.rpt` top must be xu_soc_ppa_top. **Total cell area includes SRAM macro
  area**. It is not accelerator-only area, die area, routed area or a score.
- Recompute every nonhierarchical leaf from leaf-inventory.tsv. Separate
  standard cells, 337 SRAM macros and explicit native zero-area constants.
  Reconcile standard+macro area against total cell area and leaf summary.
- Buf/Inv area is already included in combinational area; do not add it twice.
  Hierarchical cell counts can make report Number of cells differ from the
  leaf count; this does not alone show missing physical cells.
- Classify DMA/core, arbiter, shared endpoint, CPU and other SoC leaves by full
  instance path. DMA component includes W/bias macro area; report its
  standard-cell contribution separately if useful.
- Record actual library names, corner/voltage/temperature, units and SHA.
  Retain library area units until area dimensions are verified. No valid area
  delta or 25% judgment exists without a matching same-condition baseline.

## Timing interpretation

- SDC uses hfclk6.666666667ns, lfclk30517.578125ns, JTAG100ns, and conservative
  divider envelope at source rate; uncertainty/transition/gating checks0.1ns.
  Other I/O0.5ns max/0min, JTAG5ns max, load0.01 library-capacitance units.
  No new false/multicycle/clock-group exceptions or reset case assumptions.
- DC setup/hold reports are **screening**, not standalone PrimeTime STA. Print
  their worst finite slacks and path counts. Negative slack means violations;
  no finite path is missing evidence. Positive reported slack is insufficient
  for closure without coverage, reset, gating, pulse-width and cross-domain
  review. Actual placement/wiring/parasitics are absent.
- Check check_timing, clock endpoints and all warning/error codes. Especially
  TIM-276: hf/lf period ratio can exceed expansion1000, leaving crossings
  unconstrained. Do not hide this with false paths. TIM-128/141 gating and
  TIM-099 multiple clocks require interpretation. TIM-134 high-fanout delay
  approximation and undefined net interconnect area limit physical inference.
- `NO_CLOCK_ENDPOINTS=0` is necessary, not sufficient. Missing PT-only coverage,
  recovery/removal/gating/pulse-width reports remain explicit missing checks.
  The legacy clock reporter can emit literal backslash-n/backslash-t; the
  parser decodes these only for those known scalar report fields.
- Formal qualification, mapped whole-SoC functional equivalence, SRAM EMA/PVT
  eligibility, power and contest allowance stay unverified unless separately
  supported by new authoritative evidence.

## Local parser (read-only, no EDA)

```
python3 build/server-dma-synth-20261109/review/inspect_reports.py \
  --root /returned/final/candidate --out /new/local/review.json
```

The root should include the frozen candidate inputs plus returned output
artifacts. A partial selected-artifact return remains explicitly partial. The
parser hashes requested artifacts, verifies present runner-recorded outputs,
checks inputs and before/after hierarchy counts, reconciles leaf area and
classifies printed DC slacks/coverage warnings. It never claims STA/formal
qualification, area growth or 25% compliance. Original reports remain primary.
