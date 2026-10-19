# Flow routing and acceptance

Select only the rows needed for the requested outcome. Existing project commands take precedence over generic examples.

| Goal | Minimum useful stages | Acceptance evidence |
|---|---|---|
| Understand project | configuration, manifests, entry scripts, prior reports | identified part/top/clock/mode and authoritative paths |
| Review/generate automation | inspect established flow; syntax/static review | checked script plus assumptions; no claim that it ran |
| RTL compile confidence | manifest validation and elaboration/lint | intended top compiled with intended parameters/IP |
| Functional change | focused self-checking TB, then affected integration/numerical regression | scenario coverage, assertions/counters, exit status, log |
| Interface/hierarchy change | elaboration plus affected OOC or integration simulation | port/width/order/parameter compatibility and compile evidence |
| Resource estimate | synthesis or OOC synthesis | completed run, target part, utilization report |
| Timing estimate | synthesis timing is an estimate only | report labeled pre-route; no timing-signoff claim |
| Timing signoff | implementation, route, min/max timing, constraints, route status | WNS/TNS/WHS/THS/WPWS/TPWS as applicable, fully routed, no unconstrained internal endpoints |
| Bitstream/XSA | accepted implementation plus artifact generation | run status, DRC/timing disposition, hashes and source identity |
| Vitis application | matching XSA/platform/BSP/app build | processor/OS/domain, build status, ELF identity and matching XSA |
| Board signoff | program matching artifacts and run the approved workload | raw log, repeated results, counters, correctness thresholds, deterministic identity chain |

## Invalidations

- RTL behavior changes invalidate relevant simulation and downstream generated results.
- Ports, hierarchy, parameters, or manifests invalidate elaboration and affected IP/integration results.
- XDC or clock changes invalidate timing and implementation conclusions.
- target part, tool version, IP version, or implementation strategy changes invalidate prior PPA/timing comparability unless explicitly normalized.
- golden inputs, numerical mode, or tolerances change invalidate prior numerical/board correctness claims.
- XSA changes invalidate platform/BSP/application identity unless rebuilt or otherwise proven compatible.

## Result vocabulary

Use `PASS`, `FAIL`, `NOT RUN`, and `BLOCKED` with a named scope. Avoid an unqualified “works.” Distinguish behavioral simulation, synthesis estimate, implemented timing, and measured board behavior.

