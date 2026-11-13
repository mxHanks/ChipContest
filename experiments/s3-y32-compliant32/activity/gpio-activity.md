# Production N2 GPIO activity and digital SAIF

The historical `run_activity.py` and `launch_full12.py` use the N3 test-loader
configuration. Their sealed results remain unchanged and cannot establish
power for the production N2 netlist. The production collector is
`run_gpio_activity.py`, with `gpio_monitor.svh` and `gpio_trace_main.cpp`.

It accepts only a completed `validation-gpio/run_cpu.py` **PASS**, with exactly
the five production definitions (including `SYNTHESIS`, excluding
`XU_SYSBUS_TEST_LOADER`), ingress N2/PW1 and all353 generic SRAM macros. The
existing frozen PPA adapters and every production RTL byte stay identical;
the copied TB gains only one read-only monitor include. Firmware, GPIO
stimulus, original functional checker and file order remain unchanged.

The first task must finish correctly with the same complete-cycle counts as
the no-trace GPIO baseline before its binary may be reused for full12:

```sh
python3 -B experiments/s3-y32-compliant32/activity/run_gpio_activity.py \
  --base /absolute/path/to/completed-production-gpio-task0 \
  --out /absolute/path/to/new-gpio-activity-task0 \
  --vectors /absolute/path/to/sealed-vectors --tasks 1 --jobs 2

python3 -B experiments/s3-y32-compliant32/activity/check_fst.py \
  --run /absolute/path/to/new-gpio-activity-task0 \
  --native-reader /absolute/path/to/fst_inventory \
  --out /absolute/path/to/new-gpio-activity-task0-audit
```

The no-profile path above is deliberately restricted to the historical
N2/353 layout. A new layout, including the374-macro storage candidate,
requires an explicit profile; the new candidate is not assumed selected or
functionally PASS merely because a profile can be described.

`activity_profile.py` seals an independently source-reviewed JSON inventory
containing every macro's complete FST path, its group, exact group counts and
the reviewed source identities. It binds the completed GPIO baseline's
effective production RTL, package identity, definitions and any explicit
storage-overlay receipt. The observed FST must not be used to infer the
expected inventory. All32 ITCM,32 DTCM and256 shared macros are mandatory.
Every other internal instance must be listed, including output/bias buffers.

```sh
python3 -B experiments/s3-y32-compliant32/activity/activity_profile.py \
  --baseline-result /absolute/path/to/final-gpio-task0/result.json \
  --inventory /absolute/path/to/source-reviewed-exact-inventory.json \
  --out /absolute/path/to/new-sealed-profile.json

python3 -B experiments/s3-y32-compliant32/activity/run_gpio_activity.py \
  --base /absolute/path/to/final-gpio-task0 \
  --profile /absolute/path/to/new-sealed-profile.json \
  --out /absolute/path/to/new-final-activity-task0 \
  --vectors /absolute/path/to/sealed-vectors --tasks 1 --jobs 2

python3 -B experiments/s3-y32-compliant32/activity/check_gpio_fst.py \
  --run /absolute/path/to/completed-final-activity-task0 \
  --profile /absolute/path/to/new-sealed-profile.json \
  --native-reader /absolute/path/to/fst_inventory \
  --out /absolute/path/to/new-profiled-native-audit
```

The profiled native audit compares the **complete instance set**, all ten
pin declarations per macro and their native initial values. Missing one
instance, one initial value or shifting the fs window fails. The selected
storage defines must be explicitly present in the sealed storage receipt;
undeclared preprocessing changes and the N3 test loader are rejected.

The FST opens on the HF falling edge before accepted physical clear and
closes on the HF falling edge after the last of25,344 Y-write responses.
The duration must equal the baseline's inclusive clear-to-Y task cycles
times the actual6,666,666 fs HF period. Each window also records the real
first GPIO data-pad presentation and exact fs distance to final Y retirement,
plus the independent TB's GPIO-first-data inclusive cycle count. These two
conventions are explicitly separate: the first GPIO event occurs on a falling
edge and the final response on a rising edge.

The native FST audit requires all353 exact macro instances and all3,530 port
declarations (23,651 bits), including stable initial values and alias handles.
The full12 launcher additionally binds the completed no-trace full12 result
and compares each layer's outputs, clear, source loading, total and DMA cycles:

```sh
python3 -B experiments/s3-y32-compliant32/activity/launch_gpio_full12.py \
  --state-dir /absolute/path/to/new-supervisor \
  --run-out /absolute/path/to/new-full12-activity \
  --audit-out /absolute/path/to/new-full12-native-audit \
  --replay-from /absolute/path/to/completed-gpio-activity-task0 \
  --vectors /absolute/path/to/sealed-vectors \
  --native-reader /absolute/path/to/fst_inventory \
  --baseline-result /absolute/path/to/completed-gpio-full12/result.json \
  --profile /absolute/path/to/new-sealed-profile.json \
  --cpu 24
```

Choose an available CPU from the actual affinity mask; `24` above is only an
example. The independent session records actual supervisor/child PIDs and
does not retry or overwrite results. Confirm a recorded process is live
before reporting a wait, and inspect terminal evidence before launching any
replacement. Compilation is capped at2 local jobs; simulation at1 thread.

## Native streaming FST-to-SAIF

`fst_to_saif.cpp` uses the installed Verilator/GTKWave `fstapi` directly.
It streams value changes without generating a large VCD intermediate.
It selects two structural subtrees independently:

| Source FST subtree | SAIF target subtree |
| --- | --- |
| `TOP.tb_sysbus32_soc.dut` | `xu_soc_sysbus32_ppa_top/u_soc` |
| `TOP.tb_sysbus32_soc.endpoint` | `xu_soc_sysbus32_ppa_top/u_shared` |

This retains the256 shared SRAM macros; a single `strip_path` to `dut` would
lose them. TB/checker/helpers and generic SRAM model internal variables are
excluded. All actual macro interface pins are retained. Generate names are
preserved exactly; any downstream mapped-name folding still requires the
actual synthesized inventory, rather than a guessed equivalence.

```sh
python3 -B experiments/s3-y32-compliant32/activity/convert_fst.py build \
  --out /absolute/path/to/new-native-exporter

python3 -B experiments/s3-y32-compliant32/activity/convert_fst.py probe \
  --native-exporter /absolute/path/to/new-native-exporter/fst_to_saif \
  --out /absolute/path/to/new-semantics-probe

python3 -B experiments/s3-y32-compliant32/activity/convert_fst.py convert \
  --run /absolute/path/to/completed-production-gpio-activity \
  --audit /absolute/path/to/completed-same-run-native-audit \
  --probe-result /absolute/path/to/completed-semantics-probe/result.json \
  --profile /absolute/path/to/same-new-sealed-profile.json \
  --layer 0 --native-exporter /absolute/path/to/probed/fst_to_saif \
  --out /absolute/path/to/new-layer0-saif
```

The build is sequential. The actual small probe creates a VCD fixture,
converts it with native `vcd2fst`, and reads the resulting SAIF with an
independent existing parser. Hand-specified expected values check aliases,
both retained subtrees, excluded TB/model signals, vector bit order, stable
initialization, X/Z dwell, end-exclusive transitions and full original fs
duration. A second fixture with1ps timescale must be rejected.

The transition convention counts only known0-to-1 or1-to-0 changes after
the initial full frame and before the final timestamp. Initialization does
not invent toggles; transitions through X/Z do not increment TC, while TX/TZ
remain explicit. This convention is recorded and must be compared with the
actual downstream power tool; it is not asserted to equal native
`vcd2saif` unknown-transition semantics.

Every selected digital handle must have a full initial value. Aliases share
one accumulator, then each declared mapped path receives the same per-bit
statistics; they are never summed into one signal. Path collisions and
alias-width inconsistencies fail. Each bit'sT0+T1+TX+TZ must equal the exact
original task duration. The conversion receipt binds source FST, exporter,
native353-port audit, SAIF and per-macro pin statistics by SHA256.

These outputs are **digital RTL activity**, not measured power. Final mapped
annotation coverage, unknown/default activity treatment, legitimate timing,
the SRAM library's actual read/write/idle/leakage power model and whole-SoC
energy are separate gates. SAIF also drops temporal correlations; the original
FST must be retained for conditional SRAM-operation review.
