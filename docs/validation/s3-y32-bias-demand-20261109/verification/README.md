# Bias next-demand experiment: independent verification

This directory contains read-only saved-evidence checks. It does not simulate,
synthesize, edit measured sources, estimate PPA, or establish official policy
qualification. The physical-clear policy remains `REVIEW_PENDING`; FIFO payload
physical zero remains `UNPROVEN`.

`compare_bias_demand.py` imports the prior complete packed-clear evidence loader
only after its SHA256 is checked as
`2554944714fafb04370570b66ab217be283d4e2dd18306bfae22e06ef5567af2`.
It finds this loader in an ancestor repository's documented evidence directory,
or under `inherited-packed-clear-verifier/` beside this script. The loader's
SHA-pinned `baseline-campaign-seams.json` must remain beside that loader.

The new comparator changes only its prior hardcoded eight-PE core pin while
loading the candidate, using the already reviewed pair:

| Source | Baseline SHA256 | Candidate SHA256 |
|---|---|---|
| `rtl/perips/LinearAutoGroupCore.sv` | `ebc9c411a6318000369f6c466381767a469bb9d33454e4c955df713c728f9ab4` | `7d3c0f9acb6adc19c65c35360f9595fd625a68764560322c1fd3900cb650f18a` |

No arbitrary pair is accepted. All 171 source paths and file hashes remain
mandatory. CPU/fabric/firmware/TB/parser/model/clear helper identities remain
fixed. The original baseline result SHA256 is pinned as
`80cd3a507ff2ae6ace6b743eab6c8c6381f2927ffdbb27851f3b82205e534d4b`.

Both sides use the same packed-MMIO physical clear and READY firmware. No
profile, macro, selector, recipe, counter, workload or timing adjustment is
removed for comparison. The only command normalization substitutes the exact
saved repository and campaign path prefixes for relocation. Every raw layer log,
numerical `TASK_PASS`/`SOC_PASS`, counter marker, source, tool version, simulator
binary hash, ELF, loaded image, tensor/model artifact, external-reset observation,
measured clock, physical-clear work count and generation seam is revalidated.
The unchanged testbench compares every Y32 result: 25,344 per layer. The full12
comparison requires all twelve original layers; a pilot explicitly projects only
the already fully verified baseline to original layer 0.

Final independent results:

| Evidence | Baseline | Candidate | Measured delta |
|---|---:|---:|---:|
| Pilot original layer 0, payload | 425,540 | 422,768 | -2,772 |
| Full12 payload | 5,106,480 | 5,073,216 | -33,264 |
| Full12 physical clear | 801,624 | 801,624 | 0 |
| Full12 payload plus clear | 5,908,104 | 5,874,840 | -33,264 |
| Full12 clear-to-source gap, excluded from main metric | 1,224 | 1,224 | 0 |

All twelve candidate layers have 422,768 payload cycles and 66,802 clear
cycles. The unchanged numerical observer checks 304,128 Y32 outputs across the
full12 run. The payload reduction is 0.6514%; payload plus physical clear falls
0.5630%. Work/transaction counts stay equal. Raw phase changes are retained:
`other` -32,076 and `writeback` -1,188 over full12; READY wait falls 32,076.
No phase is relabelled to manufacture a compute-throughput improvement.

Final receipts are `pilot-task0-comparison-final.json`, `full12-comparison.json`,
`pilot-negative-checks-final/result.json`, `full12-negative-checks/result.json`,
and `complete-map-revalidation.json`. Both negative suites reject all twenty
expected corruptions. The revalidation checks both pilot and full12 against
their complete saved comparisons.

## Reproduce in a repository checkout

Run from the checkout root, choosing new output names because results are created
exclusively:

```bash
python3 build/bias-demand-20261109/verification/compare_bias_demand.py \
  build/packed-clear-20261109/packed-full12/result.json \
  build/bias-demand-20261109/pilot-task0/result.json \
  --source-pairs build/bias-demand-20261109/verification/reviewed-sourcepairs.json \
  --layers 0 --out /tmp/bias-demand-pilot-recheck.json

python3 build/bias-demand-20261109/verification/compare_bias_demand.py \
  build/packed-clear-20261109/packed-full12/result.json \
  build/bias-demand-20261109/full12/result.json \
  --source-pairs build/bias-demand-20261109/verification/reviewed-sourcepairs.json \
  --out /tmp/bias-demand-full12-recheck.json
```

The compact Git evidence may instead be under
`docs/validation/s3-y32-bias-demand-20261109/verification/`; the script supports
either location without changing its bytes.

## ELF identity

The 1,002 loaded firmware bytes and complete ELF PT_LOAD contract must be
identical. Raw ELF hashes differ across independent GCC builds because of a
temporary object basename, for example `ccjb06CB.o` versus `cciePHV1.o`.
`normalized_elf_file_symbol` parses the ELF32 section and symbol tables. It
requires exactly one local, absolute, zero-valued, zero-sized `STT_FILE` symbol
matching `cc[A-Za-z0-9]{6}.o` in non-allocated `.symtab`/`.strtab`, proves the
string table does not overlap any file-backed PT_LOAD, and requires that basename
to occur once. Only its six random characters are replaced, keeping all lengths,
offsets and every other byte. The complete normalized ELF SHA must then match.
Headers, loaded bytes, other symbols, attributes, other metadata and appended
bytes cannot change. Both raw hashes and parsed normalization evidence are
retained in the result. `*-elf-readelf.txt` independently documents the pilot's
sole raw ELF difference.

## Corruption checks

`test_compare_bias_demand.py` reuses the SHA-pinned prior fixture helper
(`eae8094fe916580c2f960ee86ee9b33d109943047ed64a9b13f3dc69a4e200f7`).
For portable execution, put `test_packed_clear_compare.py` beside the inherited
loader. It uses hardlinked read-only copies and atomic replacement; original
campaign bytes are never mutated. Python bytecode writes are disabled. Twenty
negative cases reject CPU/source changes, unreviewed pairs, source manifests,
tensor changes, missing clear writes, padding, disabled/weakened observers,
loaded image changes, nonloaded ELF additions, physical-clear work/policy/time
changes, duplicate or incomplete numerical markers, tool version differences,
and source drift. Changed corruption bytes and actual rejection messages are
retained; they are not native performance evidence.

The initial two fixture-harness attempts are preserved with explicit failure
receipts. One discovered untracked generated bytecode while collecting changed
artifacts; another reached an earlier valid plan/result mismatch than intended.
The final harness avoids bytecode writes and consistently alters both plan and
result before checking the externally pinned manifest. The pilot's final
20-case receipt is `pilot-negative-checks-final/result.json`.

## Relocated immutable evidence

Use the archive's actual relative campaign names; do not change any saved
absolute paths or original campaign JSON. Example for the proposed archive
layout:

```bash
python3 proofs/verification/revalidate_relocated.py \
  --archive "$PWD" \
  --baseline baseline-packed-full12/result.json \
  --pilot pilot-task0/result.json \
  --full12 full12/result.json \
  --out /tmp/bias-demand-relocated-recheck.json
```

This rebuilds both strict comparisons from the moved raw artifacts and compares
every saved result field, excluding only the current verifier/loader/result file
locations. Original SHA identities, layer coverage, raw markers, numeric proof,
conditions, physical-clear counts, firmware identities, source changes, measured
cycles and all per-layer/totals deltas must remain equal. It creates a separate
receipt and never rewrites evidence.

`baseline-identity-final2.json` is baseline-to-itself validation explicitly
labelled `IDENTITY_VALIDATION_NONPERFORMANCE`; it makes no performance claim.
