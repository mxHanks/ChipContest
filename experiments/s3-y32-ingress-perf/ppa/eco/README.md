# Original1064 N3 map-bound timing diagnosis

These tools accept only the new sysbus32-x-sram-353-dev-n3 profile:353 macros,
33 internal, TEST_LOADER enabled, exact source and original1064 developer result.
They require this package own clean DC/SVF and same-map PT receipts. The original
CPU289/physical353 modeling difference remains explicit; no production SDK claim
is introduced. No old353 or final374 map/pin identity is inherited.

All current coverage kinds and every native violation must reconcile, including
new sysbus_load port names. Current native SRAM-D or gating-enable endpoints may
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
