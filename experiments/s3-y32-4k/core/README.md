# Local 64 PE core verification

`LinearTileDmaCore` computes up to eight rows across eight output columns. All
eight engines share the original eight logical weight banks (sixteen
1024×16 physical memories) and one bias memory. There are two 8×64×16-bit X
sets and two 8×8×48-bit result slots. This directory is experimental; it does
not change the published CPU or default accelerator path.

## Verified local results

Generated source: `build/parallel4k-20261110/core-generated-r1`.
Compile and initial receipt: `build/parallel4k-20261110/core-screen-r1/receipt.json`.
Extended receipt: `build/parallel4k-20261110/core-matrix-r1/receipt.json`.

The initial four real Verilator cases pass:

| Valid rows | Consumer stall edges per eight-result bundle | 99-row active cycles | First X load cycles | Exact raw48 outputs |
|---|---:|---:|---:|---:|
| 8 | 0 | 28,751 | 256 | 25,344 |
| 8 | 31 | 102,624 | 256 | 25,344 |
| 8 | 255 | 812,256 | 256 | 25,344 |
| 1 | 0 | 218,295 | 32 | 25,344 |

The extended matrix reuses the identity-pinned compiled executable. All twelve
distinct layers pass, totaling 304,128 exact raw48 outputs; all have 28,751
active cycles in eight-row mode. Six further complete 99-row cases with
validRows=2..7 and seven consumer stall edges per bundle pass. The matrix has
18 cases and 456,192 primary raw48 output comparisons. Its C++ RNE reference
also matches all supplied Y32 vectors. This is not an RTL Y32 quantizer test.

Each case additionally checks 2,048 signed endpoint results, 2,048 reset recovery
results, 2,048 dirty pre-clear results, and 2,048 post-clear zero results. Reset
and abort each cover computation, stalled row zero, and stalled row one. An
aborted clear must not report completion. Backpressure holds all result values
and row/group descriptors stable until POP.

The read-only physical observer verifies every required clear address exactly
once: 16,384 weight words, 768 physical bias words, and 1,024 X registers. It
also checks 64 accumulators, 64 engine result registers, 128 FIFO payload
registers, and 16 bias-cache registers at clear completion. The dedicated
dirty test first fills all these payloads through public load/compute ports.
Each completed clear takes 1,027 observed module clock edges. Each full
eight-row task launches 416 groups and performs 26,624 weight-array reads and
MAC steps per active engine; the 99th-row tile enables three rows.

The synthetic module driver spends 6,144 edges loading W/bias. Its combined
clear + parameter load + first X load + computation/consumption window is
36,178 edges in the unstalled case. This uses a C++ sink and direct public core
ports; it is **not** a DMA, CPU, shared-fabric, or end-to-end throughput result.
There is no area or achievable-clock claim here.

## Integration contract

- Capture `validRows` (1..8) and `xRunSet` on START; the tail uses three rows.
- `wLoadBank` is only 0 or 4, loading four successive signed16 values per edge.
- A packed X load must use even `xLoadAddr`; low/high update k and k+1.
- The original 32-bit X-slot layout gives a 64-bit response with useful signed16
  values at bits 15:0 and 47:32, not bits 31:16.
- X may load only the inactive set while computation is active.
- Bias host input remains owned until its response, including its three
  physical 16-bit writes. Memory-read retirement alone is insufficient.
- Output POP retires one row's eight raw48 values. A group slot remains owned
  until every valid row is popped. Group indices advance from 0 through 31;
  row indices advance from 0 through validRows-1 within each group.
- The parent DMA must convert raw48 to Y32 using the original signed RNE
  semantics and wait for all output write responses before task completion.
- Abort discards ownership and work; a subsequent physical clear is required
  before relying on zero storage contents.

## Reproduction

From the repository root:

```sh
python3 experiments/s3-y32-4k/core/run_core.py \
  --generated build/parallel4k-20261110/core-generated-r1 \
  --vectors build/timing-opt-20261109/publication/cpu-full12-namespaced-r1/vectors/layer_00 \
  --out build/parallel4k-20261110/core-screen-NEW

python3 experiments/s3-y32-4k/core/run_core_matrix.py \
  --screen build/parallel4k-20261110/core-screen-r1 \
  --vectors build/timing-opt-20261109/publication/cpu-full12-namespaced-r1/vectors \
  --out build/parallel4k-20261110/core-matrix-NEW
```

Output directories must be new. Receipts bind the generated RTL, Scala source,
driver, observer, vector files, executable, exact commands, and raw outputs.
