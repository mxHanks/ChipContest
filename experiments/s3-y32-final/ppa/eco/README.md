# Final374 map-bound timing diagnosis and bounded delay ECO

This flow accepts only the final DMA4/storage21 production profile, its actual
same-source GPIO12 PASS, its own final.svf/map and a completed same-map native PT
collection. It never accepts old353 map/pin identities. Default runner mode only
reviews inputs; the coordinated native owner explicitly uses `--run`. Every
native stage is sequential and at most2 cores; preexisting processes remain
untouched. No transport, credentials or service-control code is present.

The old353 bias experiment proved that3 characterized BUFV2 cells per old bias-D
input improved its16 target margins. It did not persist/reload a map and left551
timing rows plus unchanged DRC. Those pin names and counts are deliberately absent
from this final tool package. The actual final374 map decides current targets.

First freeze tools locally, with no EDA:

```sh
python3 -B experiments/s3-y32-final/ppa/eco/prepare.py \
  --out build/s3-y32-final/ppa/eco-tools-r1
```

After the final native DC/PT outputs exist, catalog every violated coverage check
and create an explicit plan bound to THAT mapped.v/DC/PT/coverage SHA:

```sh
python3 -B /path/to/eco-tools-r1/plan.py --baseline /path/to/final/candidate \
  --families bias_D,weights_D,result_D,x_D,gating_enable --out /new/path/target-plan-r1
```

The catalogue must reconcile every check kind and total violated count. Negative
printed zero stays violated. Only currently violated characterized SRAM-D or
gate-enable hold endpoints are selected for possible delay edits. Other interface
hold, recovery/removal and output/clock setup checks remain visible and require
their actual contracts; this tool does not cut or automatically modify them.
Use a smaller `--families` subset for a bounded first experiment. Every new plan
starts from the original final baseline; separate plans are not silently composed.

For a clock-tree diagnosis, optionally pass one or more `--clock-root EXACT_PIN`
from the CURRENT native path/map. These are read-only drivers: the native stage
exports actual local segment members, owner and clock association, without
inserting any clock buffers. Cross-owner leaf grouping is not a valid tree plan.
The root fanout/load and same-owner grouping must be measured before a separate
bounded clock-tree edit is designed and probed.

All native stages require the same target plan and immutable baseline. Run
`run_stage.py` without `--run` first. The execution owner may then add
`--run --allow-coordinated-busy-jobs --coordination-note` with the recorded existing
user coordination. Example sequence (paths are placeholders, no credentials):

```sh
python3 -B eco-tools/run_stage.py --stage diagnose --baseline final/candidate \
  --targets target-plan/targets.json --out runs/diagnose
python3 -B eco-tools/run_stage.py --stage probe --baseline final/candidate \
  --targets target-plan/targets.json --prior runs/diagnose --out runs/probe
python3 -B eco-tools/run_stage.py --stage edit --baseline final/candidate \
  --targets target-plan/targets.json --prior runs/probe --out runs/edit
python3 -B eco-tools/run_stage.py --stage apply --baseline final/candidate \
  --targets target-plan/targets.json --prior runs/edit --out runs/apply
python3 -B eco-tools/run_stage.py --stage reload --baseline final/candidate \
  --targets target-plan/targets.json --prior runs/apply --out runs/reload
```

`diagnose` edits nothing. It validates exact native SRAM input/owner or AND A1 /
A2 / latch-EN topology, captures every clock/rise/fall min/max context with a
nontruncation guard, complete touched local net members, full native reports and
original clock associations. `probe` inserts exactly one characterized local-load
buffer into the first explicit target and proves native API identity/connectivity.
The plan SHA must match across diagnose→probe→edit→apply→reload.

`edit` starts again from the original mapped.v. It uses only the selected exact
targets and refuses insufficient setup margin, more than the declared buffers per
pin/total/area limits, unknown/missing timing contexts or protected clock/latch
changes. Hold/setup margins of0.03ns are experiment stopping criteria, not changed
constraints. Endpoint logs include an explicit phase field, avoiding the old
assumption of one timing path per clock context. No parameter/result RTL storage,
data semantics, IO constraints, clocks, uncertainty, gating checks, exceptions or
CPU/LSU/BIU RTL are changed.

Every PT stage first runs a separate serial DC characterized I→Z function query
against the exact same DB; PT's absent lib_pin.function attribute is never used.
Changes are exported with native `write_changes -format dctcl`. `apply` reads the
ORIGINAL mapped.ddc, records its own `eco.svf`, replays only native changes without
compile/optimization, checks374/54 hierarchy, and writes new map/ddc/sdc plus leaf
and area inventories. `reload` is a new PT process on that persisted map, under
the unchanged original SDC (only the proven three generated-clock `-add` edits),
and checks all original register/SRAM clock associations survived.

All full before/after/persisted coverage, all-violators, group min/max, gating,
recovery/removal, pulse, electrical DRC and exception reports remain required and
are individually receipt-bound. Collection/probe success is never closure. The
complete final map still needs independent coverage/CDC/reset and electrical
review, library-area/mm²/official macro pricing, RTL→mapped formal consistency,
and same-configuration power/activity validation.

After native outputs return, the reused `check_buffer_equivalence.py` can prove
map-to-map connectivity by contracting only receipt-bound characterized identity
buffers. It is not RTL→mapped formal proof, a clock-glitch proof, or qualification.
