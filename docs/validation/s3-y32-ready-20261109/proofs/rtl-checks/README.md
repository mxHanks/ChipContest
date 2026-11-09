# READY drainN RTL limited validation

All changes are confined to `../prototype-repo`. The selected production tree remains unchanged. No synthesis, EDA session, commit, or push was performed.

## Interface and ordering

New `custom3/funct3=7/funct7=0x24` accepts the same destination/group/count descriptor as `0x23`, with a 22-bit nonzero **per-group READY_WAIT edge budget**. `0x20` and `0x23` retain their original retired-status-response poll budgets and state transitions.

The existing `xu_direct_status` wire advertises bit31 only when direct support is compiled and enabled, and claim is low. Its low31 bits then report live row metadata. With claim high, the existing locked metadata is exposed unchanged. `0x24` checks capability at acceptance and every READY_WAIT edge. Capability loss returns error1. With valid=0 it waits, including the STARTROW activation interval. With valid=1, inactive returns7, wrong group returns6; correct ready takes precedence over timeout5 on the last budget edge.

READY_WAIT never claims, POPs, or emits an ICB command. A ready observation enters the unchanged wrapper capture, NICE snapshot, next-edge POP, and eight strictly serial writes. Every previous write response retires before a next write command is offered. Group-tail completion reloads the entire ready budget. Final completion waits for the final write response. Errors abort rather than retry a partially POPped group.

## Evidence

- `ready-final/` and `ready-final-console.log`: 418 unit cases, all counts1..32; all32 first-error positions for inactive-ready/wrong-group/timeout; all256 group/lane write-error positions; eight capability-loss cases;12 unit resets. Separate compile-time NICE and wrapper disable checks reject the new operation without side effects.
- The same directory contains real-MAC 32-group/256-lane Y32 oracle checks, signed full-domain endpoints and RNE ties, bundle/commit/command/response/completion stalls, three reset phases, zero status/result MMIO reads, and STARTROW-response-before-NICE coverage.
- `older-pop-race.log`: a previously accepted MMIO POP response is held while READY observes a live head; claim waits for that POP response to retire, captures the new group metadata, then returns error6 with zero direct POPs and zero Y writes.
- `old-stream-run1/`: original0x23 118-case regression, real MAC wrapper and three reset phases passed. This run preceded a comment-only NICE clarification; its logic is identical to the final RTL.
- `old-direct-final/`: original0x20 direct errors and real MAC wrapper/reset regression passed on final RTL.
- `old-readpop-final/`: original0x20 read-pop61-case, real MAC alias and original ABI checks passed on final RTL. Deliberately illegal range/unknown diagnostics exit nonzero as expected by that test; they are successful negative checks.
- `source-pins.json`: exact changed-source SHA256, baseline SHA256 and new test source identities.
- `ready-rtl.patch`: two-file RTL delta against selected production snapshot.
- `summary.json`: machine-readable coverage and raw control cost.
- `iverilog-version.log`, `vvp-version.log`: tool versions.

No implementation/test failure occurred in these limited runs. `ready-run1` and `ready-run2` retain earlier successful stages before the extra race/disabled-wrapper checks were added.

## Reproduction

From the prototype repo:

```bash
XU_READY_LOG_DIR=../rtl-checks/replay python3.12 -E -B -m unittest tests.e203.test_nice_ready_wrapper -v
XU_STREAM_LOG_DIR=../rtl-checks/replay-stream python3.12 -E -B -m unittest tests.e203.test_nice_stream_wrapper -v
XU_DIRECT_LOG_DIR=../rtl-checks/replay-direct python3.12 -E -B -m unittest tests.e203.test_direct_wrapper -v
XU_READ_POP_LOG_DIR=../rtl-checks/replay-readpop python3.12 -E -B -m unittest tests.e203.test_read_pop_wrapper -v
```

Raw cost: one new `ready_mode` control register bit; the four-bit state register and existing27-bit countdown/reload registers are reused. The wrapper adds a combinational live-status mux; there are no new ports or wider buses. Area, timing and power effects have not been synthesized or measured. Task-cycle benefit belongs to the separate SoC campaign and is not established by these fixtures.
