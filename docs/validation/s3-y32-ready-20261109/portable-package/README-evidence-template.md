# Portable ready-drain evidence

This archive preserves the selected stream32 baseline, the original failed unfenced ready attempt, corrected ready experiment(s), and any selected full12 integration. A failed campaign remains **NOTPASS**, regardless of byte-verification success or later repaired runs. `campaign-inventory.json` contains original statuses; `failure-log-index.json` preserves diagnostics including expected negative unit tests.

`campaigns/` contains each recorded source snapshot, plan/result/clear recipe, generated clear program/TB, ELF, Verilog ITCM image, native `soc_sim`, input vectors, raw commands/build/version/disassembly/simulation logs. Object/C++ intermediates, waveforms and unpinned Python caches are excluded. Task directories and vectors use **original_layer**, even though each fresh simulator process reports native layer0.

`proofs/rtl-checks` preserves ready and legacy unit/real-MAC/error/reset tests, source pins and raw RTL patch. `proofs/checks` preserves firmware/parser checks. `summaries/` contains the separate strict verifier, exact selected-baseline source map, reviewed source pairs, comparisons and review receipts. `reports/` contains the frozen final report. Original bytes and permissions are preserved in `provenance.json`; `sha256.json` verifies copied and generated contents.

From a new extracted path, run:

```bash
python3.12 -E -B verify_evidence.py --out /new/external/path/byte-verification.json
python3.12 -E -B revalidate_comparisons.py --out /new/external/path/strict-comparison-verification.json
python3.12 -E -B replay_saved_command.py campaigns/ready-fenced-task0/task-00/simulation.log
```

The last helper prints a relocated command only. Preserve archived evidence read-only and run any new simulations from a separate output directory. `path-map.json` maps saved absolute artifacts to extracted copies; toolchain paths still require compatible installed tools.

Archive verification confirms frozen bytes and receipts. Strict comparisons independently check source changes, firmware ELF/image bytes, task vectors, exact work, physical clear, clock/reset conditions and measured windows. These remain development simulations, with no synthesis, mapped area/timing/power, gate-level or official contest qualification.
