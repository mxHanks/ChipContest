# Final production GPIO / CPU validation

This harness accepts only the final sealed N2/PW1, four-request DMA, storage21
PPA input (`sysbus32-dma4-storage-sram-374-final`). It checks the entire sealed
source SET, compile order, bytes and production defines. No old storage overlay
or `XU_SYSBUS_TEST_LOADER` is accepted. The generic macro model is simulation
only; it does not establish vendor SRAM timing, area, mapped equivalence or power.

Tensor data enter the existing GPIO pads. The unchanged CPU reads GPIO/APB and
writes shared SRAM through its original LSU/BIU/SystemBus. Firmware is loaded
only into physical ITCM. Each of 15,040 GPIO word ACKs must follow its shared
write response; each task poisons Y before real hardware clear, writes all
25,344 Y32 results and reads all of them back through the CPU after DONE/fence.
A complete warmup establishes publicly dirtied W, bias, X and result storage.

The read-only pin observer enumerates and clears W16, bias1, X16 and result21
physical macros: 55,040 actual 16-bit writes (bias logical aperture 768).
The observer holds all 336 bits of result macro Q until the final scalar in
that row retires. The TB keeps its own four-slot kind/index ledger, derived
from accepted public addresses, and checks all 40,384 ordered responses and
read data independently of the DUT queue. All four hardware metadata slots,
assembly and ownership state must clear. Final Y index25343 must retire before
DONE. Actual generic leaf paths, grouped by owner, must count 374 macros.

Run the single-task build and simulation (one build CPU):

```bash
python3 -u -B experiments/s3-y32-final/validation/launch.py \
  --state-dir build/s3-y32-final/validation/gpio-task0-r2-supervisor -- \
  --out build/s3-y32-final/validation/gpio-task0-r2 \
  --vectors /home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/compliant32-20261113/numeric/public-validation-600-evaluation-r1/vectors \
  --ppa-package build/s3-y32-final/ppa/production-r1 \
  --tasks 1 --rows 8 --warmup --jobs 1
```

After it passes, serially replay the identical simulator, firmware and source
for complete12 and the independent first-load / first-DMA wait31 cases:

```bash
python3 -u -B experiments/s3-y32-final/validation/launch.py --followups \
  --state-dir build/s3-y32-final/validation/gpio-followups-r1-supervisor -- \
  --base build/s3-y32-final/validation/gpio-task0-r2 \
  --vectors /home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/compliant32-20261113/numeric/public-validation-600-evaluation-r1/vectors \
  --out build/s3-y32-final/validation/gpio-followups-r1
```

Every output directory is new. The supervisor records live PIDs and never
retries. A timeout or stale tool observation is not permission to restart a
live worker. The selected schema is `s3-final-production-gpio-cpu-v1`.

Per-task windows report GPIO first input through final Y response and clear
through final Y. The checker also reports every inter-task gap, the continuous
12-task GPIO-first-input through final-Y span, and the conservative campaign
span including clear and gaps. Inter-task CPU readback, poison and protocol
work is never silently dropped from the campaign value. All tasks/s figures
are conversions at assumed 150 MHz until the same map passes STA.

Published independent GPIO374 complete12 evidence and exact timing windows: [report](../../../docs/s3-y32-final-gpio-independent-validation.md). This is separate from the historical1064 N3 candidate.
