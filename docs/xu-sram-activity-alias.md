# xu simulation-only SRAM activity aliases

`tools/ppa/xu_sram_activity_alias.py` generates ordinary RTL observer registers
for the physical `RAMSP1024X16` port nets. This addresses a measured VCS
visibility gap: the RTL activity region can contain the surrounding design
while omitting `celldefine` macro activity. It does not alter functional RTL,
SRAM models, input values, clocks, resets, or SRAM contents.

Every macro has 67 observed bits: `CLK`, `CEN`, `WEN[15:0]`, `A[9:0]`,
`D[15:0]`, `EMA[2:0]`, `EMAW[1:0]`, `GWEN`, `RET1N`, and `Q[15:0]`.
Each register receives an initial copy and a blocking copy on changes of the
exact hierarchical macro port. X and Z pass through unchanged. There are no
forces, inferred idle values, toggle scaling, or memory contents in the
observer. Generated sources are enclosed in `ifndef SYNTHESIS` and belong
only in the simulation source list.

## Generate the current full-SoC observer

```sh
python tools/ppa/xu_sram_activity_alias.py generate \
  --out build/xu-sram-alias/new-observer \
  --dut-scope tb_xu_soc_ppa.dut --placement bind
```

The output directory must be new. The command emits:

- `xu_sram_activity_alias.sv`: a module bound to the exact DUT instance as
  `tb_xu_soc_ppa.dut.xu_sram_activity_alias`.
- `xu_sram_activity_alias.mapping.json`: source identities, scopes, pin widths,
  all target macro instances, and the observer source identity.

Compile the generated `.sv` as a testbench source. The observer is inside the
DUT hierarchy, so the existing DUT activity region can include it without
collecting scoreboard arrays at the testbench root. Actual VCS bind support
and region coverage must be checked in the intended VCS runtime before a
full-SoC campaign. The local Icarus proof below covers the include placement;
it does not establish VCS SAIF capture support.

The source-guarded topology is 256 shared, 32 ITCM, 32 DTCM, and 16 accelerator
weight macros: 336 instances and 22,512 observer bits. Constant depth-bank and
width-lane indices are emitted as direct hierarchical references. Relevant
topology, configuration, adapter, reader, and generator files are hash-bound.
Source guards describe the current source topology; elaboration and mapped
cell inventories remain separate checks.

For a small probe, use `--placement include`, `--observer-scope tb.xu_sram_activity_alias`,
`--dut-scope tb.dut`, and one or more `--macro-path tb.dut.macro` options. Include
`xu_sram_activity_alias.svh` inside that testbench module. Explicit macro lists
are marked `explicit_probe_only` and cannot imply full-SoC coverage.

## Normalize a measured SAIF without changing the raw file

```sh
python tools/ppa/xu_sram_activity_alias.py normalize \
  --raw build/xu-sram-alias/task-raw.saif \
  --mapping build/xu-sram-alias/new-observer/xu_sram_activity_alias.mapping.json \
  --out build/xu-sram-alias/task-normalized.saif \
  --receipt build/xu-sram-alias/task-normalization.json
```

The raw, mapping, normalized output, and receipt must be distinct paths. The
normalized output and receipt must be new files. Keep all four artifacts and
the generated observer source. Regenerate the mapping whenever the generator,
reader, observer, or any guarded design source changes.

Normalization first uses the existing `read_saif` parser to validate integral
statistics and dwell sums. It then requires exactly one measured ordinary RTL
NET record for every mapped observer bit, with no missing or extra observer
signals. Missing macro activity is an error, including apparently idle cells.
The alias-to-pin mapping is bijective. All state dwell buckets, transition
counts, and additional signal statistics are copied; optional absent buckets
are equivalent only to zero when comparing existing native records.

Two exact observer name encodings are accepted. The canonical form has an
`INSTANCE macro_0000` containing a `NET CLK`, giving
`.../xu_sram_activity_alias/macro_0000/CLK`. In the measured VCS 2020 bound
observer probe, the generate block and pin are one literal NET atom,
`macro_0000.CLK`, giving `.../xu_sram_activity_alias/macro_0000.CLK`.
The same finite spelling rule applies to each mapped block and pin bit,
including `macro_0000.WEN[15]`. Exactly one NET record must supply each bit;
supplying both encodings for one bit is rejected even if the statistics agree.
Other dotted names are never split or rewritten. Unsupported names inside
the observer, duplicate representations, and spelling collisions are errors.

When a native NET or PORT already exists at the target macro pin, its statistics
must equal the alias. The native kind is reused without adding another kind.
Preexisting NET and PORT records are both checked and preserved, and their
count is recorded for later annotation review. With no native record, the
alias is written at the original macro instance as PORT activity. The entire
observer instance is removed from the transformed file. Every nonalias raw
NET/PORT record is retained exactly in meaning. Headers and quoted strings
are retained; whitespace and comments can change.

The writer streams S-expression output to a new file. A second `read_saif`
pass checks every preserved raw record, every added pin record, and the time
base. The receipt records raw and transformed SHA256 values, source and
mapping identities, complete bit counts, native reuse counts, retained signal
counts, unknown bit-ticks, and a deterministic hash of the per-bit comparisons.
It also records the count of each accepted name encoding and a hash of the
exact canonical-to-measured-source-name pairs.
The raw file identity is checked again after normalization.

## Local verification on 2026-11-02

```sh
python -m unittest discover -s tests/host -p test_xu_sram_activity_alias.py -v
```

The default suite runs an open four-state port contract stand-in and skips the
private vendor test. To run the same test against the supplied private model:

```sh
XU_SRAM_VENDOR_MODEL=/absolute/private/path/RAMSP1024X16.v \
XU_SRAM_VENDOR_SHA256=81b55d87d5e6821d44037d6f0290ec89c9edb9582eb1932957f181aefc300d51 \
python -m unittest discover -s tests/host -p test_xu_sram_activity_alias.py -v
```

The original eight-test suite passed locally with that exact vendor model,
Icarus, and `ARM_UD_MODEL`; no vendor model bytes are included in the added sources.
`tests/ppa/tb_xu_sram_activity_alias.sv` uses the existing SRAM adapter and
compares all 201 observer bits against the actual ports of three macros in
an independently collected VCD over `[2 ns,100 ns)`. The stimulus checks a
fullword read, byte-masked write/read, a gated live clock, an idle memory, an
unwritten address with unknown Q, and explicit X/Z on D. Digital port nets
are dumped explicitly, keeping private model realtime objects outside this
pin experiment.

Hand-counted clock checks are 12 transitions and 30 ns at one for the live
macro; the idle macro has CLK=0, CEN=1, and RET1N=1 for all 98 ns, with Q
unknown for the entire interval. The probe checks 20 ns of explicit X and Z
on selected D bits. The suite also verifies exact unknown-bucket matching,
native NET/PORT reuse, immutable raw/output files, source tampering rejection,
complete mapping, missing/extra/duplicate alias rejection, and native mismatch
rejection. Synthetic normalization exercises the no-native case and checks
every copied pin statistic plus unrelated raw signals, including TB dwell.
The current eleven-test suite passes ten tests locally with the open model
and skips the private-model test unless explicitly configured. Added cases
cover all 67 observed VCS name spellings, mixed exact encodings, duplicate
encodings, unsupported dotted names, literal-dot nonalias preservation, and
all 45,024 canonical/VCS name candidates for the full topology. These
synthetic name fixtures do not by themselves qualify VCS activity capture.

These are local functional and digital-activity checks. They do not establish
full-SoC VCS activity completeness, mapped annotation, Liberty internal power,
SRAM PVT eligibility, timing, energy, or contest qualification. Q unknowns and
any input unknowns remain evidence requiring downstream review.
