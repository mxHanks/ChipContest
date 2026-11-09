# DMA candidate storage and mapping boundary

The machine-readable inventory is produced by
`experiments/s3-y32-dma-day/storage_inventory.py`. Its default comparison uses
the sealed 8 PE full12 source and the new 48-bit shared-weight core. It counts
declared clocked register widths with nonblocking assignments, walks the actual
module hierarchy, and checks 17 SRAM leaves, 8 versus 16 PEs, and 1 versus 4 X
buffers. Combinational temporaries and simulator randomization are excluded.
These are source register bits, before synthesis optimization; they are not
standard-cell area or a physical implementation.

```sh
python3 experiments/s3-y32-dma-day/storage_inventory.py --out build/dma-day-20261109/storage-inventory.json
```

| Storage | 8 PE baseline | DMA candidate | Change |
| --- | ---: | ---: | ---: |
| W physical SRAM | 16 × 1024 × 16 bits | same | 0 macros / 0 bits |
| Bias physical SRAM | 1 × 1024 × 16 bits | same | 0 macros / 0 bits |
| X register payload | 1,024 bits / 128 B | 4,096 bits / 512 B | +3,072 bits |
| Core result slots | 768 bits / 96 B | 1,536 bits / 192 B | +768 bits |
| Accumulators | 384 bits | 768 bits | +384 bits |
| Engine captured results | 384 bits | 768 bits | +384 bits |
| Two bias cache slots | 640 bits / 80 B | same | 0 bits |
| DMA output snapshot | none | 256 bits / 32 B | +256 bits |
| Peripheral arbiter state | none | 5 bits | +5 bits |

The candidate has 192 B of core results plus one 32 B output snapshot: 224 B
total result payload, below the 512 B design budget. Bias cache payload is
separate and is already included in `BiasSramPrefetch` below. The W bank count
and capacity do not increase. Physical SRAM capacity remains 278,528 bits
(34 KiB): 32 KiB W and a 2 KiB bias macro. The bias macro uses 768 physical
16-bit words for the 256 signed40 values; padding and unused macro rows do not
turn into additional logical parameters.

| Source clocked registers | Baseline bits | Candidate bits |
| --- | ---: | ---: |
| BiasSramPrefetch including its cache, metadata and sequencing | 973 | 888 |
| Engine captured results | 384 | 768 |
| Scheduler, core result slots and tags | 796 | 1,584 |
| MAC controllers | 9 | 18 |
| PE accumulators | 384 | 768 |
| SRAM wrapper rvalid registers | 17 | 17 |
| W-bank delayed macro select | 8 | 8 |
| X buffers | 1,024 | 4,096 |
| Historical MMIO/direct wrapper | 851 | replaced |
| New DMA wrapper | none | 1,182 |
| New peripheral arbiter | none | 5 |
| **Peripheral boundary total** | **4,446** | **9,334** |

Net source register change is **+4,888 bits**. The reduced generated bias
sequencer register count reflects unused host-read/response paths removed when
the new core connects a write-only host interface. Its physical SRAM and two
eight-bias cache payloads remain unchanged. The source hierarchy and individual
register widths are retained in the JSON so these totals can be recomputed.

The 1,182 DMA bits comprise 352 counter bits, 256 submitted/run descriptor bits,
34 configuration response bits, 62 W/bias sequencing and assembly bits, 42 X
scheduling bits, 293 Y scheduling/snapshot bits, 101 request ownership/locking
bits, and 42 state/status/error bits. The 256-bit snapshot is already part of
the 293-bit Y category and must not be counted again. The new master permits
one ordered outstanding request; no large transfer FIFO was introduced.

The added external master uses the existing tested shared ICB endpoint through
a new peripheral CPU/DMA arbiter and response route. CPU, original LSU/BIU
internals, original outstanding configuration and shared SRAM endpoint are
outside this inventory boundary. The DMA configuration uses the candidate
accelerator aperture at offsets 0x300–0x37f. Five new compute inputs occupy
20 bits: abort, X load/run set selection, packed-W enable and high INT16 data.

## Gated mapping experiment

`experiments/s3-y32-dma-day/synth_batch.py` freezes the exact successful CPU
full12 candidate source, sealed baseline source, functional gate, flow scripts,
tool binaries' hashes and the Nangate45 TT library. Baseline elaboration sets
`accel_icb_slave.DIRECT_ENABLE=1`. Candidate elaboration contains
`xu_matrix_dma`, the 16 PE core, and its peripheral arbiter; all public inputs
remain variable. Neither configuration specializes away the second engine.

Before processing or memory mapping, only `mem_1024x16` becomes a blackbox.
`Sram1024x16` remains normal logic. Each successful design must retain exactly
17 blackboxes with all six exact-width ports, no inferred/unmapped memories,
only library cells plus explicit metadata, and a nonempty sequential-cell
population. Mapped cell counts and Liberty areas are reconciled independently.

This boundary comparison excludes CPU and original fabric logic, the external
shared SRAM, SRAM macro area/access timing, placement, wiring and parasitics.
It can report mapped standard-cell area and unchanged macro count. It cannot
establish whole-SoC area change, the 25% whole-SoC soft budget, 150 MHz STA,
power, or official qualification. The library has no explicit area-unit
declaration; reports retain Liberty area units.

The initial batch at `build/dma-day-20261109/final-area-batch-r1` stopped before
mapping because Yosys detected a structural combinational loop in the sealed
baseline's command-ready/cache-clear handshake. The two MMIO dispatch addresses
are mutually exclusive, but this is not a proof that the physical loop can be
ignored. No RTL, assumptions, or feedback cuts are allowed to manufacture a
comparison. A single explicitly authorized `opt -full` attempt on the same
frozen RTL is recorded separately as `final-area-batch-r2`. Its result JSON is
authoritative. The bounded attempt still rejects the baseline's structural
loop. The candidate maps successfully: **66,047 standard cells**, independently
reconciled **109,388.776000 Liberty area units**, and **17 unchanged SRAM
blackboxes**. Its 56 `$scopeinfo` metadata cells contribute no logic area. The
mapped JSON, netlist, per-cell area sum, exact macro ports and source drift are
checked and retained under `final-area-batch-r2/candidate/`.

There is **no valid comparable area delta** because baseline mapping failed.
The candidate cell-only number is not whole-chip area and does not verify the
25% soft budget. R1 and R2 RTL origin/hash dictionaries are identical; only the
pre-map optimization command changed. No feedback cuts, source changes or input
assumptions were used. No STA is run by this flow.
