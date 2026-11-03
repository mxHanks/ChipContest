# xu S2c autonomous row and two-slot result FIFO

Independent experiment from main S2b `a2a1f076060c43fcefb1148edaa83c89bb1d4320` and E203 `d5faa5e8c857fa35df62a68de667bdb8a6e954f7`, on separate `codex/xu-s2c-autogroup` branches. This S2c selects the S2 proposal's autonomous-group/FIFO option; it does not implement the separate parallel packed-write option. No qualification, remote VCS, PPA, energy, score, or retention claim.

The architecture remains eight PEs, signed16 X/W, signed40 bias and signed48 result. The original W bank geometry, 1RW macros, 16,384-element capacity, X row buffer, bias cache and numerical fixtures are unchanged. W remains fully resident; no W load overlaps computation. The new Chisel `LinearAutoGroupCore` composes the existing unchanged `LinearComputeCore` and `BiasBankCache`, and adds two 8×48 result slots (768 raw data bits), pointers, counts and a producer controller. It issues groups 0..31 exactly once per row. Before each launch it requires a free slot and reserves that capacity until completion; a full FIFO prevents the next launch. The sole producer and one in-flight group cannot overrun the two slots. A consumer POP may coincide with enqueue; count updates account for both.

## Additive bus contract

The legacy, S2a and S2b words remain exactly `CAP@050=58550003`, `STREAM_CAP@070=58530003`, `PACKED_CAP@074=58500003`. Original START continues to compute one selected group. Old parameter/write-mask behavior is unchanged outside the newly requested row interval. Original result windows still show the core's last result, and all original firmware configurations remain available.

| Offset | Register | Contract |
| --- | --- | --- |
| `078` | AUTO_CAPABILITY | RO `58410001`: signature 5841, bit0 autonomous row with explicit POP FIFO |
| `0c0` | ROW_CTRL | WO STARTROW: exactly data=1, mask=1111; reads 0 |
| `0c4` | ROW_STATUS | RO snapshot, fields below; no side effects |
| `0c8` | ROW_POP | WO exactly data=1, mask=1111; reads 0; explicit response-retired FIFO release |
| `100..13c` | FIFO result window | RO eight lanes: LO32 then zero-extended HI16, same lane representation as original H2 window |

ROW_STATUS: bit0 row active; bit1 FIFO head valid; bit2 producer has completed all 32 groups; bit3 compute in flight; bits5:4 occupied slots; bits10:6 head group (retired count modulo 32); bits21:16 produced count 0..32; bits29:24 retired count 0..32; all other bits zero. Counts persist after final retirement and clear on the next STARTROW or reset. The head group is meaningful only when valid.

STARTROW requires enabled full bias cache, no manual busy/START, no prior legacy X/W strobe or stream adapter operation in flight, no active/pending row, and empty FIFO. Software must upload all W and 256 biases per task, and all 64 X entries per row before STARTROW. There is no X copy: STARTROW acquires ownership of the existing stable row and cached biases. The wrapper rejects all old/new operand, group, cache-control and operand-index writes during this interval (including the pending STARTROW pulse); rejected commands return response error and have no storage or register effect. Legacy manual START while busy remains ignored. Scratch, status W1C and read-only probes remain usable. No new row may start until the final POP response retires. There is no partial abort command; reset aborts the row, clears counts/pointers/response metadata/cache selection and discards queued results, without promising SRAM initialization.

FIFO reads are side-effect-free. Acceptance captures one word into the existing single response slot; data/error/valid remain stable under response backpressure. Empty window reads return 0 with error. FIFO ownership persists while software reads and writes previous results. POP acceptance validates the head and records metadata with its response; **only `rsp_valid && rsp_ready` for that successful response advances the head and retired count**. A blocked POP cannot release capacity or change any head word, and a failed POP cannot release anything. The final (32nd) POP retirement clears row-active. It does not alter the original manual done sticky bit. Producer-done is distinct from FIFO drained and from final shared-Y retirement.

When a new head read or POP is accepted on the same edge as an old POP response retires, that new command returns error with no extra head access. This explicitly avoids an ambiguous pre/post-retirement head. Normal E203 sequential firmware waits for each response and does not hit this boundary. Other command/response pipelining remains supported. Invalid STARTROW/POP data/masks/busy, empty POP and empty FIFO reads produce held response errors and no side effect. These new errors have no separate sticky flag.

## Firmware and measurement

Opt-in `bias-hw-autogroup-window` adds `XU_HARDWARE_AUTO_GROUP=1` and reuses S2b packed W/X loading. The three old capability probes remain exact; AUTO_CAP uses signature/required-bit inclusion. Each row starts once. For each group the CPU polls head-valid, checks its group, reads eight results and writes the original signed64 shared Y slots in the original order. Seven lanes are read/written normally; the last lane's two words are captured in two locals, POP is issued, then those last two shared writes occur. Thus every POP, including the final row/group's POP retirement, remains inside the historical first-input-read/final-Y-write-response window. There is no pre-window staging, cross-task reuse, DMA, compact Y format, or host-side output backend.

| Timed work per 99×64×256 task | S2b | S2c |
| --- | ---: | ---: |
| W writes | 8193 | 8193 |
| X writes | 3267 | 3267 |
| Bias upload/mode writes | 770 | 770 |
| Group/row control writes | 9504 | 99 STARTROW + 3168 POP = 3267 |
| Total MMIO writes | 21734 | **15497** |
| Shared reads / Y writes | 23232 / 50688 | unchanged |
| Result MMIO words | 50688 | unchanged |
| Actual core launches / done / MAC beats | 3168 / 3168 / 202752 | unchanged |
| Output elements | 25344 | unchanged |

Polling reads remain measured. The observer counts actual autonomous core launches rather than treating one STARTROW as one group. It independently requires 99 accepted row starts, 3168 successful POP response retirements, produced/retired=32 and empty inactive FIFO at task completion. AUTO_TASK additionally records actual compute/writeback overlap and FIFO-full producer wait cycles. Busy covers manual execution or autonomous launch/in-flight execution, not consumer stalls. Six software phases still partition the complete inclusive task window; they are scheduling phases and overlapping compute is separately observed.

## Generation and checks

Actual changed Chisel files: `src/main/scala/GenerateRTL.scala` (adds optional generator key), new `src/main/scala/linear/LinearAutoGroupCore.scala`; new test `src/test/scala/linear/LinearAutoGroupCoreTest.scala`. No existing compute, PE, controller, memory or cached-core Scala source changed. Running the new optional generator emits 11 common SV files byte-identical to the existing E203 files plus the new top. `LinearCachedCore.sv` is untouched, so all original 12 generated files remain byte-identical. Copy only the new top into E203, never hand-edit generated logic:

```bash
scala-cli run . -M GenerateRTL -- LinearAutoGroupCore
cp generated/LinearAutoGroupCore/LinearAutoGroupCore.sv third-party/e203_hbirdv2/rtl/e203/perips/
scala-cli test . --test-only linear.LinearAutoGroupCoreTest
python3 -m unittest discover -s tests/e203 -p 'test_*.py' -v
python3 -m unittest discover -s tests/numeric -v
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator \
  --firmware-schedule bias-hw-autogroup-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out build/s2c-real1-repro
```

Output directories must be new. Direct Icarus tests use the actual Chisel core and real SRAM RTL, checking two complete rows/all 64 groups/512 signed48 lanes with signed16 and signed40 limits, FIFO-full stalls, real compute/readback overlap, stable stalled read and POP responses, reset-abort, exact enqueue/pop conservation, head commands and a final-POP STARTROW colliding with POP retirement, immediate next-edge restart while the old error response retires without corrupting new-row metadata, cache-required/illegal/masked operations, legacy write in-flight rejection, protected old/new writes and return to manual START. Existing cached/scalar/packed tests remain intact. Chisel simulation separately tests two rows/all numeric lanes, rapid/stalled draining, persistent full backpressure, exact 32/32 counts and manual return.

Local screen and immutable artifact checks are recorded in [validation/xu-s2c-autogroup-20261103/README.md](validation/xu-s2c-autogroup-20261103/README.md).
