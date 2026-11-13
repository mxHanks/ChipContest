# Bounded mapped-cell ECO: selected32bit SystemBus +64PE +16X SRAM

These tools are **prepared, not native-executed**. They do not establish a timing,
area, power or contest PASS. The source RTL, CPU/LSU/BIU state machines, original
SDC and library bytes are unchanged. No constraint, false-path, ideal-clock,
clock-group, uncertainty or gating-check relaxation is allowed.

The native baseline must first finish its own353-macro DC and PT collection.
Every stage rechecks all baseline sealed inputs, native mapped output identities,
libraries, original SDC and preceding stage receipt. Each tool is max2cores.
Default execution only reviews sealed inputs; `--run` is explicit. The runner has
no remote transport, credentials, service control or other-job termination code.
Only a process group launched by this invocation may be terminated on its timeout.

## Execution by the one coordinated EDA owner

Locally freeze tools (no EDA):

```sh
python3 experiments/s3-y32-compliant32/ppa/eco/prepare.py \
  --out build/compliant32-20261113/eco-tools-r1
```

Transfer this whole sealed tools directory using the established authorized
transport. On the server use the actual completed candidate location and a new
output directory per invocation. Example variable assignments contain no secrets:

```sh
eco_tools=/tmp/codex-compliant32-eco-tools-r1
eco_base=/tmp/codex-compliant32-20261113-r2/candidate
eco_runs=/tmp/codex-compliant32-eco-r1
```

First review, then execute the real one-buffer API probe. The probe loads this
candidate's mapped.v; queries native command manuals, pin clocks collection,
actual bias SRAM D pins, full original leaf library pin directions, characterized
BUFV2 I/Z/function/area; inserts exactly one local load buffer; verifies real
returned new-cell identity, touched net membership and original clock association;
exports native `write_changes -format dctcl -output`, ptsh and descriptive text.
A syntax/API/topology failure is terminal evidence, never converted to a pass.

```sh
python3 "$eco_tools/run_stage.py" --stage probe --baseline "$eco_base" \
  --out "$eco_runs/probe"
python3 "$eco_tools/run_stage.py" --stage probe --baseline "$eco_base" \
  --out "$eco_runs/probe" --run --allow-coordinated-busy-jobs \
  --coordination-note 'User coordinated one independent max2core synthesis/STA job; all preexisting jobs remain unchanged.'
```

Only after this probe completes cleanly, run a bounded delay experiment. Use
`--mode bias`, `gating` or `bias-gating`; each starts from the same unmodified
baseline. The15 old gate anchors are checked against the NEW native mapped gate
inputs, AND reference, adjacent clock and latch enable topology. They are not
assumed to exist or to prove current violations. Changed topology requires a new
native diagnosis and explicit script revision.

```sh
python3 "$eco_tools/run_stage.py" --stage edit --baseline "$eco_base" \
  --prior "$eco_runs/probe" --out "$eco_runs/edit-bias" --mode bias --run \
  --allow-coordinated-busy-jobs \
  --coordination-note 'User coordinated one independent max2core synthesis/STA job; all preexisting jobs remain unchanged.'
```

The hold margin is0.03ns, setup margin0.03ns, max8 buffers per pin,248 total and
1000 raw characterized area units by default. These are experiment guards, **not
extra false constraints or claims of measured margin**. The scripts query each
launch clock and capture transition (rise/fall), retain capture clock and group,
and fail on query truncation, missing or nonfinite paths. A target with insufficient
setup margin stops. Only an exact local input load is buffered; clock pins and
clock/latch-enable nets are protected. Whole-SoC before/after coverage, all
violators, setup/hold, recovery/removal, gating, pulse, DRC and exception reports
remain visible. A local hold improvement does not establish global closure.

Persist the actual native exported DC Tcl against the ORIGINAL mapped.ddc, with
no compile/optimization, then save mapped.v/ddc/sdc and a complete new leaf/area
inventory. This avoids the previously failed unsupported PT Verilog export path.

```sh
python3 "$eco_tools/run_stage.py" --stage apply --baseline "$eco_base" \
  --prior "$eco_runs/edit-bias" --out "$eco_runs/apply-bias" --run \
  --allow-coordinated-busy-jobs \
  --coordination-note 'User coordinated one independent max2core synthesis/STA job; all preexisting jobs remain unchanged.'
python3 "$eco_tools/run_stage.py" --stage reload --baseline "$eco_base" \
  --prior "$eco_runs/apply-bias" --out "$eco_runs/reload-bias" --run \
  --allow-coordinated-busy-jobs \
  --coordination-note 'User coordinated one independent max2core synthesis/STA job; all preexisting jobs remain unchanged.'
```

The last stage is a fresh PT process on **DC-persisted mapped.v**, reusing the
original source SDC with only the previously native-proven three generated-clock
`-add` portability substitutions. It verifies all original register/SRAM clock
associations survived persistence. Collection completion always stays
`NOT_TIMING_CLOSURE`; review every actual global violation, design-rule issue and
untested/CDC/reset reason before making a closure claim.

## Equivalence boundary and identities

Every edit writes complete before/after leaf and net inventories, touched local
net membership, per-edit real cell/reference/old-net/area, original clock map,
per-clock/transition endpoint slacks and delta inventories. Original mapped leaf
identity/type may not disappear or resize; every added leaf must be the native
noninverting I/Z buffer. No inferred name-only equivalence is accepted.

After raw native artifacts return locally, prove persistence connectivity:

```sh
python3 "$eco_tools/check_buffer_equivalence.py" \
  --original "$eco_base/mapped.v" --candidate "$eco_runs/apply-bias/mapped.v" \
  --top xu_soc_sysbus32_ppa_top \
  --function-proof "$eco_runs/edit-bias/function-proof.json" \
  --out-dir build/compliant32-20261113/eco-equivalence-bias-r1
```

This reused checker flattens design hierarchy, keeps every original mapped leaf
opaque and named, contracts only native-receipt-bound characterized identity
buffers, compares every original port/bit/parameter and rejects reconnections,
added logic, cycles, new multiple drivers and missing native pin directions.
Its proof is **mapped-to-mapped buffer-contraction structural equivalence**.
It is not RTL-to-mapped formal equivalence, clock-glitch proof, STA, SRAM model
validation or power qualification. A full functional formal/mapped validation
still needs its own evidence; unchanged RTL CPU tests alone cannot prove mapping.

Area reports retain raw library units. The separate conservative upper bound is
all fullSoC standard cells plus33 internal SRAM macros, excluding only320 reused
CPU/shared macros. Do not add that upper bound to named accelerator charges or
claim mm² until area dimension and official macro prices are established.

Old diagnostic anchors: `build/compliance-64pe-20261113/timing/old-b-catalog-r2`.
The33-macro candidate is newly measured; old64PE or16PE timing is not substituted.

Local checker fixtures can run without EDA:

```sh
python3 experiments/s3-y32-compliant32/ppa/eco/check_buffer_equivalence.py \
  --self-test --out-dir build/compliant32-20261113/eco-checker-selftest-r1
```

No native ECO result exists until the corresponding native receipt, reports,
exported changes, DC-persisted artifacts and fresh PT reload are actually present.
