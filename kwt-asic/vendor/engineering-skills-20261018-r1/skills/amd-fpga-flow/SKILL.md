---
name: amd-fpga-flow
description: Inspect AMD/Xilinx Vivado or Vitis FPGA flows and verify requested outcomes.
---

# AMD FPGA Flow

Drive the smallest existing flow that proves the requested outcome. Reuse project-owned manifests, scripts, constraints, testbenches, golden data, and build directories before creating new ones.

## Establish the flow contract

Before changing or running anything, determine from repository evidence:

- tool and version; target part/board; top module; clock target;
- Project Mode versus Non-Project Mode;
- production source manifest, constraints, block design, generated IP, and canonical golden inputs;
- existing stage entry points and their prerequisites;
- requested outcome: analysis, script generation, execution, optimization, artifact generation, or hardware operation.

Run `python scripts/discover_fpga_project.py <project-root>` when these facts are scattered or unfamiliar. Treat its output as an inventory, not as proof that a candidate is authoritative.

Do not guess a device, clock, top, build mode, numerical threshold, or programming target when execution depends on it. Prefer checked-in configuration and manifests over directory-name inference.

## Route the task

Read [references/flow-routing.md](references/flow-routing.md) when selecting stages or acceptance evidence. On Windows or when tool activation/path behavior matters, also read [references/windows-toolchain.md](references/windows-toolchain.md).

When an appropriate focused skill is installed, use it when its subject dominates the work:

- `vivado-tcl` for Tcl generation, review, or execution;
- `vivado-sim` for xsim and simulation-flow decisions;
- `vivado-analysis` for report interpretation;
- `vivado-constraints` for XDC and timing constraints;
- `vivado-timing-closure` for iterative timing convergence;
- `vivado-debug` for ILA/VIO/JTAG planning and hardware debug.

These focused skills are optional and are not bundled here. If unavailable, use the project-owned commands and actual tool documentation without adding a dependency or stopping the task.

This skill owns orchestration and cross-stage consistency. A focused skill does not broaden authorization.

## Preserve project truth

- Identify canonical files and generated derivatives. Do not create a second source manifest, golden model, ROM copy, or convenience copy of production RTL.
- Preserve the established project/non-project flow. Do not mix `launch_runs` with an open non-project `synth_design` flow.
- Keep user changes and unrelated dirty files intact. Put generated output only in existing ignored build locations or an explicitly chosen temporary/output directory.
- Reuse valid results only when their source identity, configuration, and requested acceptance scope match the current change.
- Do not weaken constraints, numerical tolerances, assertions, counters, or test coverage merely to obtain PASS.

## Execute proportionately

For code/configuration changes, validate from cheap/local to expensive/global as applicable:

1. static checks, manifest checks, or compile/elaboration;
2. focused unit simulation and negative/boundary cases;
3. integration or numerical regression;
4. OOC synthesis for changed blocks or interfaces;
5. full synthesis/implementation/timing/DRC only when needed by the request;
6. bitstream, XSA, Vitis application, and board actions only when they are requested deliverables or necessary authorized validation.

Generate or review scripts without running them when that is the requested deliverable. Hardware programming, flash writes, device resets, and board interaction require explicit scope; build authorization alone does not imply them.

For a long run, preserve logs and report incremental status. If a run fails, inspect the first actionable error, distinguish tool/environment/license failures from design failures, apply only in-scope fixes, and rerun the narrowest invalidated stage.

## Verify the outcome

Check exit status plus stage-specific outputs. A produced file alone is not success.

- Simulation: compiled intended sources, exercised intended scenario, self-checks passed, no hidden fatal/error.
- Synthesis: run complete, intended top/part, no blocking messages, utilization and inferred structures reviewed.
- Implementation: fully routed, timing and pulse-width metrics checked, DRC/methodology findings classified, no unconstrained internal endpoints.
- Artifact chain: BIT/XSA/ELF or other outputs come from the same accepted source/configuration chain; record hashes when release or board evidence is claimed.
- Board: report the exact programmed artifacts, tool versions, inputs, raw logs, warm-up policy, repetitions, counters, correctness criteria, and determinism.

For a durable evidence record, use `fpga-change-evidence`. Clearly label unrun or unavailable checks as `NOT RUN` or `UNVERIFIED`; never convert absence of evidence into PASS.
