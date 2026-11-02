# xu approved S1 PPA source profiles

`tools/ppa/xu_soc_implementation.py` defaults to the original strict `baseline`.
Candidate support is opt in through `--profile`; it is not an arbitrary child-pin
override. The approved child commits and their complete changes from baseline are:

| Profile | Exact E203 child commit | Allowed changed child files |
| --- | --- | --- |
| `baseline` | `f49a5fc914971426bd4530db39e270a84b41139f` | none |
| `h2-only` | `434628c1525931c15dfaf06b5586118eb530ccba` | `rtl/e203/perips/LinearCachedCore.sv`, `rtl/e203/perips/accel_icb_slave.v` |
| `sram-bias` | `eee41507965d562066af3335192e3ef93ef36d31` | `rtl/e203/perips/BiasSramCache.sv`, `LinearSramCachedCore.sv`, `accel_icb_slave.v`, `mem_32x40.sv` |

The guard compares the complete child Git trees to baseline, checks every tracked
worktree file's bytes and mode against the approved commit independently of Git
index flags, and rejects extra RTL files. The other platform files remain exactly
baseline. Preparation and prepared-input verification repeat the profile check.

All profiles retain exactly 336 `RAMSP1024X16` macros: ITCM 32, DTCM 32, shared RAM
256, and accelerator weights 16. `sram-bias` adds exactly 24 `RAMSP128X16` macros
through the hash-pinned `xu_bias_sram_adapter.sv` replacement for `mem_32x40.sv`.
The bias cache has eight logical banks of 32 by 40 bits (10,240 logical bits).
Each bank uses three physical 128 by 16 macros, giving 49,152 physical bits and
38,912 padding bits. These figures must not be reported as 10,240 physical bits.

Generated DC/PT checks count actual macro leaves within each fixed hierarchy
scope and account for every leaf in the `RAMSP*` technology namespace. Unknown
references, extra or ungrouped macros, overlaps, and wrong counts fail. The SRAM
libraries are linked; only libraries with role `standard_cell` are targets.
The extra RAMSP128X16 `.db` has role `bias_sram` and is required only for
`sram-bias`. Its path and supplied SHA256 must both be provided.

Run the current producer against an independent candidate source checkout:

```sh
python3 /absolute/current-tools/tools/ppa/xu_soc_implementation.py \
  --root /absolute/candidate --profile sram-bias --out /absolute/new-output \
  --standard-cell-db /absolute/std.db --standard-cell-sha256 "$STD_SHA256" \
  --sram-db /absolute/RAMSP1024X16.db --sram-sha256 "$SRAM1024_SHA256" \
  --bias-sram-db /absolute/RAMSP128X16.db --bias-sram-sha256 "$SRAM128_SHA256"

python3 /absolute/current-tools/tools/scripts/xu_soc_ppa.py prepare \
  --root /absolute/candidate --out /absolute/new-prepared \
  --implementation /absolute/new-output/implementation.json \
  --allow-unqualified-mapping
```

For `h2-only`, select that profile and omit both bias-library arguments. For
baseline, omit the profile and bias-library arguments.

`--root` selects the platform/test source checkout. The generator imports its
adjacent current PPA module and uses its adjacent top, SRAM adapters, SDC and clock
review assets; it does not import the candidate's older PPA code. Clock review
records each actual source path, resolving platform/test files from the candidate
and PPA assets from the current tool checkout. The implementation binds the
candidate's main/child commits, complete approved child tree identity, source
manifest, memory geometry, library configuration and separate producer hashes.
Preparation copies these exact source bytes and records their origins.

Generation/preparation remains `NOT_QUALIFIED`. The mapping review starts
`UNREVIEWED`, with every check `NOT_RUN`; development measurements require
`--allow-unqualified-mapping`. Host guard tests validate these contracts, not
technology-cell timing, SRAM mapping equivalence, activity coverage, power, or a
contest score. The existing STA and activity qualification gates remain required.
