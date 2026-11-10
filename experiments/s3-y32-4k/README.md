# Local 64 PE / true64 experiment

This is an isolated experimental candidate, not the published v1 handoff.
Parent base `655713b304597ca5b2810a0940ac3f1850072d63`, E203 base
`45e61b6101ad6f0aaa7583098294ffb1550f1f2d`; candidate uses both
`XU_MATRIX_DMA` and `XU_MATRIX_DMA64`. Without the new define, the legacy
module, 32-bit external interface and default behavior remain available.

The user changed execution order on 2026-11-10: use local simulation first;
no exploration synthesis. Measure bottlenecks and freeze a final candidate
before concentrated area/STA work. Stop new experiments at 23:59 Shanghai.
All frequencies in cycle reports remain assumed150MHz until actual STA passes.
The official eligibility of a widened/rebanked shared-memory endpoint is still
unverified; local correctness cannot settle platform eligibility.

## Architecture

Eight rows share eight logical W banks, sixteen existing1024x16 macros and
one bias macro.64 original signed16 MACs retain signed48 accumulation and
RNE(acc/512) Y32. Tail tile contains three valid rows. Two X sets provide
2KiB; two raw48 result slots provide768B. DMA adds a256-bit Y snapshot,
40-bit bias staging and64-bit stalled-request payload, plus address/control
metadata. No W/bias or shared-memory capacity is added.

The true512KiB shared endpoint uses64 depth banks of four1024x16 macros
(256 total). A DMA beat accesses four lanes on the same edge. CPU32 retains
selected-half semantics; its LSU, BIU and original outstanding controls are
unchanged. Each new peripheral arbiter keeps one globally ordered request,
allows retirement/replacement on one edge, and locks a stalled offer.

DMA has one external in-flight request. Bias reads/three-word physical commits
run while W words are fetched. Each64-bit W beat writes four existing banks;
X's original32-bit slot layout is preserved, loading two low16 values from
bits15:0 and47:32. Four64-bit writes retire one eight-Y32 snapshot.
Next-tile X loading overlaps computation and gives way to Y retirement.

## MMIO additions and compatibility

The base remains0x10042300 and ID remains0x444d4131. Existing clear/status,
address and counter offsets are retained. CTRL=1 performs physical clear;
CTRL=2 uses one valid row; CTRL=0x802 selects up to eight valid rows. This
candidate requires8-byte-aligned tensor addresses. CTRL=0x102 belongs to the
legacy dual-row module; use the old build for that ABI.

CAPABILITY at+0x4c reads0x00084001: bits23:16=maxrows8,
bits15:8=memorywidth64, bit0=original X32-slot source layout. Source traffic
per task:4096W+256bias+3168X=7520 reads;12672 paired-Y writes;3168 output
pops. These are expected counts, not measurements.

CLEAR does real writes: sixteen W macro lanes in parallel for1024 addresses,
sixteen X row buffers for64 logical addresses, the required768 physical bias
addresses, caches/ACC/results/FIFO and DMA assembly state. clear_done waits
for the core clear completion. It never substitutes valid-bit invalidation.
First bus/bias error cancels new work, aborts the core, and drains accepted or
already-promised requests before returning idle. Completion waits for the
last output response and no pending/locked request. Reset is common across
the tested peripheral/fabric path.

## Evidence boundaries

`core/` verifies generated core raw48 results against independent vectors;
its C++ RNE calculation is not a test of the RTL DMA quantizer.
`fabric/` tests actual arbiter and256-macro functional endpoint.
`dma-test/` measures the full peripheral path without a CPU.
`validation/` boots the actual CPU, publicly transfers all fixture data,
observes physical clear read-only and verifies every Y32 through real shared
transactions. Program ITCM preload is explicitly the established boot-load
exception; no tensor/result backdoor is allowed.

Only the same frozen source's complete12-task CPU evidence can establish the
cycle target. Full12 principal must be<=450000 cycles, each<=37500; gap and
CPU synchronization are separately reported. Area<=2.25mm2, actual150MHz STA
and formal platform eligibility remain independent final acceptance items.

The clear-write counter at+0x38 counts W/X writes only (17,408). The
read-only physical observer separately verifies768 bias writes, for18,176
required physical16-bit writes/task. Do not label the register as totalclear.
