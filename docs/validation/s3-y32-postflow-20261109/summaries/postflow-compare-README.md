# Independent postflow saved-evidence verifier

`postflow_compare.py` copies the original production saved-evidence verifier at SHA `61f8a79741a801d389e10b2cc9b3c0bee5eb75726a87dbba3ba0a5a003c7a523`, preserving artifact, source, generated C/TB, ELF/image, simulator, raw log, command, clock, reset, physical clear, tensor, numerical output, time-window and tool checks. The production verifier was not edited.

Extensions are explicit profiles `direct-pe8`, `direct-pe16`, `batch16-pe8`, `batch16-pe16`, `stream32-pe8`, `stream32-pe16`. They pin the physical compute-core SHA and require exact MAC/start/done counts; physical16 also checks both engines independently using the original physical marker. NICE requests/responses/retirements are exactly 3168, 1584 or 99; snapshots/POPs remain 3168 and shared writes remain 25344 per layer. Batch/stream markers are checked both independently and through each campaign's exact rehashed source parser/contract. The old direct baseline retains its original profile.

A complete external baseline source SHA map and exact reviewed before/after pairs are mandatory. The candidate full source map is derived from these pins, and must match before importing the campaign's pinned local parser. Source changes have a fixed whitelist; no deletion or undeclared addition is accepted. Changed numerical model/exporter/vectors/CPU controls/memory configuration are outside the whitelist.

Only the explicitly selected transport schedule, one compiler macro and one runtime selector are normalized. All other saved arguments and conditions must be equal. Only the new transport may change loaded firmware; reviewed changes are confined to `accel.c` and the corresponding fixed contract. Every saved ELF/image mapping is independently verified. Generated physical-clear C must match after only the exact snapshot-main include path is normalized. All phase counters, overlap, waits, clear duration, source gap and full request/final response windows remain visible in the result.

Ready command for the complete selected full12 campaign (only run after its status is development PASS):

```bash
python3.12 -E -B build/postflow-20261108/postflow_compare.py \
 build/writeback-v2-20261108/direct-full12/result.json \
 build/postflow-20261108/selected-full12/result.json \
 --baseline-profile direct-pe8 --candidate-profile stream32-pe8 \
 --baseline-sources build/postflow-20261108/baseline8-full12-sourcepins.json \
 --source-pairs build/postflow-20261108/selected-full12-sourcepairs.json \
 --out build/postflow-20261108/selected-full12-comparison.json
```

Use a new `--out` path when repeating; output creation refuses to overwrite existing results. Source pin files and all campaign evidence should be included when transferring the verifier. Campaign folders may be relocated: saved paths are normalized only for comparison, while artifact hashes are checked under the current folder.

`test_postflow_compare.py` has nine positive/negative checks using real saved campaigns and in-memory damage. It rejects incorrect physical/transport profiles, unpinned or undeclared source changes, unexpected extra macros/selectors, clock/clear changes, generated clear-program changes, duplicate markers and incorrect final response/count markers. It never modifies campaign evidence or starts a simulator.

This verifies local artifact consistency and equal stated conditions. It does not create new simulation evidence, establish independent authenticity, or qualify synthesis, timing, power, SRAM macros or official contest acceptance.
