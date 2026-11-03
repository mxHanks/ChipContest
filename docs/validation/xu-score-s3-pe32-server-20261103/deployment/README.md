# xu S3 frozen32PE incremental VCS deployment

This package restores a new independent source checkout, requiring the existing frozen server S2c checkout `ChipContest-s2c-02` (main d276b55 / child49a9436). Exact deployment commits and incremental prerequisites are in `source-identity.json`. The added local evidence descendant preserves the measured code d46486c / childfc3977d byte-for-byte.

The launcher verifies package identities, exact commits/gitlink, all tracked source bytes and clean source state; requires SiFive GCC10.2.0-2020.12.8 and VCS Q-2020.03. Both mandatory directed tests compile the new32PE wrapper itself with actual VCS. Then host62 (cached/wide/compat helper backends explicitly VCS), numeric42, vectors12, doctor, new32PE legacy5, synthetic1/2 and wide real12. Two additional full12 controls use old auto firmware on the same physical32PE RTL and default8PE RTL, respectively. Strict result replay binds every layer's complete TASK/PERF/AUTO/PE, source/log hashes, compiler flags, ELF/image and fixture identities. Wide/old-auto32 must share exactly the same VCS executable; default8 must use a distinct physical-variant executable. Actual enabled-lane work is1622016 per task, never discarded hidden arithmetic. Source is verified again after all execution.

Only a successful full sequence yields `VCS_ACCEPTED_NOT_RETAINED`. Mandatory direct actualVCS cannot be replaced by optional Icarus helper skips. All source/output directories must be new; old server sources/logs are not mutated.

```bash
python3 launch.py --source /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/ChipContest-s3-pe32-01 --out /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/s3-pe32-accept-01
```

`--previous-source PATH` overrides the existing S2c prerequisite path; `--prepare-only` restores/verifies without running EDA. The bootstrap helper performs archive SHA/size and safe-member validation, then starts a detached job with durable PID/log/boot records.

Actual local real layer00:8PE old-auto1013171,32PE old-auto1013171,32PE wide957040 (−5.5401309354491985%). This is GCC14.2/Verilator5.032 development screening, not a server prediction. Production Chisel changes are GenerateRTL.scala and new linear/XuParallelCore.scala. The32-lane design has one W array:32×512 logical16bit bank words, each stored in one1024×16 macro with upper address bit0; logical W32KiB, physical64KiB. Whole SoC expected352×1024 macros (fixed320 + W32). This is a source-structure expectation, not a mapped count/area result. Old8PE implementation remains exact with variant off. 64PE generation geometry exists but64PE integration/validation is pending.

Formal clear/first-request activity, mapped consistency, complete150MHz STA, same-library area, fullSoC energy and retention remain separate required stages. No baseline area/energy or SAIF is reused for this candidate.
