# E203 C Integration Implementation Plan

> For agentic workers: execute inline using superpowers:executing-plans, then request one fresh whole-branch review.

**Goal:** Complete the C-role development SoC chain and portable regression entry point.
**Architecture:** Preserve eight-PE core and ABI; add optional external memory pins, C firmware, an independent memory/writeback scoreboard and a stdlib Python runner.
**Tech Stack:** Existing Verilog/SystemVerilog, bare-metal RV32 GCC, Icarus 12, Verilator, Python3; existing Scala CLI project for core regression.
**Spec:** docs/superpowers/specs/2026-10-26-e203-c-integration-design.md

## Global Constraints

New branches only; preserve Chisel/core ABI; CPU/testbench never substitutes mandatory computation. Keep E203 a submodule. Push E203 first. Follow repository make clean/install workflow. Keep official PPA status separate from development results.

## Review Focus

- Signed 40/48-bit high words must survive C and MMIO conversion.
- Accepted output writes and their responses, not core done alone, establish completion.
- Missing/truncated/oversized vector files and tool failures must stop the runner.
- Parameter reload must not reuse prior-layer SRAM or sticky done state.
- A bad expected result, simulation timeout or nonzero exit must never report PASS.

### Task 1: External memory and CPU-driven writeback

Files: E203 rtl/e203/soc/e203_soc_top.v; main tests/e203/tb_accel_soc.sv, firmware/{start.S,link.ld,accel.h,accel.c,main.c}.
Consumes: existing accel_icb_slave ABI at 0x10042000.
Produces: signed full-matrix CPU writes to shared memory; TASK_PASS / SOC_PASS markers.
- [ ] Add TB/firmware first; demonstrate missing top-level memory interface fails compilation.
- [ ] Add optional external ICB ports, preserving default behavior.
- [ ] Compile/run a complete synthetic layer and a negative golden-data test.
- [ ] Run the existing default ADD and four assembly tests through repository make flow.
- [ ] Commit/push E203 changes on new feature/e203-c-integration branch before main gitlink.

### Task 2: Portable runner and 12-layer coverage

Files: tools/scripts/e203_soc.py; tests/e203/test_runner.py; tests/e203/vectors/ fixture archive/provenance.
Consumes: Task 1 top/TB/firmware, strict .mem vectors.
Produces: fail-closed build/simulation runner and JSON/log evidence.
- [ ] Write/run failing stdlib tests for input validation, negative result detection and command failure.
- [ ] Implement doctor, baseline, synthetic and external-vector modes; explicit paths/options, version/hash records, optional waves.
- [ ] Import only existing real-checkpoint silence .mem data/provenance from c2e58fd, without adopting its alternate hardware/ABI.
- [ ] Run synthetic and real 12-task regressions without per-layer reset; verify signed values and exact output/write counts.
- [ ] Run host tests and repository Scala regression; commit the integrated software/test milestone on the new main branch.

### Task 3: Documentation, fresh reconstruction and review

Files: README.md, quickstart.md, docs/e203-integration.md.
Consumes: actual Task 1/2 command outputs and limitations.
Produces: reproducible handoff and honest validation summary.
- [ ] Document prerequisites, commands, memory map, vector contract, source identity, waveform/timing scope and official-server handoff.
- [ ] Repeat a build/run from a separate directory using documented inputs.
- [ ] Request fresh review; fix important findings with reproducing tests and rerun relevant/full checks.
- [ ] Commit docs and verified fixes. Publish only new feature branches if credentials permit; otherwise preserve commits and report exact publishing blocker.
