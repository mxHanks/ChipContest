# xu private observations 133: source plan and read-only extractor

The original S2c target mapped body is not present in the searched local
ChipContest worktrees. Its required SHA256 is
`9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892`
and its recorded length is 14,199,670 bytes. All **60 private gates remain
pending**; this preparation changes no original source, fatal, preload, DUT
state, clock, constraint, VPI callback, simulator argument, or acceptance rule.

`source-review133.json` and `private60-source-table.md` cover every private
reference from the original 72-reference plan. The 12 already-public ports and
288 original preload statements are not reclassified as private proof.

## What can be decided from source

The two production accelerator source files match the actual S2c PPA source
manifest by SHA, as recorded by115. The retained-port lookup strategy covers
40 private references:16 core aliases,13 nested core ports,9 HCLK controls,
and2 EXU commit inputs. This is a source strategy, not40 proven mapped bindings.

The remaining20 references require retained-name inspection, physical FF
reconstruction, or formal correspondence:17 private state names,2 wrapper
combinational expressions (`busy` and `row_start_accept`), and the sole referenced
regfile element `rf_r[3]`. No reference can honestly be labelled “synthesized
away” without the target body or actual synthesis/formal correspondence evidence.

The extractor makes three **static** distinctions on its selected input:

1. A named module port/net or complete escaped scalar bundle exists at the
   candidate/original path with the exact expected width.
2. A retained `_reg` FF endpoint or a known wrapper expression with every operand
   located in this same netlist is a candidate for physical reconstruction.
   FF pin names alone do not establish polarity or library semantics. No
   reconstruction expression is executed by this static inventory.
3. A required endpoint was not located or needs formal correspondence. Failure
   to find a name does not prove synthesis removal.

All three categories remain unqualified until their actual native handles,
four-state runtime values,
sampling edge, alias/polarity meaning, and original assertion semantics have
been demonstrated. No two-state conversion, shadow RTL state, inferred zero,
MMIO acceptance substitute, or HOST+4 shortcut is supplied.

## Priority and exact missing evidence

* **X/bias clear:** bind actual `io_xLoadWen/Addr/Data` and
  `io_cacheWriteEnable/Addr/Data/Mask`, plus `cache_enable`, legacy `bias_regs`,
  and the original clear ownership/strobe state. Keep the original post-reset
  sampling edge and per-address/per-byte uniqueness checks. Commit observation
  alone does not prove downstream physical FF contents; retain the final111
  physical-clear gate until actual state/correspondence evidence exists.
* **FIFO ownership:** bind active/running/count/produced/retired/head/tail,
  start/pop/valid/group/result, core start/done, and stream ownership. Preserve
  initial empty ownership, `produced-retired=count`, row storage exclusion,
  complete16-word retirement, and response stability. The original S2c
  `LinearAutoGroupCore` state equations are recorded, not replayed as shadow state.
* **PLL nine controls:** bind the nine actual HCLK module inputs with exact
  widths. Preserve the original vector
  `{0,1,1,6'b0,0,0,2'd2,8'd50,5'd2}` at every original static-check edge.
  A tie-off requires actual connected constant evidence and runtime four-state
  checks; a source default is insufficient.
* **EXU halt:** bind actual commit valid and32-bit PC, plus the32-bit output
  corresponding to original `rf_r[3]`. Preserve the original halt condition
  PC=`32'h80000086`, GP=`1`, completed=`tasks`, SAIF end and LF-clock checks.
  The source's disabled latch-based regfile configuration makes
  `regfile[3].rfno0.rf_dffl.qout` a lookup candidate, not a target binding proof.

Required server-side design source, read only:

```
/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/s2c-ppa-campaign-20261103-01/s2c/ppa/mapped.v
```

The default extractor refuses any different hash/length before creating output.
It reads no vendor library/model body and emits no entire design module body.
Its output has source hashes before/after and exact names, widths and selected
design FF pin bindings. For absent/renamed state, the next necessary inputs are
the **same target's** synthesis renaming/register mapping and Formality reference
to implementation correspondence, or a same-netlist native hierarchy/VPI probe.
The available116 netlist cannot replace those target inputs. This133 script
does not call DC, PT, FM, VCS, FTP, VNC, a shell command, or a network API.

## Reproduction

Run in this directory after copying its public files into a new server tools
directory (this work performed no remote operation):

```sh
python3 extract_private133.py \
  --mapped /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/s2c-ppa-campaign-20261103-01/s2c/ppa/mapped.v \
  --out /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/private-target133-static-new
```

Local parser mechanism reproduction on **different** actual116:

```sh
python3 build/xu-mapped-private133/extract_private133.py \
  --mapped build/xu-score-resume-20261103/terminal122/full-soc-timing-combined-20261105-116/mapped.v \
  --out build/xu-mapped-private133/mechanism116-new --mechanism-only
python3 build/xu-mapped-private133/host_checks133.py
```

`mechanism116-v3/inventory133.json` is the final recorded parser run. It finds927
design modules/scopes and60 reference records:37 retained endpoint lookups and23
unlocated/formal-required entries. In particular, the unbound source-only
`row_start_accept` expression is category3, not a mapped reconstruction.
Those are properties of **actual116**, whose SHA is
`16d29dea71ed2668b33c893e1a38be01a6eea02ca190ba8aabcb4658fe610292`.
They are **not S2c target counts or any passing gate**.

Earlier local iterations `mechanism116` and `mechanism116-v2` were preparation
outputs, not exported native evidence. The first counted one unbound source
expression as a category2 candidate; v2/v3 require all physical operands before
that classification. The final v3 also freezes all helper identities before/after.
Only the final v3 inventory is used by the committed host checker.

`mapped_parser123.py` is the unchanged public123 parser, SHA
`688aa9aa49b85c08d493e9cf50b150376f311acfa07bfa0245d80c14c100b4e9`.
Its strict structural subset handles escaped atomic identifiers and rejects
unknown syntax. Both hash guard paths, exact widths, scalar bundle order,
unknown-token preservation, escaped RF3 hierarchy and the unrelated116 identity
are exercised by the host checks. No mapped task00, timing, energy, or contest
qualification is claimed.

Recreate the60-row source review from the manifest-matched local S2c checkout:

```sh
python3 build/xu-mapped-private133/review_sources133.py --out build/xu-mapped-private133/source-review-new
```
