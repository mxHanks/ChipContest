# xu local full-SoC SAIF power probe

`tools/scripts/xu_soc_saif_power.py` prepares and runs independent averaged PrimeTime power probes from `tools/ppa/xu_soc_task_activity.py` output. The default is real global task 0. A subset always has a `PARTIAL_*` status, even when its collector contains twelve tasks. A twelve-task run requires an actually completed twelve-task collector. Every successful execution remains `REVIEW_PENDING` and `NOT_QUALIFIED`; this tool calculates no task energy, average power across tasks, contest score, or pass.

The runner executes locally. It does not connect to a remote host, fetch credentials, launch VCS or synthesis, alter private libraries/models, or replace missing SRAM activity with zero. Supply the collected activity and mapped target produced by the existing flow. Vendor models, DB libraries and proprietary tool manuals stay at their private paths and should not be committed.

## Prepare an isolated task-0 probe

The collector must have run with both `--clear-task-before-window` and `--sram-pin-alias`. Its completed `result.json` must describe the formal first valid source-request to final retired Y-response window, the preceding drained 33,697-write physical clear, and a fresh process with fixture-matched W/bias/X uploads. The normalized SAIF must contain all 336 RAMSP1024X16 macros and 22,512 measured signal-pin bits. Raw SAIF remains immutable, and normalization is recomputed during preparation to verify its complete bijection and preserved unknown dwell.

```bash
python3 tools/scripts/xu_soc_saif_power.py prepare \
  --activity /private/collector/result.json \
  --implementation /private/implementation/implementation.json \
  --netlist /private/ppa/mapped.v \
  --constraints /private/ppa/constraints.sdc \
  --out /private/saif-power-task0 \
  --task-ids 0
```

Use `--ppa-prepared /private/ppa/prepared.json` instead of `--implementation` to validate a prepared PPA bundle and its generated controls and copied RTL as well. `--constraints` means the exact analysis SDC supplied to the collector and sourced by PT; it is distinct from DC's generated `mapped.sdc`. Its hash must also match the implementation's reviewed constraints. A direct implementation uses the repository containing this runner by default; `--root` selects its actual platform repository. A PPA prepared manifest supplies its own platform root.

The implementation is checked through the existing `xu_soc_ppa.checked_implementation(..., allow_unqualified=True)` and actual library-role checks. Development probes may retain incomplete mapping, netlist-equivalence or PVT qualification evidence; those gaps are recorded. Existing source-profile, RAM geometry, clock-review and source-hash guards still apply. A source profile with additional SRAMs, such as the 24-macro bias SRAM variant, cannot consume the baseline collector's 336-macro pin coverage and is rejected. It needs a matching collector/normalizer before power probing.

Preparation rejects an existing output directory. It records nested collector/implementation file identities, absolute source-hash maps, task vectors and their materializations, raw logs, raw and normalized SAIF, normalization mappings/observer/helper, mapped netlist, exact analysis SDC, actual role-labelled standard-cell/SRAM DB files, and runner/helper code. It checks collector source bytes against the implementation's original RTL, exact replacements and added top/shared-memory sources.

## Execute locally in PrimeTime

```bash
python3 tools/scripts/xu_soc_saif_power.py run \
  --out /private/saif-power-task0 \
  --pt pt_shell \
  --timeout 21600
```

`--pt` can name a PT executable or absolute executable path. Each task gets a fresh `pt_shell -f power.tcl` process with closed stdin, a separate working directory and log. The timeout applies independently to each process; a timeout kills its process group and records failure. No shell interpolation is used to execute PT. A run refuses existing execution receipts, reports or logs; failed runs need a freshly prepared output.

Each generated Tcl script enables averaged power analysis, links the supplied mapped netlist against the implementation's actual DB list, and sources the exact analysis SDC under its existing conservative clock envelope. It checks the primary clocks and generated clock contract and reuses `ppa.memory_checks` for all actual SRAM groups and retained CPU/accelerator/interconnect hierarchy. It checks that every SRAM name is represented in normalized activity, accepting equivalent slash/dot generate-scope spelling.

The activity command is `read_saif` with `-strip_path tb_xu_soc_ppa/dut` and `-report_inconsistent_annotation`. The options were checked against the locally retained PrimeTime T-2022.03-SP5-1 command manuals. `read_saif` is not given a VCD time window or an unsupported `-rtl` option: each SAIF already contains exactly one measured task duration. Tool reports and supplied simulation records must establish actual annotation coverage; source presence alone cannot establish it.

## Evidence and remaining review

`prepared.json` stores exact input hashes, implementation qualification gaps, selected task IDs, per-task unique completion markers, expected reports, Tcl hashes and measured SRAM-pin-state artifacts. Every `task_XX` includes:

- `power.tcl`, `pt.log`, and `tool-version.rpt` with actual command/executable/version evidence.
- `read-saif.rpt`, `inconsistent.rpt`, units, clocks and timing-check diagnostics. An empty inconsistency report is permitted because the documented no-conflict result is empty; a missing report fails.
- Before/after switching summaries and hierarchy coverage, unannotated nets/pins, and explicit file/default/propagated/no-switching-activity lists.
- `measured-sram-pins.json`, retaining every measured pin's T0/T1/TX/TZ/TB/TC statistics. Disabled DTCM unknown Q dwell remains present.
- Before/after PT attributes for every signal pin of every SRAM, and a power report for every individual SRAM, with exact inventory markers checked after execution.
- Full-SoC and hierarchy power reports plus actual linked SRAM-library-cell attributes and general loaded-library reports.

`execution.json` preserves commands, return codes, logs/reports/artifact hashes, the executable identity and input hashes before/after execution. A nonzero exit, PT error diagnostic, absent/duplicate completion marker, changed input, missing/empty required report, missing/extra/duplicate SRAM power cell, or missing/extra/duplicate pin report fails execution. Tcl catches errors and exits nonzero; a unique completion marker appears only after all commands and report existence checks.

These are host orchestration and evidence guards. The generated PT script still needs execution with the installed target PT version and private real libraries. Attribute/library report support and the 67-signal-pin SRAM interface are checked by that execution; a tool/interface mismatch fails instead of silently omitting evidence. Host tests neither simulate a successful PT run nor label generated Tcl as measured power.

A reviewer must inspect mapped annotation against simulation, unresolved/black-box models, file versus propagated/default activity, inconsistent native annotations, all unknown pin dwell, units and operating conditions, SRAM clock/enable/write/retention modes, and the actual Liberty `when` expressions and `internal_power` tables for every operating mode. Linked library attributes and generic library reports are evidence to guide that review; they are not an automatic Liberty mode audit. Preserve the original libraries and obtain an authorized detailed Liberty/internal-power report when these reports do not expose the needed tables. No zero-power inference is allowed for unknown, disabled, unannotated or unmodelled SRAMs. Coverage review and macro-library review must finish separately before a downstream energy calculation or qualification can be considered.

Run host guard tests with:

```bash
python3 -m unittest discover -s tests/host -p test_xu_soc_saif_power.py -v
```
