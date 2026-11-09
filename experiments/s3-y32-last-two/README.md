# Optional S3-Y32 dataflow experiments

Default production remains the measured8PE/48-bit READY/packed-clear/bias-demand version. None of the experimental NICE files are installed into the E203 submodule. Full-SoC measured best remains5,874,840 cycles for12 layers including separately observed physical clear.

- `acc41/`: complete signed16/signed40/64-product prefix bound and real generated48/41/40 RTL comparison. `LinearAutoGroupCore41` is an explicit generator. Only eight ACC registers narrow; every public result and result buffer remains48. Default generator produces the original48-bit RTL exactly.
- `rowpair/`: shared weights/bias, two input rows and16PE; actual speech task0 raw48 captures and read-only physical macro observations, with five controlled sink stalls. Comparator is the same prototype in one-row mode, not the production SoC.
- `paired-nice/`: explicit0x25 strided two-row transfer, with pair capability and row identity. Uses the same one-command/one-response NICE LSU transport. It is not an independent DMA and has no production CPU/MMIO/firmware integration.

Run all commands from the repository root; output directories must be new:

```sh
python3.12 -E -B experiments/s3-y32-last-two/acc41/run_acc41.py --out /tmp/new-acc41
scala-cli run . --server=false --jvm system -M GenerateRTL -- LinearRowPairPrototype
python3.12 -E -B experiments/s3-y32-last-two/rowpair/run_rowpair.py --repo "$PWD" --vectors /path/to/task0 --out /tmp/new-rowpair
python3.12 -E -B experiments/s3-y32-last-two/rowpair/verify_rowpair.py /tmp/new-rowpair
python3.12 -E -B experiments/s3-y32-last-two/paired-nice/run_probe.py --repo "$PWD" --generated-rowpair generated/LinearRowPairPrototype --vectors /path/to/task0 --out /tmp/new-paired-nice
```

The vector directory must contain x.mem,w.mem,bias.mem,y.mem,y32.mem from the pinned speech task0 fixture. The complete evidence archive includes these files; filenames and SHA are checked in each receipt. The paired fixture requires an ASCII vector path at most128 bytes; its runner rejects unsupported paths before creating output.

The acc41 runner builds a source-only snapshot and does not replace installed RTL. To reproduce the full-SoC41-bit campaign, use a separate copy, generate `LinearAutoGroupCore41`, replace only that copy's installed MacPE.sv with the generated41-bit file and run the unchanged packed-clear/READY CPU campaign. Do not replace the default production file in a shared checkout.

Module cycles exclude real CPU instruction and fabric behavior. Controlled sink timing is not measured production LSU service, and reduced physical reads do not prove energy savings. The new two-row clear controller is a module experiment; its direct port window does not replace the production MMIO clear recipe or its policy status. No synthesis/STA/energy/official qualification was performed.

See [complete results](../../docs/s3-y32-last-two-results.md) and the local `build/last-two-20261109/handoff/README.md` for original raw evidence, failures, strict comparisons, portable verification and rollback.
