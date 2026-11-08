# S3-Y32 accelerator → NICE direct result prototype

This is a measured, opt-in internal result transport prototype. It preserves the
`custom3/funct3=7/funct7=0x20` drain8 instruction, destination checks, error codes
1–8, nonzero poll-limit requirement, response backpressure, and completion after
the last successful shared-Y response. It does not modify E203 LSU/BIU logic,
in-flight configuration, or CPU control. CPU/top changes are pass-through ports.
No synthesis, mapped timing/area, energy, VCS qualification, or official score is
claimed.

## Selection and compatibility

`accel_icb_slave.DIRECT_ENABLE` is an explicit hardware parameter, default 0 for
standalone instantiations. The SoC's peripheral instantiation sets it to 1.
The additive, independent registers are:

| Offset | Read | Write |
| --- | --- | --- |
| `0x0f0` DIRECT_CAP | `0x59440001` when hardware supports it; otherwise 0 | No mode effect |
| `0x0f4` DIRECT_CTRL | Current enable in bit 0 | Full-word 0 or 1, only while the accelerator and direct adapter are idle; other writes return ICB error |

The mode resets to **disabled**. All old capability words remain exact. Existing
MMIO/read-pop remains available; disable DIRECT_CTRL or parameterize the hardware
off to use the old NICE transport. MMIO can consume results when no direct claim
is active. New result-window accesses and explicit POPs accepted during a direct
claim return ICB errors; already-accepted MMIO POP responses retire before a
direct snapshot may start. There is no simultaneous MMIO/direct POP.

The separate schedule is
`bias-hw-autogroup-y32-packed16-nice-direct-window`. It adds only the firmware
macro `XU_NICE_DIRECT=1`, probes DIRECT_CAP and writes DIRECT_CTRL **inside the
measurement window after first_w is read**. It adds one measured MMIO write;
old schedules' macro lists, contracts and load images do not change.

## Interface and ordering

The seam carries capability, claim, valid/ready, one atomic 256-bit payload and
32-bit captured ROW_STATUS, followed by a commit/ready/error handshake. All eight
signed-Y32 lanes belong to one FIFO head/group.

1. NICE issues and retires real LSU `ROW_STATUS` reads exactly as before. Only
   retired status responses consume `polls_left`. Empty responses may repeat.
2. Once a valid head matches the expected group, NICE claims the direct
   adapter. The wrapper excludes competing result/POP commands and captures the
   current group/status. A stale or missing head is returned as an error instead
   of silently changing the expected group.
3. The wrapper captures one lane per clock for eight clocks. A single selected
   `y32_rne` datapath is shared with MMIO conversion. Only the complete atomic
   bundle is published. Valid, payload, and metadata remain stable under
   backpressure.
4. NICE rechecks active/valid/group and captures all eight lanes into its
   existing snapshot registers. It offers commit **on the following edge**, so
   the FIFO cannot POP at bundle acceptance. The wrapper rechecks head ownership
   before the commit edge produces exactly one POP.
5. NICE releases the claim and issues exactly eight shared-Y writes through the
   unchanged LSU. Each next write waits for its predecessor's response.
   Completion appears only after the last response. Any error ends the entire
   instruction/task; a post-POP partial write is never retried.

A minimum successful group therefore uses **9 LSU transactions**: one status
read and eight Y writes, compared with read-pop's 17. It still performs at least
one status read; this prototype does not remove or reinterpret polling.
`poll_limit` is neither a cycle deadline nor a direct-handshake timeout. A
stalled internal producer/commit, like a permanently stalled ICB request, can
hold the instruction indefinitely. All injected direct stalls exceed the poll
budget in tests without changing that budget's meaning.

## Clocks and reset

The real hierarchy is `subsys_main.hfclk` → peripheral `clk` → accelerator FIFO,
and `subsys_main.hfclk` → CPU `clk` → `clk_aon`, where `e203_clk_ctrl` assigns
`clk_aon = clk`. There is no CDC in this connection.

Both CPU `core_rst_n` and peripheral `bus_rst_n` originate from `main_rst_n`.
The wrapper uses bus_rst_n; NICE uses the existing CPU `rst_aon`, which asserts
from the same reset and releases after synchronization. The direct source mode
and ownership reset to disabled/idle, and NICE cannot claim before its later
reset release. This interface is valid only with this common assertion/same
clock arrangement; wiring it to an independently clocked/reset accelerator
would require an explicit CDC/reset protocol.

Physical SRAM/FIFO-payload clearing policy remains the existing campaign's
`REVIEW_PENDING`/`UNPROVEN` policy. Resetting the new direct snapshot registers
is not a claim that existing physical payload storage was cleared.

## Cost and timing tradeoff

Sequential conversion avoids eight parallel 48→32-bit rounding datapaths, at the
cost of eight local capture clocks. It adds a 256-bit source snapshot, captured
status, small ownership state/counter/control registers, a lane input mux, and
wide internal wiring. NICE reuses its existing eight snapshot registers. The
common RNE expression is structurally shared in RTL, but post-synthesis mapping,
area, critical path, clock load and energy remain unmeasured. A one-clock
8-RNE bundle was deliberately not implemented without those measurements.

## Evidence and limits

`tests/e203/test_direct_wrapper.py` runs Icarus with real uploaded W/X/bias and
real MAC results for 32 groups × 8 lanes, including each legal domain endpoint
32 times, 75 positive/75 negative ties and 75 even/75 odd quotient ties. It compares a separate integer
sign/magnitude RNE oracle, stalls bundle/commit/completion, checks three MMIO
ownership errors, and verifies first-error abort. Separate direct-interface
injection covers all frozen error codes, status/group errors, commit errors,
all 8 shared-write error lanes, and reset in held NICE states. Three real-wrapper
runs reset during capture, held bundle, and owned/held commit, verifying the mode
returns to disabled with no stale bundle or POP. No force or golden preload is
used. The old read-pop test still covers all 17 bus error positions and all 32
groups.

The SoC observer retains every old schedule's exact checks. The new profile
additionally requires 3168 atomic snapshots, 25344 direct lanes, 3168 direct
POPs, zero result MMIO reads, and 25344 shared-Y writes; each bundle and each
NICE snapshot is checked against the numerical reference. Real LSU/endpoints,
OITF/rd writeback, command/completion stability and final-response ordering stay
observed. Result writeback phase begins with a real direct claim in the new
profile, analogous to the first result MMIO read in the old profile; positive
compute/writeback overlap is still required.

The first two native runs intentionally remain failed evidence: their payload
was correct but the original phase observer only started writeback at MMIO
result reads, leaving direct overlap at zero. A diagnostic run proved
rows=99, POPs=3168, produced=retired=32, FIFO empty, bundles=3168 and
logical lanes=25344; the new-profile phase definition corrected this observer
omission without changing RTL or performance cycles.

The corrected single-layer run, `direct-task0-phase`, is
`DEVELOPMENT_PASS_POLICY_PENDING`: 453259 measured cycles, 5049 real status
polls, 0 result reads, 12330 MMIO writes, 15040 shared reads and 25344 shared
writes. Positive compute/writeback overlap is 158103 cycles. Conditions are
Verilator `--assert`, 150 MHz HF/32.768 kHz LF stimulus, external pad double
reset, physical parameter preclear, frozen layer 0. This is development evidence,
not STA or a qualified score. Full-12 evidence is collected separately in
`direct-full12` by a fresh native process per layer.

`direct-proof/legacy-compatibility.json` records equality for all 336 old
schedule/optimization/experiment macro/contract/simulator-argument combinations
and six exact old read-pop load images (3 optimization levels × 2 experiments).
The original route test requires unavailable VCS; a separate Verilator run with
vendor SVA enabled passes its 1030 requests/29 commands, as two-state evidence.

Old frozen read-pop firmware was also run on the new direct-capable SoC binary
with DIRECT_CTRL reset-disabled and the unchanged read-pop TB profile. Its
single-layer run in `direct-legacy-task0` passes every old exact counter at
564118 measured cycles, identical to the baseline's layer 0. The reused binary
and frozen firmware image hashes are saved in that result.
