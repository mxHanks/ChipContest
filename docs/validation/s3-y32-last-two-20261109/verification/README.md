# 41-bit saved-evidence strict verification

The baseline is current bias-demand full12 result SHA `6c60c5cda7a0740b5169077936aa150366aec79e2f59e368e8549679af3bfce1`. All171 source pins remain mandatory; only MacPE.sv may change from `74321ca1a17f355f71ecea27807078d42c9be423564d453b2f1de097ffa2ae70` to `1b8eefc0910663a6996cb7f282def3f6a0b9656e016a18bb5a8b711f5c14a8d1`.

`compare_acc41.py` derives from the previous strict verifier and retains its exact pinned original loader. It checks every raw source/artifact/log, generated C/TB, all input/golden identities, tool/clock/reset conditions, physical clear/work/protocol, output/last-response windows and loaded ELF/image. The original ELF's sole permitted nonloaded metadata variation remains the parsed local ABS STT_FILE `ccXXXXXX.o` six-character GCC random suffix; all other bytes must match after that precise normalization.

Additionally every layer's full timing/work totals, entire window and entire clear record must equal baseline. Cross-layer aggregate cancellation is rejected. This is no-cycle-change functionality evidence, never an area/energy/speed claim. `compare_acc41-initial.py` and initial receipts predate that independent-review hardening and are NOTFINAL. Final comparison receipts are `acc41-task0-comparison-final.json` and `acc41-full12-comparison.json`.

Final task0 and full12 each passed20 corruption rejections. Independent review added3 in-memory negative checks: opposite phase changes across layers, changed absolute request window and changed clear response-end time. The first task0 comparison explicitly projects original layer0 after validating the complete baseline; full12 is a separate12-to12 comparison. All measured campaign result files remain unmodified.

Reproduce using new output filenames:

```sh
python3.12 -E -B compare_acc41.py /path/to/baseline/result.json /path/to/acc41-full12/result.json --source-pairs reviewed-sourcepairs.json --out /tmp/new-acc41-comparison.json
```

The portable handoff includes the SHA-pinned inherited loader and its exact sidecars, path mappings and `revalidate_saved.py`. It revalidates archived originals without reading the original host paths, rerunning simulation or rewriting sources/results.
