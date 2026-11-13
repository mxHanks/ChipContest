# Final storage-SRAM PPA preparation

This directory prepares a new, isolated **374-macro / 64 PE / production N2 / original32-bit SystemBus** candidate. It never uploads or starts an EDA job. Default `run_once.py` behavior is input review. A later explicit `--run` must first find an actual same-freeze production GPIO CPU complete12 PASS, raw simulation log, frozen checker and actual ELF/image sealed into this new package; missing or mismatched evidence is rejected before native tool/library access.

The source reference is sealed `build/compliant32-20261113/ppa-native-r2`, package-files SHA256 `f697416ea83570b25ad9aa9ecfb37c915f7b93547cd8aa6297297e9092313555`. The selected isolated storage overlay is `build/compliant32-20261113/storage-macro/wide-candidate-r2`, manifest SHA256 `9461237a61158e94544cd98d0db491db72cbed6530a98c48da9d78a8289a2f73`. Only `LinearTileDmaCore.sv` and `xu_matrix_dma_sysbus32.sv` production bytes change. `XU_MATRIX_STORAGE_SRAM` is added to the exact existing five production defines. No test loader define, additional source port or bus widening is allowed.

The final storage core directly instantiates eight rows of eight byte-identical signed41 accumulator MACs; it has no `DotProductEngine` child. Its named SRAM scopes are `weights`16, `biasMemory`1, `xSets`16, and `resultSlices`21. The package counts **all54 internal macros**, plus CPU64 and shared256 = **374 total**. Result SRAM is 21×1024×16 =344,064 physical bits, even though logical result state uses5,248 bits. It removes the reusable bias prefetch and result register-array caches; remaining scalar transaction assembly state is disclosed in the storage manifest.

All54 internal macros are charged by the inherited disjoint DMA scope accounting. The independent conservative upper bound includes **all full-SoC standard cells plus54 internal SRAM macros**, excluding only the320 reused CPU/shared macros. Never add that upper bound to the disjoint charged scope. Neither raw library area units nor absent official SRAM pricing establish a contest mm² score.

The original standard/SRAM libraries, original full-SoC SDC, 150MHz HF constraint, PT generated-clock portability overlay, max2 cores, hold-fix request and `compile_ultra -no_autoungroup` policy remain unchanged. Constraint report precision increases to8 significant digits to retain tiny min-capacitance failures. No timing check, capacitance/slew threshold, clock period, I/O constraint or exception is relaxed.

Prepare an offline package (no native launch):

```sh
python3 -B experiments/s3-y32-compliant32/ppa/storage/prepare.py \
  --base build/compliant32-20261113/ppa-native-r2 \
  --storage-candidate build/compliant32-20261113/storage-macro/wide-candidate-r2 \
  --out build/compliant32-20261113/ppa-storage374-new
python3 -B build/compliant32-20261113/ppa-storage374-new/run_once.py
python3 -B build/compliant32-20261113/ppa-storage374-new/preflight.py \
  --out build/compliant32-20261113/ppa-storage374-new-xml
```

After actual final GPIO complete12 PASS, prepare another NEW package with `--cpu-full12 /absolute/path/result.json`. Do not mutate an existing seal or add a late evidence file to bypass the gate. Later native execution still requires the already coordinated, independent max2-core allocation and actual same-package DC completion before PT. This directory does not initiate that execution.

Actual local evidence:

- `ppa-storage374-r1`: sealed187 inputs; default review PASS; missing-CPU12 `--run` actually rejected before native access (`ppa-storage374-gate-r1`). XML initially stopped on this collector's wrong arbiter port label; no source or hardware failure was inferred.
- `ppa-storage374-r2`: corrected collector uses actual `i_bus_icb_cmd_*` names; strict XML PASS in `ppa-storage374-xml-r2/result.json`. Macro scopes are uniquely partitioned32 ITCM +32 DTCM +256 shared +16 W +1 bias +16 X +21 result. All374 exact source-reviewed activity macro paths match the elaborated macro set after Verilator bracket-name decoding. This is elaboration evidence, not synthesis or mapped equivalence.

The corrected preparation policy explicitly lists result21, internal54 and full374, matching actual synthesis/geometry guards. Old offline r1–r4 policy JSON inherited353 wording and is superseded. The stricter CPU12 gate replays the sealed original checker against the sealed raw complete12 log, including every per-layer25344 outputs, transaction retirement, GPIO loading, timing window and55,040 physical clear writes; it also checks exact production source SET and actual ELF/image hashes. Actual same374 task0 PASS was rejected as insufficient complete12 evidence.

No 374-macro area, STA, mapped functional equivalence, mapped activity coverage or characterized power result is claimed here.
