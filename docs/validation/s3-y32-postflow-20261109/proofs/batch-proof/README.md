# Batch16 transport experiment (development evidence)

The optional `0x22` instruction uses the existing 256-bit direct path twice.
Both eight-lane snapshots and both FIFO POPs retire before the first of 16
32-bit shared-memory writes. It does not add a 512-bit path or atomic POP2.
There are 1,584 requests/completions/OITF retirements, 3,168 snapshots/POPs and
25,344 Y writes per layer. Legacy `0x20` remains unchanged.

| Physical compute | Payload | Clear | Sum | Versus stable 8 PE payload |
| --- | ---: | ---: | ---: | ---: |
| Stable 8 PE/direct | 453259 | 198403 | 651662 | 0 |
| 8 PE/batch16 | 458110 | 198403 | 656513 | +4851 |
| 16 PE/batch16 | 458110 | 198403 | 656513 | +4851 |
| New batch RTL, old 8 PE/direct firmware | 453259 | 198403 | 651662 | 0 |

All three new canonical single-layer campaigns pass golden output/transaction,
physical compute, OITF and explicit final-response checks, with source_drift=[];
clocks are 150 MHz/external-reset and Verilator --assert remains enabled.
No synthesis, area, timing, power or official qualification claim is made.

Each physical version passes the real-MAC wrapper fixture: one row, 32 bundles,
256 lanes, 16 instructions; 11-cycle bundle stall, 13-cycle commit stall,
17-cycle completion stall and an injected lane-12 write error after the second
POP. All real RNE domain endpoints and signed ties are covered. Three common
reset phases also pass. The 8 PE old direct fixture passes in the new DUT.
Python contracts pass 6 tests for 16 PE and 7 tests for 8 PE, including malformed,
missing, duplicate and undercounted markers and old-profile rejection.

Raw campaigns are siblings `batch16-task0`, `batch8-task0`, and
`batch8-legacy-task0`. Fixtures/logs are in each sandbox
`build/batch16-wrapper`; unit failure/reset coverage from the NICE agent is
`batch16-repo/build/batch16-unit`. The source-variation description for 8 PE is
`batch8-repo/batch8-source-variation.json`.

Initial 16 PE wrapper failures are retained: the old 40-poll producer guard was
shorter than pair preparation, and the old observer expected one-column-group
physical starts rather than even pair starts. The adapted final fixture uses a
bounded 200-poll guard and group += 2 only for physical 16 PE. The 8 PE guard and
logical work remain independently verified.

## Adaptive stream experiment

A separate eight-PE sandbox implements optional `0x23`: one instruction drains
1..32 groups, each as poll -> capture 8 -> POP -> write 8. The full-row firmware
issues one request per row. Per-group poll budget resets, and each eight-write
response sequence retires before the next group begins. The old `0x20` remains.
No 16-lane buffer is used in this candidate.

`stream8-task0` passes: payload **431776**, clear **198403**, total **630179**,
source_drift=[]. This saves 21483 payload/total cycles from stable 8 PE, exactly
99 rows * 31 removed instruction gaps * 7 cycles. Polls remain 5049; result
MMIO reads remain zero; 99 NICE requests/completions/OITF retirements cover 3168
bundles/POPs and 25344 golden-matched Y writes. Physical MAC counters remain
3168 starts/dones and 202752 MAC cycles (8 PE).

The new real wrapper test passes one instruction/32 groups/256 lanes, all
numeric endpoints and ties, held bundle/commit/completion, MMIO ownership and
an injected write error at output index59 (group7/lane3), aborting at 60 writes
and 8 POPs. Three common-reset phases and the old direct wrapper regression pass.
Six strict parser test methods pass, including marker presence and old-profile
rejection. These fixtures are `stream8-repo/build/stream-wrapper`.

Initial new-fixture failures are retained: the parser assumed the historical
8-PE contract exported a `pes` key (it instead exports module constant PES),
and reset setup reused drain8 rs2 so stream poll_limit decoded zero. Both were
fixed in build-only test fixtures; canonical production source stayed frozen.

`stream8-observer-contract.patch` compares the four observer/tool files against
stable main. Its hashes and source snapshots pair with the separate NICE/fw
agent patch; do not apply the batch16 and stream patches on top of each other.
