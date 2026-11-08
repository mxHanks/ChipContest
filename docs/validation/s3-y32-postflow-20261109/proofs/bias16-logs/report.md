# 16 PE + independent bias SRAM streaming, 2026-11-09

Formal canonical layer-0 result: development PASS, 25,344 exact outputs. Payload **469,191 → 464,340** (-4,851, 1.034%), physical clear remains 198,403, total **667,594 → 662,743** (-0.727%). This remains 11,081 payload cycles slower than the selected 8 PE direct baseline (453,259).

The original frozen 16 PE sandbox `build/pe16-20261108/pe16-repo` was copied excluding `.git`, build/generated output, and Scala caches. Only `BiasSramPrefetch.scala` and generated `BiasSramPrefetch.sv` changed; the two pipeline test files were added. Whole-repo comparison confirms all PE16 compute RTL, NICE RTL, firmware, TB, contract, parser, and campaign runner remain byte-identical. Actual campaign input manifests differ at exactly `rtl/perips/BiasSramPrefetch.sv`. Scala is separately pinned in `source-hashes.json`.

Formal output: `build/postflow-20261108/bias16-task0/result.json`. `source_drift=[]`, identical loaded firmware image. PE16 activity parser confirms two synchronized 8-lane engines, 1,584 paired groups, 101,376 physical MAC cycles, 1,622,016 logical MACs, and zero synchronization errors. NICE still uses the original drain8 ABI, 3,168 requests/responses/retirements, 6,633 polls, zero result MMIO reads, 3,168 POPs, and 25,344 shared writes.

Selected differences: compute-wait -4,554, writeback/shared stall -99, other -198, status polls -792. No combined batching change is included.

The copied low-cost pipeline unit passes against this sandbox as well: 32 tags, 24 reads per fill, 25 stream cycles, 25 invalidate and 25 reset boundaries, held responses, signed40 boundaries, and 768 physical clear writes. Broader exhaustive mask and Chisel tests were already run on the identical streamed bias RTL in `../bias8-logs`.

The first attempted campaign was launched from the 8 PE runner entry point. It preserved the old 16 PE source snapshot and all DUT/TB assertions but omitted the extra `pe16_activity` parser result. It passed at the same 464,340 cycles, and is preserved separately as `bias16-task0-diagnostic` with `campaign-diagnostic.log`. It is not the formal comparison. The formal campaign reran with the untouched old 16 PE runner and includes the strict PE16 marker check.

Exact formal invocation, from `build/postflow-20261108/bias16-repo`:

```bash
python3.12 -E -B tools/ppa/s3_task_campaign.py \
 --repo /home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/postflow-20261108/bias16-repo \
 --out /home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/postflow-20261108/bias16-task0 \
 --bias-kind sram --schedule bias-hw-autogroup-y32-packed16-nice-direct-window \
 --simulator verilator --cross-prefix /usr/bin/riscv64-unknown-elf- \
 --platform-clocks 150mhz --startup-profile external-reset --layers 0
```

Verilator `--assert` was enabled, with Chisel procedural assertions and original golden checking. This is 2-state development simulation with vendor SVA disabled. No synthesis, power, STA, VCS, official qualification, full12, commit, or main-tree edit was performed.
