# Direct stream8 NICE validation

Only the isolated sandbox NICE RTL, firmware and these independent unit fixtures
were modified by this task. The source is frozen; no synthesis or SoC simulation
was run by this task. The root and observer own real-MAC / whole-SoC validation.

New direct-only instruction: opcode `0x7b`, funct3 `7`, funct7 `0x23`.
`rs2` packs starting eight-lane group `[4:0]`, count-minus-one `[9:5]`, nonzero
per-group status-response poll limit `[31:10]`. Count encoding covers 1..32;
zero-count is not representable. Group plus count must fit one 32-group row.
`rs1` is 32-byte aligned, row offset must equal `group*32`, and the complete
span is inside `[0xa0020000, 0xa0038c00)`. New descriptor/span errors use code9;
frozen codes1..8 and drain8 funct7 `0x20` retain their semantics.

Each group: real status poll -> atomic eight-word direct snapshot -> POP on the
following edge -> eight ordered 32-bit shared writes, each waiting for its own
response. The final response of the current group advances destination/group
and reloads its poll budget. Only the final group's final response produces one
instruction completion. The existing eight snapshot words and 256-bit transport
are reused; claim stays low throughout the eight writes. Any first failure
aborts the whole task; post-POP partial writes cannot be retried safely.

Run `python3.12 -E -B build/stream8-unit/run-tests.py` from this sandbox.
Exact commands and source SHA256 are in `test-commands.json`; corresponding
`*-compile.log` and `*-simulation.log` retain raw outputs.

```
NICE_STREAM8_PASS cases=118 success_counts=32 status_abort_groups=32 postpop_write_errors=24 resets=14
NICE_STREAM8_DISABLED_PASS compile_time_enable=0 no_side_effect=1
NICE_DIRECT_ERRORS_PASS cases=19 bus_error_positions=9 direct_status_errors=2 commit_error=1 shared_error_lanes=8 resets=4
```

Coverage includes every count1..32, first-error abort at every group0..31,
second/middle/final group status/bundle/commit errors and all eight shared-write
error positions in each, per-group poll budget restart, descriptor/row/span
validation, last valid destination/group, runtime and compile-time capability
rejection, stable direct bundles/commands/completion under stalls, claim release,
reset in each stream-reachable state (first and second group), and unchanged
legacy drain8 odd-group behavior without the new row-offset constraint.
No force or preloaded golden RTL state is used. This is interface-level unit
evidence; the independent SoC run supplies real accelerator data.

`firmware-compatibility.json` retains exact compiler commands and binary hashes.
New macro absent: loaded binary is identical to original main direct firmware,
SHA256 `dab9774da00f34688002d60931ec4128650bd7f92002e48d5ae86a3fb510feda`, 710 bytes.
With `XU_NICE_DRAINN=1`, the loaded binary is 692 bytes, SHA256
`c8acc6261a896e321b5f5d6eb80fbfcf7c0b2796dc93293455b4c6b04d544951`.
Disassembly shows one `0x23` call per row followed by fence and immediate nonzero
return check. Firmware rejects poll limits above 22 bits before touching MMIO.

There is no PPA or official-qualification claim in these unit results.
