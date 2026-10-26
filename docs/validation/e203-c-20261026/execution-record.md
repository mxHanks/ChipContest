# SDD ledger — plan: docs/superpowers/plans/2026-10-26-e203-c-integration.md

User authorized execution of the C-role design and requires all commits on new branches. Main base 9d5f800; E203 base 999913e. Both new branches are feature/e203-c-integration.

Pre-flight: firmware and scoreboard share memory-map/ABI constants described by the spec; checked signed40 bias, signed48 output, group/bank addressing and completion ACK after the final write response.

Task 1: complete. E203 e36d34a pushed before main b7da551 gitlink. Original five Icarus cases PASS; real CPU 12-layer shared-memory writeback PASS (304128 outputs, 608256 word writes); independent golden corruption rejected.

Task 2: host 7/7 PASS, real12 PASS, fresh GitHub clone real1 PASS, synthetic12 PASS (304128 outputs/608256 writes), final original Chisel suite 11/11 PASS. All process identities and full logs retained under build/e203.

Task 3: independent read-only reviewer completed. Found response retirement bug; new outstanding-response assertion reproduced RED at cycle ~4544, then independently clear rsp_valid on response handshake. Full positive runs repeated after correction. Doctor/build-cache/source-identity issues treated as required portable-handoff corrections: missing-simulator and stale-recipe tests RED→GREEN, baseline actual input/RTL hashes recorded.

Original Chisel baseline failed WeightBankArrayTest because its stimulus kept loadWen high while asserting ren; corrected only stimulus (0474121). Targeted original test GREEN; final original 11-test suite 11/11 GREEN. No calculation RTL changed.

SDK Legacy: original Ubuntu GCC command fails on ISA spelling and missing Newlib. Kept upstream source unchanged; verified publisher SHA for complete xPack 15.2.0-1 and rebuilt SDK Hello World with explicit CSR ISA, exit0. New C firmware remains freestanding on Ubuntu GCC; official SDK/platform migration is pending actual materials.

No deferred code-review issues. Official macro binding, formal 150 MHz/PPA and dataset accuracy are outside C's development evidence and remain explicitly unclaimed.

Task 2: complete. Task 3: complete. Fresh GitHub clone PASS; all review fixes verified; evidence bundled in docs/validation/e203-c-20261026. No new simulation or source changes after final checks.
