# S3-Y32 public PACK32 physical-clear evidence

This portable bundle preserves the fixed READY scalar-clear twelve-layer baseline, the PACK32 pilot, the final single-layer candidate, the final integrated twelve-layer candidate, every helper probe/fault-injection source and log, exact source/firmware/vector identities, independent strict comparisons, and failed diagnostics. Reports and the final native helper receipt state the measured scope and remaining qualifications. Only SRAM mode was used for the selected full-SoC campaign; the optional register-RTL test is explicitly skipped when that generated variant is absent.

Verify bytes, file modes, saved sources, loaded image, simulator, original-layer vectors and raw logs:

```bash
python3.12 -E -B verify_evidence.py --root . --out ../portable-verification.json
python3.12 -E -B revalidate_comparisons.py --out ../portable-comparisons.json
```

Both checks are read-only and launch no simulator or EDA tool. The strict verifier regenerates exact C and TB observers from the selected helper source, checks all 171 candidate sources, and compares the original saved measurements. Archived helper checks use public-MMIO known nonzero prefill and passive deep physical observations; isolated fault mutants are negative tests, not production RTL. FIFO payload physical zero remains UNPROVEN and official clear policy REVIEW_PENDING.

`path-map.json` maps original absolute roots to paths inside this tree. `replay_saved_command.py campaigns/packed-full12/task-00/simulation.log` prints the corresponding relocated saved simulation command and does not execute it. Rerun into a separate output directory. Full source/ELF/image/vector/soc_sim inputs are included, while ordinary object and C++ intermediates, waveforms and Python caches are excluded. Original files were copied with modes preserved; deduplication only hardlinks copies inside this evidence tree and never links originals. `provenance.json`, `sha256.json`, and `failure-log-index.json` distinguish source copies, packaging metadata and raw failure diagnostics. Do not interpret a negative-test FATAL as a production failure or as a PASS by itself.
