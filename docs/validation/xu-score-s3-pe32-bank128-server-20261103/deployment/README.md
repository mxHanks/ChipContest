# xu compact128 W32 server handoff

Incremental prerequisites: original32 main94ce6f0 and childfc3977d objects, present in a clean original32 checkout.
No credential or vendor model body is included. All tracked source bytes/modes/link targets are frozen.
The launch requires a new source and output directory, actual regular RAMSP128X16.v, same SiFive GCC10.2/VCS2020.03.
It first runs mandatory VCS generated/designated single-bank and wide/compat checks, then eight-step development
acceptance and two full12 controls: original32 same wide and compact128 old auto. Actual model SHA is frozen before/after.
WholeSoC development cycles still use generated memories; do not label them a wholeSoC macro or timing qualification.

```bash
python3 launch.py --previous-source /absolute/ChipContest-s3-pe32-01 \
  --source /absolute/new/ChipContest-pe32-bank128-01 --out /absolute/new/bank128-accept-01 \
  --ramsp128-model /absolute/actual/RAMSP128X16.v \
  --cross-prefix /absolute/sifive-rv32-c/bin/riscv64-unknown-elf-
```

`--prepare-only` checks actual clone, bundle prerequisites, commits, gitlink, complete tracked file set,
bytes/modes/link targets and clean state; it does not run or qualify EDA or the supplied model path.
No candidate retention, area, 150MHz, mapped-equivalence or fullSoC-energy claim is made by this package.
