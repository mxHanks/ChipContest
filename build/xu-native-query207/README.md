# xu207 native query compatibility replay

`query207.py` is one foreground worker for the original153 controller. It runs
three isolated PT sessions sequentially, retaining each ordinary case failure
and continuing to the next case. A native timeout stops the later cases because
launcher termination does not prove that every native descendant exited:

1. `s2c_original177`: own9c16 map, original177/57 all-clock propagated method.
2. `s2c_common190`: same9c16 and404c7d SDC; exact clock method from actual190
   inventory and task0 power script, both checked equal. This sources45037c scope.
3. `s2e_final155186`: own3440182e map and original186/155 clock method, also
   bound to404c7d SDC contents and45037c scope. Its original method text is
   preserved;190's additional clock-period guards are not falsely described as
   byte-identical to155's method.

No original177/186 source is changed. Their full executable runtime manifests
remain frozen under `frozen177/` and `frozen186/`. The 5 `frozen190/` files are
exact original191 payload bytes (archive SHA256
`44770417f09a4244cbeea5690b4f21923e5d641de365094010ca7eeaf7c998b3`).
Their corresponding server files are rehashed before/after the common case.
The actual failures and unchanged guard replays are in sibling
`build/xu-native-query-failure206/` (commit951b866).

Only these compatibility changes are derived with exact occurrence guards:

* Unsupported `get_clocks -of_objects` becomes `xu207_pin_clocks`. It reads
  the native `clocks` attribute **one pin/port at a time**, checks collection and
  clock object classes/names against enumerated `all_clocks`, and unions native
  handles. `pin-clocks207.tsv` preserves every pin/clock identity, empty attribute
  and native diagnostic. Errors fail; absence never becomes0 or a waiver.
* The186 design-pin→library-pin lookup uses native owner→libcell and enumerated
  libcell pins with exact string equality. These two APIs already executed in
  actual130/132 and177. It preserves all9257 metadata targets and writes exact
  native mappings to `pin-lib207.tsv`; pin rows must match original186 metadata.
* Mutually exclusive annotated/not-annotated switches become separate reports.

The original native completion/required-report guards remain in use unchanged.
The186 original 9257-object and 9219-pulse metadata checks remain mandatory.
Optional gaps remain visible. No-path reports and real timing violations are
not converted to passes. Original177 model metadata records10ps/1ps and1.0
setuphold/width tokens; this does not prove correspondence to the SS DB or a
same-corner SDF simulation. No model/TB/RTL/SDC modification is made.

The fixed job is `native_query207`, output
`B/native-query-replay-20261105-207`, depending on final191 terminal. It consumes
one native slot; it does not register or launch another controller. No retry or
resume is offered. The root state is successful only if all three required
queries execute; even then its status is
`EXECUTED_THREE_CASE_QUERY207_NOT_QUALIFIED`. Any case failure gives
`FAIL_QUERY207_NOT_QUALIFIED` after retaining subsequent case results.
`output-manifest207.json` hashes every output file and records actual totals.

Local validation:

```sh
python3 -B build/xu-native-query207/query207.py --describe
python3 -B -m unittest discover -s build/xu-native-query207 -p test207.py
python3 -B build/xu-native-query207/job207.py
```

Server invocation (only through the original153 registered job):

```sh
python3 -B -u "$HOME/Desktop/xu-native-query207/query207.py" \
  --out "$HOME/Desktop/xu-score-optimization-20261102/native-query-replay-20261105-207"
```

`manifest207.json` freezes23 runtime files. Eleven local tests cover actual method
bindings, unsupported command elimination, original required guards, wrong
map/method rejection, fresh-root rejection, absent-clock integrity, Tcl syntax,
ordinary-failure continuation and timeout stopping. They are host checks, not EDA
or qualification results. Independent review210 separately tests the Tcl helper.
