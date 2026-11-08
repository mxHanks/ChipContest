# Physical 16-PE single-layer observer

Modified only the experimental repository's `tests/e203/tb_accel_soc.sv`,
`tools/scripts/xu_firmware_contract.py`, and `tools/scripts/e203_soc.py`.
Firmware and the production tree were not modified by this observer work.

The generated `PairComputeCore` contains two actual `DotProductEngine`
instances, `core.engine` and `core.engineHi`, each containing its original
eight-lane `peArray`. The observer independently samples both instances'
start, init, enable, and done on every payload-window edge, failing immediately
if any corresponding control differs. Per-engine counts are retained, and
logical MAC work accumulates eight lanes from each engine's own enable.
The physical MAC-cycle count remains one count per simultaneous cycle.

The new mandatory `PE16_TASK` record has these exact single-layer constraints:

| Field | Required value |
| --- | ---: |
| pes / engines | 16 / 2 |
| physical_groups | 1584 |
| physical_mac_cycles | 101376 |
| logical_macs | 1622016 |
| lo_starts / hi_starts | 1584 / 1584 |
| lo_init / hi_init | 1584 / 1584 |
| lo_mac_fire / hi_mac_fire | 101376 / 101376 |
| lo_done / hi_done | 1584 / 1584 |
| checked_cycles | complete payload window |
| sync_errors | 0 |

The unchanged external work remains 3168 eight-result groups, 3168 NICE
requests/completions, 3168 direct snapshots/POPs, and 25344 output writes.
No numerical, response-retirement, window, row, poll, backpressure or error
checks were removed or weakened. The experimental TB intentionally accepts
only the existing NICE direct schedule. Its original firmware flags, command
ABI and external group counts are preserved.

The transaction contract now explicitly contains `pes=16`, starts/dones 1584
and `mac_fire=101376`. `e203_soc.check_performance` requires and strictly parses
the new record; missing, duplicated, malformed, wrong-profile or wrong-work
records fail. The direct `e203_soc` runner also saves parsed `pe16_activity`.
The campaign runner can call `soc.check_pe16_activity(log,native_layers,schedule)`
to include the record in its per-layer JSON; regardless, its existing
`check_performance` call already enforces this proof.

Validation before the root agent's canonical full-SoC single-layer run:

- Python 3.12 compile of both edited Python modules passed.
- Strict-parser positive case passed.
- Twelve negative cases were rejected: missing record, duplicate record,
  old 8-PE physical-cycle count, half logical MAC work, incomplete checked
  window, synchronization error, missing high-engine init, wrong PE count,
  extra field, negative field, wrong layer, and unsupported schedule.
- Generated SV hierarchy/port names were checked against the new two-engine
  core (`engine`, `engineHi`, `peArray.io_init`, `peArray.io_enable`,
  `io_start`, `io_done`).
- No synthesis, EDA compile, or long simulation was launched by this subtask.

Parser validation marker:

```text
PE16_PARSER_PASS positive=1 negative=12 physical_contract=16x101376 external_groups=3168
```
