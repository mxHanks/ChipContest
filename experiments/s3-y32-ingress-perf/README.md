# Ordered 32-bit ingress regression

Run from the repository root:

```sh
python3 experiments/s3-y32-ingress-perf/run_ingress_regression.py
```

The implementation changes the existing `sirv_gnrl_icb_arbt` instance's owner
FIFO from one entry to four entries. Each entry contains only the selected
source ID. The 32-bit command and response data continue through the existing
`e203_subsys_mems` fabric, whose command and response FIFOs each have depth two
and whose splitter retains its original one-outstanding configuration. No
platform module, fabric parameter, CPU/LSU/BIU logic, or SRAM path is changed.

Four owners permit the existing command pipeline to accept commands before
earlier responses reach their sources. The original fabric's ready signal
continues to limit downstream storage use. Responses must remain ordered, as
required by the original ICB fabric. The owner FIFO backpressures commands at
four outstanding requests. Its cut-ready behavior is retained.

`tb_ingress32_pipeline.sv` tests production (CPU + DMA) and simulation
(CPU + DMA + loader) configurations with mixed reads/writes, changing payloads,
round-robin service, a held command when other sources arrive, four outstanding
owners, response backpressure, injected errors, simultaneous owner enqueue and
dequeue, FIFO wraparound, and joint ingress/endpoint reset followed by recovery.
The disabled production loader is held valid to ensure it cannot participate.

`tb_ingress32_fabric.sv` instantiates the unmodified platform fabric with the
same depth-two command/response buffers and depth-one splitter as production.
A saturated source issues 1,000 writes to a one-cycle endpoint. The acceptance
span must be at most 2,100 cycles; the actual optimized result is 1,997 cycles
(initial gap one, maximum gap two), versus 3,997 cycles with the frozen owner
depth of one (every gap four). Response completion spans are 2,002 and 4,000
cycles respectively. This verifies ingress service rate, not full-task
throughput or physical timing.

To reproduce the failing frozen baseline without editing the frozen tree:

```sh
python3 experiments/s3-y32-ingress-perf/run_ingress_regression.py --fabric-only \
  --ingress /path/to/frozen/xu_systembus_ingress32.v
```

Add `--allow-slow` to print the baseline measurement without enforcing the
optimized service-rate threshold. The older compliant32 ingress test explicitly
asserts that only one transaction can be outstanding and is historical; use
this regression for the pipelined implementation.

No synthesis, place/route, STA, or official qualification is claimed here.

## DMA and complete-task validation

The DMA now keeps four ordered metadata entries, containing only request kind
and index. Its accepted commands still pass through the same ingress and original
fabric. W half-word assembly, bias physical commit, X set ownership, Y packet
retirement, error drain and final DONE conditions are preserved. Metadata entries,
indices and pointers are explicitly cleared and observed.

`verify_sources.py` compares all 168 production RTL files against frozen child
`bde23ba9d06c57f6536d9992b3cd3427daccd9f8`: exactly the two scheduling files may
differ. It also requires the CPU firmware to remain byte-identical.

```sh
python3 -B experiments/s3-y32-ingress-perf/verify_sources.py
python3 -B experiments/s3-y32-ingress-perf/run_cpu.py \
  --vectors <vector-directory> --out build/ingress-perf/task0 \
  --tasks 1 --warmup --jobs 2 --load-pipeline 1
python3 -B experiments/s3-y32-ingress-perf/run_campaign.py \
  --base build/ingress-perf/task0 --vectors <vector-directory> \
  --out build/ingress-perf/campaign
```

The CPU runner uses the selected production sixteen-X-macro core. The shared and
internal SRAM adapters are identical to the frozen functional model. It preserves
physical clear of 33,536 sixteen-bit words, every source write and response, all
40,384 DMA requests/responses, 25,344 Y32 writes and full public readback. The
metadata queue is checked against an independent four-entry scoreboard. The shared
endpoint itself still permits only one outstanding request.

Only the source-loader task pipelines its requests (`--load-pipeline 1`); source
payloads, address order, total transactions and full response retirement remain
mandatory. `--load-pipeline 0` retains serialized source loading for differential
measurement. Poison writes and verification readback remain outside the task
window, exactly as in the 504.3868 baseline. File reads and packing are outside
this window, but actual input/parameter loading is fully timed.

The campaign reuses one simulator, firmware and RTL snapshot for complete twelve
tasks, first-DMA/first-loader endpoint waits of 31 cycles and serialized-loader
comparison. It independently checks the identity of the reused binary and that
multiple requests were actually in flight.

`run_dma.py` builds a separate actual-ingress/original-fabric functional model
from a sealed selected-X candidate (prepared using the existing compliant32
X-macro tooling). `run_dma_replay.py` reuses that model's pinned archive and
headers with strengthened drivers, retaining source/model/vector SHA256 evidence.
Its coverage includes complete twelve-task output, source and result errors,
command/response stalls, one-row mode, a last Y response held VALID for 97 cycles,
resets with at least two requests in flight, and seven address-targeted errors
(W low/high, bias low/high, X, first/last Y) followed by different-parameter full
recovery. This separate C++ functional model uses `--no-timing`; the CPU model
uses `--timing`. Neither represents gate-level timing.

## Measurement boundary

These are local engineering measurements using the original-SystemBus stimulus
source, matching the earlier 504.3868 tasks/s baseline. They are not qualification
of the newer GPIO-to-CPU loading environment. That environment must be remeasured
with the new RTL before making a production GPIO throughput claim.

All tasks/s conversions assume 150 MHz. A new matching synthesis/STA/area/power
run is required: the frozen candidate's old PPA identity cannot be reused for
changed RTL. X remains in the original one-INT16-per-32-bit-slot format; no
packed16-X performance claim is made.
