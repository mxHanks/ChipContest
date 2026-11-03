# xu S2d: two X banks and queued rows

Independent experiment on `codex/xu-s2d-doublebuf`, from main `e930469fc2017c3d5273c8826030e2a37b8d42b8` / E203 `2b4b5dc` (S2c production bytes, including the VCS declaration-order fix). The new hardware commit is E203 `dd692c190dadafd9baa6dffe8514a3f684e7fbf5`; initial measured main is `9f1362f`, final measured main is `0ad5e047a20df59f8211cbba9ef5bb77e8baffbb`. This is a local screen, with server VCS/PPA/energy and retention still pending.

The accelerator still has eight signed16 MAC lanes, signed40 biases and signed48 results. `LinearBufferedComputeCore` contains two 64×16 X row buffers, **one** unchanged 32KiB logical W bank array and **one** dot-product engine. Selecting the X bank requires no 64-cycle row copy. It adds one 1024-bit X buffer; both remain the existing register-buffer implementation. This experiment does not claim that register-backed task storage has passed the contest SRAM qualification review.

`LinearDoubleBufferCore` retains the old manual/S2c scheduling behavior on X bank0, and adds an opt-in row-descriptor FIFO with two entries. At most two submitted rows may await final POP retirement. A submitted bank is immutable until its group31 compute result is captured; the bank becomes free at that edge, independently of result consumption. Thus the CPU may upload a future row while older results remain owned. Submission of that future row still requires the outstanding-row limit. The two 8×48 result slots are shared between modes; DB results carry row and group tags. A launch reserves a free group slot; a full FIFO stops further compute launches. There is one producer, with at most one in-flight group.

W/bias writes remain excluded throughout DB mode. The 1RW W array never reads and loads simultaneously. A row descriptor carries an X-bank bit and a 7-bit row tag; the producer emits all groups0..31 in order before advancing to the next descriptor. Only a successful explicit POP **response retirement** releases a result and, for group31, decrements outstanding rows. FIFO peek reads and accepted/stalled POP responses retain their head. Reset aborts ownership and pending response metadata without promising SRAM/data initialization. There is no partial abort command or DMA.

## Additive registers

Old capability words remain exact: `050=58550003`, `070=58530003`, `074=58500003`, `078=58410001`. Existing old schedules, windows and STARTROW behavior remain available when DB mode is off.

| Offset | Register | Contract |
| --- | --- | --- |
| `07c` | DB_CAP | RO `58440001` |
| `0d0` | DB_CTRL | Full-mask data0/1 disables/enables DB mode, only when old/new execution, descriptor/result queues and load strobes are idle. Enabling requires the full bias cache. |
| `0d4` | DB_STATUS | RO: bit0 mode; bit1 head-valid; bit2 compute-running; bits4:3 result count; bits6:5 outstanding rows; bits8:7 descriptor count; bits10:9 free-X-bank mask; bits15:11 head group; bits22:16 head row tag; bits31:23 zero. Head metadata is meaningful only when valid. |
| `0d8` | DB_X_CURSOR | Full-mask write: bank bit8 and element cursor bits6:0, 0..64. Other bits must be zero. Selected bank must be free and have no pending submit pulse. |
| `0dc` | DB_X_PACK32 | Full-mask write: two signed16 values, low half then high half. Cursor must be even and below64, bank free. Response becomes valid only after both internal write edges. Cursor advances by2. |
| `0e0` | DB_SUBMIT | Full-mask write: bank bit0, row tag bits14:8, all other bits zero. Requires enabled cache/DB, a free selected bank and room in both row limits. Submission acquires bank ownership. |
| `0e4` | DB_POP | Full-mask data1 only; requires a valid head. Releases only when this successful response retires. |
| `0e8` | DB_HEAD | RO row tag bits14:8 and group bits4:0; empty or same-edge POP retirement returns held response error. |
| `200..23c` | DB results | RO eight lanes, LO32 then zero-extended HI16, side-effect-free snapshot. Empty or same-edge POP retirement returns error. |

Invalid data/masks, busy-bank uploads, mode changes while rows remain, excess submissions and legacy operand/config writes during DB mode return errors with no state/storage effect. Old manual START while busy remains ignored. A DB_SUBMIT on the same edge as a final POP retirement sees the old outstanding count and may be rejected. A new submission on the following edge can be accepted while the previous error response retires; that response never inherits POP metadata. No duplicate POP or submission occurs under backpressure. As with old STARTROW, software must upload all64 X entries before submission; hardware does not add a per-element initialization bitmap.

## Firmware and complete-task accounting

`bias-hw-doublebuf-window` is opt-in. It uses S2b packed W upload and refreshes all W and256 biases per task. After enabling DB mode, it uploads/submits row0. Before consuming each row, it uploads/submits the next row into the alternating free bank. Every row/group head is checked against a combined tag `(row*32+group)`. All99×64 X source words stay inside the task window; no cross-task reuse or pre-window staging is added. Original signed64 shared-Y slots and ordering remain unchanged. Each group's final lane is read into two locals, POP is issued, then its two shared writes occur. DB mode is disabled after the final POP and before the final two Y writes, so both mode writes remain inside timing.

Both S2c and DB execute3168 compute groups,202752 eight-lane MAC beats,23232 shared source reads,50688 result-word MMIO reads and50688 shared-Y writes. S2c has15497 timed MMIO writes; DB has15499, including its enable/disable. Poll reads remain measured. `DB_TASK` independently requires99 accepted submits,3168 successful POP retirements, positive actual compute/X-upload and compute/writeback overlap, and empty queues/free banks/mode-off at the final shared-Y response. Six scheduling phases partition the complete inclusive first-input-request/final-Y-response window; overlap counters are not added to those phases. This local historical inclusive window is not a candidate-specific S0 formal-clear/SAIF qualification.

The initial firmware checked row and group separately and measured1,018,530 cycles, slower than the same-RTL S2c control1,013,171. That negative result is preserved. Combining the same complete tag check gave1,003,527 cycles,9,644 fewer (0.951863%); actual X/compute overlap was3618 cycles and compute/writeback overlap142227. The entire X phase was not hidden. These are local GCC14.2/Verilator5.032 layer00 numbers, not server12-layer acceptance or a score claim. See [immutable raw evidence](validation/xu-s2d-doublebuf-20261103/README.md).

## Changed Chisel and reproduction

Production Chisel changes are exactly `src/main/scala/GenerateRTL.scala` (new optional generator key), new `src/main/scala/linear/LinearBufferedComputeCore.scala` and new `src/main/scala/linear/LinearDoubleBufferCore.scala`. Existing compute, PE, controller, SRAM and bias-cache Scala files are unchanged. Generation emits two new SV files; every emitted common file matches the tracked old file byte-for-byte, and all original12 generated SV files plus `LinearAutoGroupCore.sv` stay unchanged.

```bash
scala-cli run . -M GenerateRTL -- LinearDoubleBufferCore
cp generated/LinearDoubleBufferCore/LinearBufferedComputeCore.sv third-party/e203_hbirdv2/rtl/e203/perips/
cp generated/LinearDoubleBufferCore/LinearDoubleBufferCore.sv third-party/e203_hbirdv2/rtl/e203/perips/
python3 -m unittest discover -s tests/e203 -p 'test_*.py' -v
python3 -m unittest discover -s tests/numeric -v
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator \
  --firmware-schedule bias-hw-autogroup-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out build/xu-s2d-repro-auto
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator \
  --firmware-schedule bias-hw-doublebuf-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out build/xu-s2d-repro-db
python3 docs/validation/xu-s2d-doublebuf-20261103/check-results.py
```

Use new output directories. Generated SV is copied from Chisel output; the handwritten bus wrapper adds validation, held response metadata and the packed-write adapter. The real-core Icarus test exercises four rows/all128 groups/1024 signed48 lanes, signed16/signed40 boundaries, queued-bank ownership, early free-bank upload, full-FIFO backpressure, stable stalled peeks/POP, same-edge POP/read and final-POP/submit boundaries, next-edge valid submission during old-error retirement, legacy write rejection, reset-abort and manual return. Existing S2c, scalar, packed and cached tests also run against the new wrapper.
