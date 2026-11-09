# Ready transport evidence verifier

`ready_compare.py` is an independent copy of the already strict postflow verifier. The original verifier, original selected campaign, and sealed postflow evidence are not edited. It reads saved files only; it never launches a simulator or a synthesis tool.

The only accepted direction is `stream32-pe8` to `ready32-pe8`, using the same original eight-PE core SHA and the same complete 170-source set. The original selected-full12 result and complete baseline source map are pinned by SHA in the verifier. Candidate changes require exact before/after SHA pairs and the fixed whitelist: wrapper, NICE, firmware implementation, firmware header comments, SoC testbench, contract, parser, and campaign. Header changes must preserve every noncomment byte. All changed paths remain listed in the comparison receipt.

It independently rehashes all sources, saved raw command/log pairs, ELF and simulator binaries, tensor files, generated clear C/testbench, and RTL filelist. Both load images must match the corresponding ELF PT_LOAD bytes. Raw numerical, physical work, NICE/direct/stream/ready, clear, window, clock, and startup markers must match saved data and the exactly pinned campaign parser. Ready status polls must be zero. The legacy stream profile still requires at least 3,168 retired status responses. The immutable clear C may differ only in its one known snapshot include path.

Only the exact named schedule, compiler `DRAINN`/`READY` macros, and `STREAM`/`READY` runtime selectors are normalized. All other commands, arguments, tool versions, clocks, startup semantics, input tensor identities, physical clear work, and test conditions must match. The READY-only leading fence remains compiled into the candidate and its cost remains in the measured payload. No cycle count or phase is normalized.

For a single-layer experiment, `--layers 0` first verifies all twelve original baseline layers, then compares the explicit common original layer against the candidate. The receipt records baseline original coverage `[0..11]`, candidate original coverage `[0]`, and compared coverage `[0]`; neither source result is edited. Without `--layers`, twelve candidate layers are required and the receipt says `full12-to-full12`.

Example after a reviewed candidate source-pair file exists:

```sh
python3.12 -E -B build/ready-20261109/ready_compare.py \
  build/postflow-20261108/selected-full12/result.json \
  build/ready-20261109/ready-fenced-task0/result.json \
  --baseline-sources build/ready-20261109/selected-baseline-sources.json \
  --source-pairs build/ready-20261109/ready-task0-sourcepairs.json \
  --layers 0 --out build/ready-20261109/ready-task0-comparison.json
```

`test_ready_compare.py` creates temporary hardlink clones, then atomically replaces only corrupted fixture files. These are labelled synthetic evidence corruption tests. They cannot modify measured source campaign files through the hardlinks, and they never execute the hardware simulator. The CLI and negative receipts must exist before claiming a candidate comparison has passed.
