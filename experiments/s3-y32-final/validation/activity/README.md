# Final374 production activity tools — prepared, not yet qualified

`run_campaign.py` waits for the existing final functional task0 PASS, replays
that exact binary for full12 and two wait31 cases, then builds a single tracing
binary from the same159 production RTL sources, six defines and firmware.
All activity changes are read-only TB instrumentation and the C++ event driver.
Only one trace object is active at a time: task0 clear-through-lastY and actual
first-GPIO-data-through-lastY windows are captured by serial identical-binary
runs. This avoids shared generated Verilator trace cleanup flags consuming
another concurrently active trace object's changes.

`inventory_from_xml.py` derives all374 exact physical leaf paths from the
independent final production PPA XML and binds its package SHA. The native FST
reader audits all ten macro pin classes and initial values, plus both CPU RAM
interfaces. SAIF preserves DUT and shared endpoint scopes as `u_soc` and
`u_shared`, retains aliases and unknown dwell, and omits only TB/helper and
macro-model internal variables. Digital parser binaries may be reused only
with exact binary/source and semantic-probe receipts; old FSTs are never used.

The campaign builds and simulates on one CPU, never retries, and records each
owned PID, stage and command. Functional full12 completes before activity starts.
If a conservative disk projection fits the reserve, it also captures and audits
activity full12 with the same trace binary and checks its complete layer/cycle
evidence against the no-trace full12. Task0 gets both separately bounded SAIFs.

Current owned campaign command is recorded in
`build/s3-y32-final/validation/activity/campaign-r3-launch.json`; its stage is in
`campaign-r3/state.json`. Do not restart or reuse that output directory. These
tools are prepared; no final activity PASS exists at this snapshot. FST/SAIF
captures remain RTL activity, not mapped power. Verilator's two-state backend
cannot prove silicon unknown coverage; vendor macro power arcs, mapped
annotation, achieved timing and energy remain separate required measurements.
