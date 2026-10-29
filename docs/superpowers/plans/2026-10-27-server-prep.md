# E203 Server Preparation Implementation Plan

> For agentic workers: execute inline using superpowers:executing-plans; request one final independent code review.

**Goal:** Deliver reproducible, offline-capable xu server acceptance.
**Architecture:** Reuse e203_soc.py and Git bundles, add only a stdlib integer checker and sequential acceptance entry point.
**Tech Stack:** Existing Python3, Git, RV32 GCC, Icarus/Verilator and Scala CLI.
**Spec:** docs/superpowers/specs/2026-10-27-server-prep-design.md

## Global Constraints

New branch only; no RTL/ABI or dependency-version changes. Preserve original evidence. Fail closed. No official-platform/PPA/600-sample accuracy claims.

## Review Focus

- A malformed or one-bit-wrong vector must fail before being treated as a trusted reference.
- An uninitialized submodule must not accidentally report its parent's Git commit.
- Unsupported RV32 ISA/toolchain must fail doctor despite a discoverable executable.
- A failing acceptance child process must not leave an aggregate PASS.
- Offline recovery must use the exact gitlink and preserve fixture/evidence bytes.

### Task 1: Independent integer vector check

Files: tools/scripts/e203_soc.py; tests/e203/test_vectors.py.
Consumes: strict signed .mem layout and original hashed archive.
Produces: check_vectors(directory, tasks) and --mode check-vectors with default fixture or --vectors.
- [x] Add a failing check using a sparse, hand-derived signed matrix; corrupt one y word and require row/column diagnosis.
- [x] Extract existing archive loading into one helper; implement exact Python integer XW+b comparison and SHA report without simulator/toolchain requirements.
- [x] Run host tests and all 12 real layers; commit.

### Task 2: Real preflight and sequential acceptance

Files: e203_soc.py, tools/scripts/server_accept.py; test_runner.py, test_accept.py; .github/workflows/host-checks.yml.
Consumes: Task 1 checker, existing runner modes and exact submodule pin.
Produces: doctor with RV32 build/identity validation; fail-closed standard/full acceptance CLI.
- [x] Reproduce missing-submodule and failing-step cases in runnable tests.
- [x] Validate submodule root/gitlink, actual firmware build and compiler versions in doctor. Run host, vector, doctor, baseline, synthetic1, real12 sequentially; --full additionally runs Chisel and Icarus1.
- [x] Run all host tests, doctor and actual complete acceptance; retain logs and commit.
- [x] Enable the same lightweight host/vector checks on GitHub and inspect the actual run.

### Task 3: Offline reconstruction and handoff

Files: docs/server-handoff.md, README.md, quickstart.md, docs/validation/server-prep-20261027/.
Consumes: committed source, E203 gitlink, successful Task 1/2 evidence.
Produces: documented native bundle recipe, local bundle pair plus hashes, offline restoration evidence and official-material checklist.
- [x] Create/verify both bundles; restore into a new directory without network, verify commits and run host/real1 there.
- [x] Document exact commands, acceptance limits and official inputs still needed; copy compact immutable evidence.
- [x] Fresh final review, fix important findings with RED→GREEN checks, rerun affected checks, commit/push only the new branch.
