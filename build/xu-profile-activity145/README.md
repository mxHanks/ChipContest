# xu profile activity145

One CLI compiles the exact candidate firmware plus its CPU clear wrapper,
compiles the full SoC once, and runs all twelve original tasks in twelve fresh
processes. This bundle does not change the baseline, S2c or S2e collectors.
It does not start remote work, synthesize a mapping, or claim qualified power.

```bash
python3 -B /absolute/xu-profile-activity145/check_bundle145.py
python3 -B /absolute/xu-profile-activity145/activity145.py run \
  --profile s2d --source-root /exact/ChipContest-s2d-01 \
  --freeze-receipt /queue138/s2d/freeze.json \
  --adoption-receipt /queue138/s2d/adopt-own-fm.json \
  --vendor-model1024 /private/RAMSP1024X16.v \
  --netlist /exact/repair19/mapped.v --constraints /exact/constraints.sdc \
  --out /new/activity145/s2d
```

The two mixed profiles `s1_sram_bias` and `compact32_128` also require
`--vendor-model128 /private/RAMSP128X16.v`. `--vectors` selects an existing
validated twelve-task fixture; its48 tensor hashes must match the candidate's
original fixture manifest exactly. Both vendor models must match the original138
official model SHA; a valid alternate module or host stub is rejected. Otherwise
the candidate's pinned fixture is extracted into the new output.
`--prepare-only` performs all source, adoption,
fixture and firmware checks and prepares the VCS command without starting VCS.
It returns `PREPARED_NOT_SIMULATED_NOT_QUALIFIED`, which is not completion.

The runner accepts exactly the eight IDs in inventory137. Both source commits,
every tracked main/child byte and executable mode, live RTL file set, original
TB, candidate ABI/firmware contract, common adapter/generator bytes, vendor
models, toolchain, selected ownFM mapped body, SDC and all declared138 inputs
are bound explicitly. It rechecks immutable inputs around compilation and each
task. It independently checks the original ownFM native log and SVF chain;
original and selected repair mapping identities remain separate.

The clear wrapper uses 33697 accepted CPU writes, except H2's 32928 writes and
S2d's 33639 writes. It never reads fixture pointers or preloads accelerator W,
X or bias storage. The existing generator only preloads program ITCM and the
original shared fixture. The observer verifies every accepted clear write in
order and all actual core W/bias commits. Every elaborated SRAM announces its
actual `%m` through a global reference-type bind, with independent 1024/A10 and
128/A7 pin schemas. Actual accelerator SRAM write edges must cover every
logical reachable bit once with zero data and again with fresh task payload.
Unused SRAM padding is not claimed cleared. Bound X probes check every actual
storage write against its real register after NBA; S2d must clear both banks
and upload rows to alternating actual banks.

The measured interval starts at the first valid source REQUEST and stops on
final Y response RETIRE, checked against the retained original numeric/PERF
scoreboard and nominal150 physical timestamps at 1fs precision. The first
source request must remain stable until acceptance. Actual accelerator reset
sampling is checked separately from the external TB reset; later reset/X is
rejected. LF32768 uses absolute phase. FIFO reset establishes empty logical
ownership; unowned FIFO payload bits are not claimed physically reset.

`task_00` through `task_11` each contain `simulation.log`, original
`task.saif`, `task-normalized.saif`, `actual_macro_inventory.json`,
`task-normalization.json`, and `result.json`. Mixed SRAM aliases form a full
bijection with the actual elaboration inventory; normalization preserves all
nonprobe signals and every TX/TZ/TB/extra dwell statistic, and rejects unequal
native NET/PORT duplicates. Full-SoC clock and scope presence are checked;
mapped annotation and power remain separate146 work.

Top-level `result.json` is atomic and updated after every completed task.
Completion is exactly `COLLECTED_12_REVIEW_PENDING_NOT_QUALIFIED`; any failure
records `FAIL_REVIEW_REQUIRED_NOT_QUALIFIED` and preserves its evidence. An
existing output directory is never restarted or overwritten. A compile-only
result or precreated task directories cannot satisfy the terminal status.

```bash
python3 -B /absolute/xu-profile-activity145/activity145.py verify \
  --activity-root /completed/activity145/s2d --profile s2d \
  --receipt /new/verification145-s2d.json
```

Verification rechecks all frozen inputs and task IDs, replays raw logs,
physical clear, actual inventory, SAIF inspection and raw-to-normalized SAIF
into a new scratch directory. It starts no native tool. Python API:
`verify_result(root, expected_profile=None, replay_normalization=True)`.
The individual `checked_log`, `physical_check`, and `inspect_activity` APIs are
also available to146. Duration fields are integer fs ticks plus the explicit
decimal seconds-per-tick string; original acceptance-based inclusive cycles
and formal REQUEST inclusive/elapsed cycles are distinct.

`build_jobs145.py` generates eight direct CLI job registrations for150, plus
`activity-plan145.json`, in a new local directory. Specify deployed bundle,
output, freeze and model paths. When generating locally for the server, use
`--freeze-evidence-root` with the returned149 original receipts and `--freeze-root`
with their server location. All138 original inputs, both returned receipt bytes,
the selected official models and the complete145 bundle are frozen in every job.
The first job depends on successful138 and terminal142 (override `--after-job`);
following jobs depend on terminal prior
activity, preserving failures while allowing the remaining candidates to run.
Each `process_contains` is its unique absolute output path. Generation does
not register or launch jobs. Register only `activity145_*.json`, not the plan.

The final task-input freeze includes the actual VCS executable, native version
log and compiled simulator binary, and verification rejects a missing chain
member. Compiler version/build logs and their hashes remain in the run output.

Host validation: all eight exact source contexts and clear firmware wrappers
compiled; all eight complete full-SoC source sets and global binds passed
Verilator lint with explicit host-only vendor stubs. The real supplied vendor
VCS compile/run remains server work. Thirteen focused host tests cover clear
protocols, all physical geometries, missing/duplicate/nonzero/late writes,
double-buffer bank errors, mixed inventories, lossless SAIF normalization,
fixed tensor/model rejection, complete queue receipts and native compile-chain
freeze omissions. Python3.6 grammar and Git1.8 command compatibility were
reviewed; actual server VCS execution remains unproven.
