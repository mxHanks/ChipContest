# DMA64 through the real local shared-memory interface

This harness isolates the experimental DMA from CPU firmware while retaining
the actual `xu_dma64_shared_arb`, `xu_shared_icb_sram64`, and all 256 physical
1024×16 memory instances in the shared endpoint. The macro model is the
repository's **generic functional model**, not a vendor timing or power model.

All X, W, bias, and poisoned Y words enter through the arbiter's public CPU32
port. Every Y32 result is read back through that same port after completion.
The checker does not access or write a DUT memory array. Configuration accesses
are direct MMIO transactions to the DMA module. No host payload request occurs
while the DMA is busy. Therefore this measures DMA/fabric behavior, not CPU
instruction costs or official platform eligibility.

## Cases

- A complete 99×64 by 64×256 task, with every Y32 checked against both the
  supplied vector and an independently calculated signed16/40-bit-bias RNE oracle.
- Twelve complete, distinct layer vectors in the same simulation instance;
  each task performs hardware clear and reloads its own parameters.
- A first read-response error and first write-response error. The whole task
  aborts, drains, reports error, never reports DONE, and does not retry.
- Reset in weight/bias loading, X/computation scheduling, and output traffic;
  ownership clears and no delayed completion appears.
- Sustained response backpressure, with the real endpoint holding its response.
- A one-row control using the same wide transport and shared memories.
- A 97-edge hold on the final Y write response. BUSY must stay asserted and
  DONE must remain low throughout the hold.

Each successful task must accept **and retire** exactly 20,192 DMA64 requests:
7,520 reads (4,096 W, 256 bias, 3,168 X) and 12,672 Y writes. It must pop 3,168
eight-result bundles. Eight-row mode must perform 26,624 MAC steps per active
engine; one-row mode must perform 202,752. No completion is accepted with an
outstanding request, locked offer, or active core.

## First measured candidate

R1 evidence: `build/parallel4k-20261110/dma-screen-r1`.
Its frozen source was byte-for-byte checked against the original compilation
identity before the root's later error-classification fix. The older evidence
is retained. **R2 is complete PASS**, binds that fix, and adds the final-Y hold
test. Its authoritative receipt is
`build/parallel4k-20261110/dma-screen-r2/receipt.json`; all source/input and output
hashes were rechecked after completion, with no source drift. The tested
experimental DMA file also matches the production candidate copy byte-for-byte.

R1 and R2 full12 each verify all **304,128 RTL Y32 outputs** and report:

| Metric | Cycles |
|---|---:|
| Twelve-task payload | 416,593 |
| Twelve-task clear CSR count | 12,312 |
| Sum of payload and clear CSR counts | 428,905 |
| Typical task W/bias phase | 5,079 |
| Typical task RUN phase | 29,637 |
| Typical task payload + clear CSR counts | 35,742 |

The first task differs by one endpoint-throttle phase cycle. This corresponds
to about **4,196.73 task/s at an assumed 150 MHz**. It is a module-level result;
CPU overhead, gaps, and actual clear-to-completion measurement must be added by
the CPU harness. Achievable 150 MHz, area, and formal eligibility remain untested.

The clear CSR counts 1,026 state-CLEAR edges. The separate core physical
observer counts 1,027 inclusive edges from clearFire through observed clearDone.
Keep these measurement conventions distinct; the CPU observer determines the
end-to-end clear interval.

W/bias transport is close to the real channel limit: 4,352 wide reads at six
accepted beats per seven cycles need about 5,077 cycles, versus 5,079 measured.
RUN is 886 cycles longer than the core's 28,751-cycle unstalled module case.

R1 periodic response stalls pass with 44,746 module cycles. The one-row control
passes with 224,995 module cycles. Error/reset cases also pass. These are
correctness stress cases and do not set the throughput acceptance number.
R2 repeats these results. Its final-Y response hold lasts exactly 97 edges,
keeps completion suppressed, and increases the task from 35,743 to 35,840
cycles, after which all 25,344 output words still match.

The bounded R3 extension closes post-reset task-recovery coverage without
changing or rebuilding RTL. It links a new driver to the read-only R2 compiled
model archive. Each of three resets (W/bias, active computation, and output)
actually cancels an accepted, unretired transaction. The fixture then loads a
different layer through public CPU32 transactions, performs a new physical
clear, and completes a fresh full task. All three fresh tasks accept and retire
20,192 new DMA transactions and return 25,344 correct Y32 words each. All
**76,032 actual post-reset readback words** are retained as `.actual-y32.mem`
files and independently compared with the new layer's golden vectors.

R3 evidence is `build/parallel4k-20261110/dma-reset-recovery-r3/receipt.json`.
Its recorded compile and run commands reproduce the bounded extension using
`dma64_reset_recovery.cpp` and the frozen R2 helper/model. R2 receipts, binaries,
and source snapshots remain unchanged.

## Reproduce

From the repository root, before the authorized experiment cutoff:

```sh
python3 experiments/s3-y32-4k/dma-test/run_dma.py \
  --vectors build/timing-opt-20261109/publication/cpu-full12-namespaced-r1/vectors \
  --generated build/parallel4k-20261110/core-generated-r1 \
  --out build/parallel4k-20261110/dma-screen-NEW
```

The output directory must be new. The runner snapshots the source, uses two
local build jobs, records exact commands and identities, and preserves failed
logs. Its default cutoff is November 10, 2026, 23:59 Asia/Shanghai. A later
authorized campaign needs its own explicit `--deadline-utc` argument.

The core's separate read-only all-address clear observer and numeric tests are
documented in `../core/README.md`. This DMA harness checks clear counters and
zero ownership; it does not duplicate that physical address observer.
