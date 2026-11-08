# NICE batch16 isolated validation

Source is frozen for this experiment. No CPU pass-through, wrapper, bus width,
LSU configuration, or synthesis changes were made by this task.

- New `funct7=0x22`, opcode `0x7b`, funct3 `7`; requires direct transport.
- `rs1` must be 64-byte aligned in `[0xa0020000, 0xa0038bc0]`.
- `rs2[4:0]` is an even 8-lane group in `0..30`; `rs2[31:5]` is the nonzero
  per-group retired-response polling limit, reset before the second group.
- First 8-lane snapshot and POP, one full claim-low edge, second real status poll,
  second snapshot and POP, then sixteen shared writes. First failure aborts.
- Errors remain codes 1..8; completion stays stable until accepted. A failure
  after either POP must abort the task; retry is unsafe.
- Added upper eight snapshot words, two mode bits and the saved poll limit.
  Existing 256-bit transport, one-POP commit interface, and 32-bit shared writes remain.

Run `python3.12 -E -B build/batch16-unit/run-tests.py` from this sandbox.
Exact commands and source hashes are in `test-commands.json`; raw outputs are
`batch16-simulation.log` and `legacy-direct-simulation.log`.

`NICE_BATCH16_PASS cases=41 success16=2 write_error_lanes=16 second_group_failures_no_write=7 resets=11`

Coverage includes invalid instruction/capability, both alignment bits, lower/upper
range, odd group, zero limit, timeout, status/bundle row/group errors at both
stages, commit error at both stages, each of sixteen post-POP write errors,
held direct valid/commit, command and response backpressure, held completion,
per-group poll-budget reset, full claim gap, last legal span/group,
legacy odd-group drain8, and reset in every state reachable by drain16.
Seven second-group failures independently assert zero Y writes.
Every write checks exact snapshot data; changing the second bundle also checks
that the first eight words were preserved. The fixture uses interface injection,
not force, and is complemented by the root's real-MAC wrapper/SoC run.

The existing direct drain8 errors fixture also passes all 19 cases unchanged.

`firmware-compatibility.json` contains exact cross-compiler commands. Old main
firmware and new firmware with the new macro absent have identical loaded binary:

`dab9774da00f34688002d60931ec4128650bd7f92002e48d5ae86a3fb510feda` (710 bytes).

With `XU_NICE_DRAIN16=1`, the custom instruction encoding is 0x22, group loop advances by 2, and the immediately following fence and nonzero-code abort remain in disassembly.

No PPA or official-qualification claim follows from these unit simulations.
