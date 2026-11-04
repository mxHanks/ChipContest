# Audit112 local handoff and fixture evidence

This archive preserves **local preparation and 16 local checks only**. It contains
no evidence of audit112 running or finishing on the server. `NOT_QUALIFIED` applies
throughout. The copied handoff README and JSON retain their historical
`READY_FOR_ONE_SERVER_RUN_NOT_EXECUTED` wording byte for byte; that wording is not
a statement about the current server process.

The archive contains 47 original files, 12,859,487 uncompressed bytes. Its compressed
size is 533,364 bytes and SHA256 is:

```text
124870b50342e9799704d217581ddbe5bfa357d3fd2ced7d1eda5ef117b8a685
```

`manifest.json` records each original relative path, source path, byte count and
SHA256. The payload includes:

- The delivered audit112 script, launcher, original local-check script, README and
  handoff JSON, without source edits.
- All 33 files under the original `local-check112-v4`, including the result JSON,
  actual-layout byte fixtures, positive replay output and rejected mutant files.
- The frozen extractor93 helper and the original native report samples used to
  generate the local fixtures.
- The complete original source-file driver listing used for exact membership
  checks, the fixed PT57 execution/prepared receipts, and the **older six-task
  RUNNING extractor93 state used only as a rejection fixture**. That last state
  must not be treated as the current extractor93 status.

The local checks cover three actual native attribute layouts, two-pin report and
compact replay, exact before/after type/value comparison, SHA corruption, summary
and phase changes, native-value changes, duplicate pins, invented annotation
source, missing native attributes, an artificial integer-SAIF fixture and its
TX mutant, exact native driver-column membership, and persisted rejection of the
older incomplete snapshot. They do not replay the server's full 24 compact files,
540,288 pin blocks, 19 GB native reports, or actual mapped SAIF bodies.

Run integrity verification from any directory:

```sh
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-native-pin-audit-local112-20261105/check-evidence.py
```

To reproduce all 16 checks using only the archived inputs:

```sh
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-native-pin-audit-local112-20261105/check-evidence.py --replay
```

The checker first verifies the whole compressed file and every original payload
byte. Replay then makes an isolated temporary tree under this evidence directory
and runs the unchanged original check script. The archived sample JSON contains
two absolute local paths; only those two path strings in the **temporary copy**
are relocated to archived sample copies. Original script/input archive bytes stay
unchanged. The temporary tree is removed after replay. The resulting 16 check
names and frozen tool hashes must match the original result. This command was
executed successfully when the archive was created.

The delivered scripts pass Python 3.6 grammar checks. Local runtime replay uses
the available local Python interpreter; it does not prove operation under the
server's Python 3.6 runtime.

The planned server audit independently checks measured-SAIF TX against native PT
attributes. A native `x_probability=0` still does not establish physically known Q
state, the cause of PT's unknown handling, or a qualified energy value. Attribute
getters may trigger lazy engine propagation, so before/after means before/after
the explicit `update_power` command, not synchronized engine snapshots. Saved
driver-column membership and `activity_checker_status` do not supply a complete
annotation-source proof. Timing, physical state and contest scoring remain outside
this local archive's scope.
