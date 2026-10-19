# FPGA evidence levels

| Level | Proves | Typical evidence | Does not prove |
|---|---|---|---|
| E0 Static | files/configuration are internally inspectable | review, lint, manifest/hygiene check | functional behavior |
| E1 Compile | intended sources elaborate/compile | compile or elaboration log, parameters/top | runtime correctness |
| E2 Functional | tested scenarios meet an oracle | self-checking unit/integration/numerical simulation | complete coverage or timing |
| E3 Synthesis | mapping/inference and estimated resources | completed synthesis/OOC run, utilization, messages | routed timing or board behavior |
| E4 Implementation | placed/routed design satisfies checked physical criteria | route status, timing min/max, DRC, methodology, constraints | software identity or board behavior |
| E5 Artifact chain | deployable outputs share an accepted build identity | BIT/XSA/ELF hashes, manifests, matching embedded BIT | that hardware ran them correctly |
| E6 Board | a named workload ran on named artifacts/hardware | programming record, raw UART/logs, repetitions, counters, correctness/performance criteria | other workloads or configurations |

Status is per claim and per level. A change can be `PASS E2`, `PASS E3`, and `NOT RUN E4–E6` without contradiction.

## Minimum timing record

Record target clock/period, WNS/TNS, WHS/THS, pulse-width metrics when applicable, route status, unconstrained internal endpoints, DRC disposition, and tool/device identity. State whether metrics are post-synthesis or post-route.

## Minimum PPA record

Record stage, device, tool version, top, clock/strategy, LUT/FF/BRAM/DSP/URAM, and power method/confidence. Compare only like-for-like reports.

## Minimum board record

Record board/device identity, tool versions, BIT/XSA/ELF hashes, input hashes, programming command/session, warm-up count, measured repetitions, raw log path/hash, expected/actual counters, correctness thresholds, failures, and determinism.

