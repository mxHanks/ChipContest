# SYSBUS32 sealed PPA preparation

This directory prepares exact **64-PE, original 32-bit SystemBus** source profiles
for one later, coordinated synthesis experiment. The selected X SRAM profile
has353 macros; the explicit register-X reference profile has337 macros. Preparation
and local preprocessing/XML elaboration launch no DC, PT, remote process, transfer,
simulation or power analysis. They are not area/timing qualification.

The X SRAM production defines are exactly `SYNTHESIS DISABLE_SV_ASSERTION=1
XU_MATRIX_DMA XU_MATRIX_DMA_SYSBUS32 XU_MATRIX_X_SRAM`; `XU_MATRIX_DMA64` and
`XU_SYSBUS_TEST_LOADER` are absent. The register-X reference omits only
`XU_MATRIX_X_SRAM`.
The full digital SoC top is
`experiments/s3-y32-compliant32/structure/xu_soc_sysbus32_ppa_top.sv`.
No production pad or exposed test loader is added to that top. The ingress's
simulation-only loader inputs are tied inactive with `TEST_LOADER=0`.

The source stage reuses selected B's actual compile-file ordering and its exact
two physical SRAM adapters. It excludes the three inactive historical wide DMA,
arbiter and endpoint files, adds the new32 DMA/ingress and original32 endpoint,
and records each source origin, order, bytes and SHA256. All sources outside the
four integration wrappers and two new interface modules must match selected B.
The X SRAM profile stages only its explicit candidate core and new
`TileXMacroRowBuffer.sv`, leaving every other B41 arithmetic dependency exact.
The original B41 core SHA256 is
`710b8e180652f49751769e152a3b3a9e6a35ba622fb4c3e2385dc5ffab241fcb`.
Its published child blob is checked even after the identical selected overlay
has been installed. The register-X profile always restores that original core
from the fixed tracked reference archive and labels its source accordingly.
The CPU `rtl/e203/core` directory and `e203_subsys_mems.v` remain exact published
child `ccdac30d92ecf40f14d0b78879b8711fb0b1cdd1` bytes. No production RTL is edited.

Preparation works without a private historical `build/area-opt-*` tree. By
default it recovers only required reference files from the tracked
`docs/validation/s3-y32-area-opt-20261111/candidate-b-ppa-inputs-r3.tar.xz`
(SHA256 `8a03367cda442aff22d9e7806c82964f454934d0c80cb299420de436f68a5d48`)
and the two native PT script/receipt members of the tracked
`candidate-native-reports-r4.tar.xz`
(SHA256 `fd235de2b63b06b321d9940641937e1a29a35c6497ca6ba3ed89687be13fd763`).
Relocated copies can be passed with `--reference-package` and
`--reference-native-package`; the expected archive SHA256s remain fixed.
Every tar member is checked before extraction: absolute/traversing/noncanonical
paths, duplicate names, symbolic/hard links and special nodes are rejected.
Only pinned regular files are written into new sibling reference-cache
directories, with per-member hashes checked. Existing caches must match exactly
and are never overwritten. `reference-recovery.json` records this provenance.

## Prepare and inspect locally

From the repository root, using fresh output names:

```bash
python3 experiments/s3-y32-compliant32/ppa/prepare.py \
  --x-candidate build/compliant32-20261113/x-macro/candidate-r2 \
  --out build/compliant32-20261113/ppa-xmacro-inputs-r2 --archive
python3 build/compliant32-20261113/ppa-xmacro-inputs-r2/run_once.py
python3 build/compliant32-20261113/ppa-xmacro-inputs-r2/preflight.py \
  --out build/compliant32-20261113/ppa-xmacro-local-r2 --elaborate
```

`--x-candidate` requires an exact overlay manifest. Its independently pinned
default SHA256 is candidate-r2
`5a7ae65ece333666fdf15c6c717bc9a102892d3d36a0fcc04305b0f6a780abdd`.
An intentionally different reviewed manifest requires
`--x-candidate-manifest-sha256`; source SHA256s, fixed B41 origins, physical
capacity, clear contract and file set remain checked. Symlinks, extra files,
missing inputs and modified candidate bytes fail. A copied manifest is sealed
inside `evidence/x-candidate/manifest.json`. The new source list has159 entries,
including the physical X wrapper; generic SRAM models stay outside `rtl.f`.
Omitting `--x-candidate` prepares the separate337-macro register-X reference.
No old sealed directory or production source is overwritten.

Default `run_once.py` only rehashes/reviews sealed inputs. `preflight.py` runs
single-core Verilator preprocessing and optional XML elaboration, using a generic
functional SRAM model **outside `rtl.f`**. It checks the production branch and
353 unique macros: ITCM32 + DTCM32 + shared256 + weights16 + bias1 + X16;
33 internal macros; eight engines,
64 PEs, one ingress32, one DMA32 and one original32 endpoint, with zero historical
wide/downstream arbiter instances. It checks Tcl script completeness without
evaluating EDA commands. All preflight evidence is placed outside the sealed
experiment; prior outputs are never overwritten.
The337 profile has an exact separate geometry, with X macros zero and17
internal macros. Preprocessing checks16 selected X rows of the correct kind.
DC before/after mapping and PT each use the same sealed exact geometry and
require all SRAM scopes to be disjoint and exhaustive.

`package-files.json` seals every prepared input. `source-manifest.json` is the
ordered per-source manifest. `pinned-cpu-and-mem-fab.json` records immutable
platform sources. `synthesis-emitter-vs-B.patch` exposes every emitter change.
`toolchain.json` preserves exact **actual old B native** DC/PT/LC and two DB paths
and SHA256s. The local preparation does not have or certify those library bytes;
the future runner rehashes the actual executables and DBs before launch.

## Later native execution, separately coordinated

The following are documented future commands, **not authorization to execute now**:

```bash
python3 run_once.py --stage dc --run
python3 run_once.py --stage pt --run
```

They are local-only commands intended to run from the new candidate directory on
the separately coordinated native host. There is no SSH/remote-launch code. Each
stage refuses a restart or an existing output. Both retain `max_cores=2` and
refuse concurrent same-account native heavy jobs. DC defaults to a bounded 14400s
tool lifetime; PT retains the native-tested 300s bound. A timeout is a failed
collection, never a timing result.

DC retains selected B's `compile_ultra -no_autoungroup`, hierarchy preservation,
macro dont-touch, `set_fix_hold [all_clocks]`, envelope clock mode and exact input
SDC. New hierarchy guards execute before/after mapping. The reference SDC SHA256
is `c15ede0fc2c65771f87e2d6aee763b4ea0d53934868ca807b4785c36182fce7c`.
There is no added false path, multicycle path, clock-group exception, ideal
network, relaxed I/O delay, clock period, uncertainty or gating check.

PT accepts only this new package's clean DC execution receipt and rehashes the
new `mapped.v`, DDC, mapped SDC, leaf TSV, component report and library list. It
cannot import the old B mapped receipt/netlist as new32 evidence. It replays the
original SDC using the exact native-proven three `create_generated_clock -add`
portability substitutions in a new output-local copy; source/master/period/edge
and every other SDC byte retain their original meaning. Expected transformed
SHA256 is `404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`.

The collector retains native-tested global/group setup/hold, all violators
(including electrical DRC), recovery/removal, gating setup/hold, minimum pulse,
exceptions, case analysis, disabled timing, complete analysis coverage and
per-register/SRAM clock association. Unsupported optional commands create
explicit unavailable files. DC's unsupported coverage/exception/async reports
remain explicit gaps requiring PT. The historically unbounded Cartesian DMA
register query remains omitted and documented; no timing path is waived.
Finite worst-path samples do not establish closure. Collection completion
never means timing closure or official qualification.

## Area and unresolved obligations

`area-charge-policy.json` explicitly charges:

- All DMA32 front-end/scheduler, core/FIFO/control, 64 PEs, weight/bias adapters,
  X double-buffer control/adapters, all16 X physical macros,16 weight macros
  and one bias macro. Logical X holds2KiB, but the entire32KiB physical X
  allocation is charged. There is no utilization discount.
- All upstream SystemBus ingress32 arbitration, owner state and address/data/
  control mux logic.
- All standard-cell logic of the original32 shared endpoint, conservatively.
- The complete CPU `u_e203_cpu/u_e203_nice_core` standard-cell scope,
  conservatively, including reused logic. This covers retained legacy NICE mux,
  drain8 and direct-interface logic without subtracting their reused portion.

Every full-SoC leaf is listed once in `leaf-inventory.tsv`, and all353 SRAMs are
uniquely grouped. `area-components.tsv` partitions all charged leaves and checks
its sum against the charged leaf total. CPU and reused shared SRAM savings are
not credited. Matched-baseline positive standard-cell growth outside the named
scopes must be checked and added separately before any final area claim.
The true original-platform baseline is child
`f64a430f172c701df43e3d63afaf9dc0178096e1`, with the same library and matched
configuration. Selected B already contains earlier interface additions and is
not an incremental-area baseline. Any retained added passthrough/interface
logic outside the named scopes also belongs in the final charge.

`area-upper-bound.tsv` separately collects **all full-SoC standard cells**,
including the CPU and reused peripherals, plus all33 internal SRAMs. Only
the320 reused CPU/shared SRAMs are excluded. Thus this conservative upper bound
does not depend on finding every increment against the original platform.
Its official formula is full-SoC standard-cell area in verified mm² plus33
times the official RAMSP1024X16 macro price. The raw DB-area sum is reported
separately and establishes no official conversion. If verified units and macro
prices later put this upper bound at or below2.25mm², it bounds area only; it is
not an official area score or full qualification. No baseline or EDA job runs
during preparation.

Raw library area units have no verified mm² conversion. The official SRAM area
table remains unresolved. No mm² value or contest-area verdict is produced.
The isolated353-macro package stages the explicit selected X SRAM overlay.
The original337-macro sealed packages remain unchanged as historical reference.
Preparing either profile does not authorize native execution or establish an
official area/timing verdict.

New32 simulation/numerical validation, the complete official input-to-writeback
measurement window, mapped functional equivalence, active-power annotation and
coverage on this same new netlist/window, complete SoC+SRAM average power and
energy remain separate obligations. The package copies no old area/netlist/
functional status as new proof. `reference-B.json` labels the old211 violated and
27911 untested timing checks as **old B reference facts only**. Old evidence is
preserved unchanged.
