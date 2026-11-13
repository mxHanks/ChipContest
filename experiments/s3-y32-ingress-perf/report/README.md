# Original 1064 candidate report data

`audit_report_data.py` only reads local frozen source/evidence and exports report tables. It starts neither simulation nor EDA and does not edit RTL, constraints, PPA inputs, or the submodule pointer.

From the repository root:

```sh
python3 experiments/s3-y32-ingress-perf/report/audit_report_data.py \
  --ppa-root build/ingress-perf-20261113/ppa-dev-n3-r2
```

Default output is `docs/validation/s3-y32-ingress-perf-report-20261113/`. `--output` can select another directory. The optional `--ppa-root` verifies all 159 sealed compile input hashes and binds four original candidate RTL files to child `5470c5650f2d11d16e7c52cc96626d21030a3973`; it imports no PPA verdict. The original N3 source package is owned by the PPA workflow.

The default optional generated Verilator scope source is `build/ingress-perf-20261113/cpu-task0-r2/simulator/Vtb_sysbus32_soc__Syms.cpp`. `--functional-symbols` can explicitly select it. If absent, the export says `SOURCE_CONFIGURATION_ONLY` rather than claiming to have counted a generated hierarchy. The portable CSV already records the 289 local functional model scopes counted for this audit.

The audit parses every principal layer directly from raw logs, cross-checks recorded JSON, recomputes inclusive timing windows and disjoint phases, and verifies DMA/loader/endpoint response counts and physical clear records. Warmup is excluded. It independently checks all 168 production source files against frozen baseline `bde23ba`, permits only the original ingress/DMA changes, and compares captured CPU source hashes against current child bytes.

Report consumers should use `audit-summary.json`, `per-layer-cycles.csv`, `run-aggregate.csv`, and `phase-plot-data.csv` for cycle numbers. `storage-inventory.json/.csv`, `macro-geometry.csv`, and `area-expected-accounting.json` retain the unremediated register storage and distinguish 289 functional model macros from 353 expected PPA macros. `evidence-index.json` records source artifact hashes; each per-layer row includes exact raw log line numbers.

This export proves a local data/source audit. It does not establish GPIO production loading performance, achieved clock frequency, gate-level equivalence, public600 NRMSE identity, physical area, energy, or storage-rule compliance. Use only newly returned same-N3-source DC/PT results for the synthesis report. The merged374 candidate, an old353 timing run, and S2 formal proofs are separate evidence and are excluded.
