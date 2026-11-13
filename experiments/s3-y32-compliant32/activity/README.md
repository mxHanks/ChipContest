# Full-SoC RTL activity capture, isolated from functional runners

Current final direction is the production N2 GPIO/CPU-loading configuration;
see [gpio-activity.md](gpio-activity.md) for the new production collector,
explicit source-reviewed macro profile and native streaming SAIF exporter,
and [gpio-adaptation-plan.md](gpio-adaptation-plan.md) for the earlier seam plan.
The collector supports a newly sealed storage layout through exact instance
paths and source/define binding; a numeric macro-count override is not enough.
No new activity simulation is started until the final functional candidate is
selected. The remaining examples below describe the historical N3 tools.
The N3 test-loader
full12 activity attempt was stopped as superseded before completion. Its
existing 353-macro task0 remains functional/port evidence, with the N3/N2
configuration difference explicitly retained below.

This directory copies a sealed PASS `cpu-xmacro-task0-r1` source and firmware.
Only the copied TB gains an include containing read-only observation signals.
No original CPU/RTL/runner file is changed. This produces **RTL activity**;
it does not establish mapped coverage, SRAM power, achieved frequency, or
contest power/energy qualification.

```sh
python3 -u -B experiments/s3-y32-compliant32/activity/run_activity.py \
  --out build/compliant32-20261113/activity-task0-NEW \
  --vectors build/compliant32-20261113/numeric/public-validation-600-evaluation-r1/vectors \
  --tasks 1 --jobs 2

# Full12 reuses the exact completed task0 simulator, ELF and observed source.
# This does not compile a replacement binary.
python3 -u -B experiments/s3-y32-compliant32/activity/run_activity.py \
  --out build/compliant32-20261113/activity-full12-NEW \
  --vectors build/compliant32-20261113/numeric/public-validation-600-evaluation-r1/vectors \
  --tasks 12 --jobs 2 \
  --replay-from build/compliant32-20261113/activity-task0-r1
```

`--out` must be new. `--prepare-only` copies and seals inputs without compiling
or simulating. `--build-only` also compiles but does not simulate. Compilation
uses at most two jobs; the simulator and trace writer use one thread and the
simulator is pinned to one available CPU. FST files are bounded by a 12 GiB
default guard and a 512 MiB free-space reserve. Keep the complete run, including
generated simulator objects, below the task's 15 GB total disk budget.

The default source remains the already validated macro-X CPU source, not a
new RTL selection. Current source/model/ELF/vector/driver/TB-diff identities
are saved in `result.json` and `source-manifest.json`; the copied checker is
used unchanged for all original SoC functional and transaction checks.

## Exact capture window

The custom C++ main uses `eval()`, `eventsPending()` and `nextTimeSlot()` to
visit every scheduled simulation event. The context time precision is checked
to be 1 fs. Each task has an independently registered `VerilatedFstC` object;
all registrations happen before the first `eval()`, and each file is opened
only at its task boundary.

`monitor.svh` does not drive the DUT, endpoint, loader or firmware. It exposes
the HF clock, task identity, upcoming clear command, accepted clear timestamp,
and independently counted final Y response timestamp using
`/* verilator public_flat_rd */`.

For a counted task, C++ opens and takes a full initial snapshot at the HF
falling edge immediately before clear request acceptance. It dumps after each
evaluation until the HF falling edge immediately after the 25,344th Y write
response retires. Thus the trace includes clear, complete source loading,
CPU scheduling/waits/gaps and computation, including the last retirement.
Warmup, output poisoning and public readback lie outside each file.

The following must all hold, otherwise the run fails:

* `clear_fs - first_trace_fs == 3,333,333`;
* `last_trace_fs - last_Y_response_fs == 3,333,333`;
* trace duration equals original TB inclusive task cycles × 6,666,666 fs;
* original checker and independent activity timestamps agree exactly;
* first-task cycles equal the sealed non-tracing baseline.

The monitor arms on a valid clear command. If that command is stalled across
additional HF edges, the exact-boundary assertion rejects the trace. It never
silently includes extra pre-task cycles or fabricates an earlier snapshot.
This initial normal-path collector does not yet implement a rolling pre-edge
snapshot for arbitrary clear-command backpressure.

## Hierarchy and SRAM scope

Compilation uses `--trace-fst --trace-threads 1 --trace-underscore`, without
`--trace-depth`, and permits signal widths up to 65,536 bits. The API's
registration depth argument is the locally documented `99`; actual waveform
declarations must independently prove that every required hierarchy and pin
exists. Default `--trace-max-array=32` omits large memory/reference arrays.
Omitted macro storage arrays do not excuse missing macro port declarations.

The frozen CPU functional model physically instantiates **289** generic
`RAMSP1024X16` models: 256 shared plus 33 internal (X16/W16/bias1). Its ITCM
and DTCM remain the original two behavioral `sirv_sim_ram` models. Their
logical `clk/cs/we/wem/addr/din/dout` interfaces are traced. They correspond to
64 CPU macros only in the PPA adapter; this collector does **not** pretend to
have captured those 64 physical macro ports. The intended PPA total remains
353 macros.

An isolated second profile can close this **activity** gap by using the exact
sealed PPA CPU adapter, rather than inferring waveforms offline:

```sh
python3 -u -B experiments/s3-y32-compliant32/activity/run_activity.py \
  --out build/compliant32-20261113/activity-cpu353-task0-NEW \
  --vectors build/compliant32-20261113/numeric/public-validation-600-evaluation-r1/vectors \
  --tasks 1 --jobs 1 \
  --cpu-macro-package build/compliant32-20261113/ppa-native-r2
```

This profile copies the frozen selected CPU source and replaces only
`rtl/general/sirv_sim_ram.v` with its sealed PPA adapter. The copied TB's
original 64 KiB ITCM boot initialization is replaced by
`boot_cpu_macros.svh`, which writes **only boot firmware** into the 32 actual
generic ITCM macros, using the functional model's physical interleaving.
No tensor, parameter or output is initialized through hierarchy. The other
32 CPU macros are the actual DTCM instances. All original firmware bytes,
tensor loader, shared path, timing boundaries and functional checks remain.
Use a distinct output directory; the older 289-macro evidence stays intact.

Before the CPU experiment, `check_cpu_adapter.py` replays the existing
four-state adapter-vs-original suites with the exact sealed adapter and
generic model. The suites include all-address 32/64-bit cases, real platform
geometries, random byte masks, same-address writes while retaining the read,
disabled writes and bank changes. This does not use or claim a vendor model.

Only after task0 is correct with unchanged cycles should full12 reuse its
exact compiled simulator via `--replay-from`. The native inventory then
requires all **353 actual macros**, all **3,530 macro ports**, plus both CPU
logical interfaces. This remains generic RTL activity: mapped annotation,
vendor model eligibility, SRAM characterization and actual power remain
separate required work.

There is also a **preprocessor configuration difference** from the current
production PPA package. These CPU tests define `XU_SYSBUS_TEST_LOADER`, so
the ingress arbiter has three masters and a two-bit owner (`N=3`, `PW=2`).
The production package omits that define and has two masters with a one-bit
owner (`N=2`, `PW=1`). Common RTL bytes can match while the elaborated
hardware differs. Capturing all 353 physical generic macros therefore does
not establish production PPA activity or power for the current package.
This must be closed explicitly before claiming the same frozen hardware
configuration for throughput, area and energy.

For the long final 353-macro run, `launch_full12.py` starts one independent
local session, seals the relevant tool and baseline identities and records
the supervisor PID, each actual child PID, exit codes and final state. It
does not automatically retry or overwrite a run. After simulation it performs
the native FST audit and compares every layer's counted cycles, output count,
firmware identity and vector bytes with the completed no-trace full12 result:

```sh
python3 -B experiments/s3-y32-compliant32/activity/launch_full12.py \
  --state-dir build/compliant32-20261113/activity-cpu353-full12-supervisor-NEW \
  --run-out build/compliant32-20261113/activity-cpu353-full12-NEW \
  --audit-out build/compliant32-20261113/activity-cpu353-full12-native-audit-NEW \
  --replay-from build/compliant32-20261113/activity-cpu353-task0-NEW \
  --vectors build/compliant32-20261113/numeric/public-validation-600-evaluation-r1/vectors \
  --native-reader /absolute/path/to/fst_inventory \
  --baseline-result build/compliant32-20261113/cpu-public-audio-full12-r1/result.json \
  --cpu 1
```

Poll the **recorded live process**, then inspect `state.json`; a state file
alone does not establish that the process is still running. A closed tool
handle is not a terminal result. The prior attached 289-macro full12 attempt
returned exit143 with its runner and simulator both absent; its separate
`unexpected-termination.json` preserves the incomplete status. Its two
finished layers cannot be called full12 evidence. The unexplained SIGTERM
source has not been established; changing launch method does not prove the
cause of that earlier interruption.

Independently check the FST files using the native inventory helper after
building it as described by `check_fst.py --help`. Required actual macro pins
are `CLK/CEN/GWEN/WEN/A/D/Q/EMA/EMAW/RET1N`, including initial values, even for
signals with no transitions. A separate receipt binds FST bytes, native time
range, hierarchy declarations and window manifests. It does not edit the
functional run result or claim mapped activity coverage.

`fst_inventory.cpp` uses the installed native FST reader to enumerate the
complete hierarchy and decode the required pins' first frame, including
stable constants. `check_fst.py` verifies all exact X/W/bias/shared instance
names, each pin width and initial value, the two CPU logical RAM interfaces,
the FST bytes and the native first/last timestamps against the independently
counted task. Build commands are included in `check_fst.py --help`; then run:

```sh
python3 -B experiments/s3-y32-compliant32/activity/check_fst.py \
  --run build/compliant32-20261113/activity-full12-NEW \
  --native-reader /absolute/path/to/fst_inventory \
  --out build/compliant32-20261113/activity-full12-native-audit-NEW
```

All 2,890 required macro port declarations and 14 CPU logical RAM port
declarations must carry initial values. Alias handles are checked once by
the native reader and then checked separately for every declared port by
Python; fewer unique handles do not indicate missing port activity.

The complete SoC and external shared endpoint are captured. TB/checker signals
also appear; they must not be charged as mapped hardware power. A future PPA
step must explicitly map source scopes to the final netlist, check coverage
and handle the CPU macro adapter, rather than guessing zero activity for
unmapped logic or SRAM. `fst2vcd` is available for a future VCD conversion;
conversion must preserve the declared per-task window and exact fs duration.

## Local primary documentation

The implementation relies on the installed Verilator 5.032 sources and docs:

* `/usr/share/doc/verilator/html/connecting.html`, event scheduling and public
  flattened read access;
* `/usr/share/doc/verilator/html/faq.html`, FST/C++ trace registration;
* `/usr/share/doc/verilator/html/exe_verilator.html`, full default hierarchy,
  max array/width and trace-thread options;
* `/usr/share/doc/verilator/html/languages.html:508`, `$dumpvars` module/level
  arguments ignored; `$dumpon/$dumpoff/$dumpall/$dumplimit` ignored;
* `/usr/share/verilator/include/verilated_fst_c.h:210`, dump immediately after
  evaluation;
* `/usr/share/verilator/include/verilated.h:561`, context time uses precision;
* `/usr/share/verilator/include/gtkwave/fstapi.h`, native FST reader metadata.

There are no SV `$dumpfile/$dumpvars` calls in the copied TB. All runtime
gating is explicit C++ file opening, dumping and closing; it does not depend
on the ignored SV dump-control commands.
