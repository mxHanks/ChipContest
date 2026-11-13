# Original1064 N3 map-bound timing diagnosis

These tools accept only the new sysbus32-x-sram-353-dev-n3 profile:353 macros,
33 internal, TEST_LOADER enabled, exact source and original1064 developer result.
They require this package own clean DC/SVF and same-map PT receipts. The original
CPU289/physical353 modeling difference remains explicit; no production SDK claim
is introduced. No old353 or final374 map/pin identity is inherited.

All current coverage kinds and every native violation must reconcile, including
new sysbus_load port names. Current native SRAM-D, register data-D or gating-enable endpoints may
be selected for bounded experiments only after actual topology and one-buffer
API diagnosis. Native characterized buffer function is queried in serial DC; no
PT function attribute is assumed. Other IO/clock/reset checks remain visible.

The explicit new resource authorization is cap8 with affinity to8 allowed CPUs
and at least2 other allowed CPUs reserved. Native host-options is required. One
own EDA stage runs at a time; preexisting jobs are never modified. The original
150MHz SDC, DB identities and constraints remain unchanged. No RTL is changed.

Stages are diagnose → probe → edit → DC apply with own eco.svf → fresh PT reload.
Each prior stage, plan, full report and exact map is SHA bound; full baseline and
persisted coverage/DRC remain required. No collection success certifies closure.
Prepare freezes tools locally; run_stage.py defaults to input review and requires
explicit --run for execution. Never run until the main DC/PT stage has finished.

If the first candidate/pt collection failed, preserve that directory. Both
plan.py and run_stage.py accept --baseline-pt-dir for an explicitly selected
successful same-DC recollection. There is no automatic fallback. The receipt,
all required reports, original map/DDC/SDC/SVF and source-DC output identities
remain checked; the selected PT receipt and report hashes bind the target plan.
Pass the same explicit directory to every ECO stage. An external directory
cannot substitute another map, package, profile or constraints. Native PT uses
report_host_usage -verbose; DC and its serial function query retain
report_host_options. The runner sets the tool role for each native subprocess.

The current N3 bias hierarchy is /u_core/bias/memory/. Register data-D
candidates must be current violated hold checks, exact members of native
all_registers -data_pins, input pins on sequential library leaves, and pass the
same per-clock/per-transition min/max and clock-association checks. Clock,
async reset/removal and arbitrary combinational pins are excluded from this
family; no CDC or reset exception is introduced.

Experiment budgets default to 1024 added buffers, 8 per endpoint and 5000 raw
characterized area units. Explicit upper limits are 2048 buffers, 16 per endpoint
and 10000 raw area units. Each receipt records the chosen budgets; each actual
insertion remains checked against the count and characterized area ledger.
These are bounded experiment limits, not a timing or contest-area pass.

The optional reset_removal family is excluded from the default family set. Use
--families reset_removal to make a separate plan for the exact current native
removal endpoints; it cannot be mixed into the default hold experiment by
omission. The planner strips only a native (rise)/(fall) coverage annotation
from exact RDN/SDN pins. Before mutation, native all_registers -async_pins
membership, sequential leaf/library identity and the **async_default** min/max
paths must pass. Unknown recovery is retained and cannot become a numeric
setup pass. Current edge-envelope buffer results do not prove reset release
for arbitrary asynchronous phase. Full recovery/removal, pulse-width, coverage
and clock association reports remain mandatory after persistence.

Every PT stage additionally exports mandatory reference-metadata.tsv from the
native library: reference, library_cell and is_sequential for each mapped leaf
reference, including RAMSP1024X16. Classification is queried from the linked
library, with no name heuristic. The file is receipt-bound and, where a function
proof is emitted, its SHA is included in that proof.

Native endpoint path enumeration starts at 64 and retries saturated exact
launch-clock/endpoint-transition queries at 256, 1024, 4096 and 8192. Only
saturated queries expand. All returned native capture-clock/path-group contexts
remain retained; no path-group/capture-clock equivalence is assumed. Saturation
at the explicit --max-paths-per-query limit (default 8192, bounded 64..65536)
remains a failure. endpoint-query-attempts.tsv records every attempt and is bound
as a prior-stage input. A final cap hit additionally exports exact context,
all capped candidate context/slack rows and up to 128 native timing paths.

The clock chain is probe → tree → DC apply → fresh PT reload. The r7 sealed
whole-tree plan has 1560 groups and a predicted root fanout of18. Four unused
hierarchy clock inputs (g0032/g0034/g0052/g0546) are omitted after exact structural
review; every created output must have1..32 actual flattened leaf loads. The
discarded four-load probe establishes native insertion scope only. The complete
tree must reduce actual root capacitance without worsening measured transition.
An empty native attribute never substitutes for zero or a pass.

The electrical chain measures all68 catalogued roots but mutates only51 ordinary
control nets in198 bounded groups. The17 asynchronous reset roots remain visible
and unchanged. Its discarded four-AO32-load probe checks exact local membership,
fanout and clocks and records real capacitance/slew; it does not claim electrical
improvement. Every full-split root must reduce measured capacitance without
worsening transition, followed by full STA/DRC, DC/SVF and a fresh PT reload.

The prune chain requires an explicit completed apply/reload seed and the exact
original-map1796-leaf whitelist (including36 unobservable state leaves). Complete
wave outputs are checked for zero native leaf-input/top-port visibility before
any deletion in that wave. All353 SRAMs remain protected. Optional cleanup
removes only newly dead, native-proven identity XU_ECO_* buffers and records a
separate ledger. Fresh PT permits only the exact deleted state clock endpoints
to disappear; all remaining original clock associations must match.

Unknown setup/recovery on AON first-stage asynchronous receivers remains
unresolved. A fixed-delay experiment under the current clock-edge envelope does
not prove arbitrary-phase CDC/RDC safety and cannot change coverage to Met.
