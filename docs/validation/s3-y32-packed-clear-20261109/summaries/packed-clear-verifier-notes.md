# Strict saved-evidence verifier

`packed_clear_compare.py` is a standalone read-only verifier derived from the earlier READY comparison verifier. It runs no simulator, synthesis, compiler, objcopy or external command. The fixed original twelve-layer READY result SHA is `0e57d26b7493cfc8a98846346bb5183b5d6132d089000782972adfe199a58a28`; its 170-source map is separately pinned in `ready-baseline-sources.json`. The old campaign generation functions are separately pinned in `baseline-campaign-seams.json` and verified before use.

The only allowed reviewed source pairs are the changed `campaign.py` and addition `tools/ppa/s3_task_packed_clear_protocol.py`. Every original RTL, payload firmware/header/main, original TB, contract/parser, model/vector exporter and old scalar/legacy helper remains fixed byte for byte. Candidate source count must be 171. The final selected pair file is `packed-full12-sourcepairs.json` (the same exact pairs as final task 0).

The verifier independently checks each real ELF PT_LOAD byte against that campaign's actual ITCM image, not just ELF or image checksums. Clear code changes may relocate frozen payload code; ELF/images are therefore independently verified rather than required equal. For each algorithm, generated clear C must equal exact regeneration from its own source-pinned helper and frozen main, normalizing only the precise old frozen-main include path for evidence relocation. Generated TB must equal the original payload TB processed by the unchanged independently pinned old instrument/clock/reset functions and the selected helper's exact observer. No general code or TB normalization is allowed.

Saved/raw commands, versions, artifact hashes, tensors, external reset, measured clock rounding, numerical PASS markers, work counts and complete first-source-VALID-to-last-Y-response windows are checked for every layer. A partial experiment first verifies all twelve baseline layers and then explicitly projects original layer 0. Final acceptance requires twelve candidate layers in the original order and a twelve-to-twelve comparison.

Only the explicit clear profile/helper/count schema is removed for condition equality. Every remaining condition and normalized command must match. MMIO clear counts and clear timing differ by design, and each algorithm is validated independently. Logical physical clear work/policy must match. Candidate evidence additionally measures true core W/X write edges, every W macro write edge/address/data and all 768 bias SRAM writes; historical baseline logs do not contain those new macro-edge observations.

All payload timing, phase, stall, overlap, FIFO wait and READY wait cycle differences remain visible. No padding is added and no timing is normalized away. The final single-layer candidate has a real one-cycle first VALID-to-accept wait, so payload is 425540 rather than the baseline 425539. Fixed transaction/MAC/output work remains equal.

`test_packed_clear_compare.py` uses hardlinked read-only evidence copies and atomically replaces only the stated mutant files. Thirteen real saved-artifact corruptions exercise source/tensor pins, generated C omission and added `nop`, original payload observer preservation, actual image loading, physical coverage marker, early proof, policy promotion, timing relation and duplicate markers. These are verifier corruption tests, not fabricated native simulation results. Each mutated artifact and actual rejection is retained. Separate real-wrapper negative simulations owned by the helper tests exercise omitted physical writes, masks/errors, pending beats, reset, bias staging and nonzero pre-state.

`UNPROVEN` FIFO payload physical zero and `REVIEW_PENDING` policy must remain unchanged. This tool does not grant official qualification, gate-level signoff or PPA results.

Example final comparison (from repository root):

```sh
python3.12 -E -B build/packed-clear-20261109/packed_clear_compare.py \
  build/ready-20261109/ready-full12/result.json \
  build/packed-clear-20261109/packed-full12/result.json \
  --baseline-sources build/packed-clear-20261109/ready-baseline-sources.json \
  --source-pairs build/packed-clear-20261109/packed-full12-sourcepairs.json \
  --out build/packed-clear-20261109/packed-full12-comparison.json
```

The output path must not already exist. Auxiliary verifier pin files must remain beside the verifier when relocated. Campaign artifact folders can be relocated: integrity checks use their current root while saved commands and C include-path regeneration use the originally recorded absolute path.
