# xu release161: repair the firmware input path

This is a new, independent bundle. It does not edit or restart release145 and
does not alter RTL, firmware source, vectors, clocks, task windows, SRAM models,
clear recipes, or the existing 4,000,000-cycle limit. All outputs remain
`NOT_QUALIFIED`. No server/native run is claimed by this bundle.

The returned server159 originals prove the immediate145 failure: the native TB
appends `.verilog` to `TESTCASE`, while145 supplied an already suffixed path.
VCS could not open `accel_soc.verilog.verilog`, accelerator reset completed,
and no firmware clear or source request occurred before the cycle timeout.
The original S2b generated TB and native task00 log are retained unchanged in
`fixtures/`. Their source is the independently verified server159 export;
the log SHA256 is
`572ef7596d46a6cc34507cbea7e28d1a287af2bfb4a7f89ec050f165b68c213d`.

Only `activity145.py` differs from the copied release154/activity145 payload:

- Build/run checks bind `TESTCASE + ".verilog"` to the actual compiled image
  identity and pass the ELF prefix to the original TB. Each task continues
  to use the same frozen native simulator binary and firmware image.
- A read-only `$fopen`/`$fclose` guard immediately before the unchanged
  `$readmemh` fails when the firmware file is absent. This new harness assertion
  only diagnoses file existence and never assigns a DUT signal or storage bit.
- Verification rejects the native missing-file diagnostics and rechecks the
  exact task command. It retains the complete145 raw-log/SAIF/physical checks.
- New runs and verification accept only `baseline_h1_h2`, `s1_h2_only`,
  `s1_sram_bias`, `s2b`, `s2d`, `compact32_128`. `pe32` and `pe64` are excluded.

`activity161.py` is the new CLI. The file `activity145.py`, function
`verify_result`,145 result/task schemas, and the filename
`bundle-manifest145.json` deliberately retain the existing power146 interface.
That manifest explicitly identifies `release=xu-activity-repair161` and freezes
all new payloads. `parent145-manifest.json` is the exact original154 manifest
(SHA256 `001c66b2e19cc6ec279e3ae3f24c859b0931ec2b5b850040f9207e7e97941358`).
`check_bundle161.py` checks every original payload remains byte-identical except
the single declared modified file. The copied original `README.md` describes
the145 parent; use this file for161 changes and commands.

Local verification (Python3.6 compatible runtime, standard library only):

```sh
cd /absolute/xu-activity-repair161
python3 -B check_bundle161.py
python3 -B -m unittest test_repair161 test_activity145 test_macro145
python3 -B activity161.py run --help
```

Run161 with the same required145 source/freeze/adoption/vendor/model/netlist/SDC
arguments and a fresh161 output directory; do not reuse145 output paths. The
new activity registration IDs should be `activity161_<profile>` and the later
power campaign IDs `power162_<profile>`, with each power job depending on its
own activity161 success. Existing failed145 registrations/outputs are retained.

For power, the unchanged146 worker can use:

```sh
python3 -B /absolute/power146/power146.py campaign \
  --profile baseline_h1_h2 --source-root /exact/frozen/source \
  --freeze-receipt /exact/freeze138/baseline_h1_h2/freeze.json \
  --adoption-receipt /exact/freeze138/baseline_h1_h2/adopt-own-fm.json \
  --activity-root /fresh/activity161/baseline_h1_h2 \
  --activity-tools /absolute/xu-activity-repair161 \
  --out /fresh/power162/baseline_h1_h2
```

The six profiles are not all expected to pass merely because the program
path is fixed. Native complete task checks must establish each later result.
This patch does not change unknown SRAM activity or150MHz qualification status.
