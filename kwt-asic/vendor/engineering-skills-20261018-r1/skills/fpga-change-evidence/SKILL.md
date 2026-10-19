---
name: fpga-change-evidence
description: Capture, audit, compare, or package reproducible evidence for FPGA changes and signoff claims. Use when reporting test results, PPA/timing deltas, release readiness, artifact identity, BIT/XSA/ELF provenance, board logs, or PASS/FAIL/NOT RUN status across RTL, Vivado, Vitis, and hardware stages. Do not use to perform the design change itself.
---

# FPGA Change Evidence

Build an auditable chain from source identity through commands and results to artifacts. This skill records evidence; it does not make an unrun stage pass and does not authorize builds or hardware actions.

## Define the claim

Start with the exact claim being supported and its scope: unit behavior, numerical correctness, RTL integration, synthesis/resource estimate, implemented timing, generated artifacts, software build, or measured board behavior.

Read [references/signoff-levels.md](references/signoff-levels.md) to select the evidence tier. Read [references/evidence-schema.md](references/evidence-schema.md) when producing a durable JSON/Markdown record or release handoff.

## Capture identity

Record where applicable:

- repository path, branch, full base/head commit, dirty status, and relevant changed files;
- authoritative configuration, interface/schema tag, top, target part, tool version, clock, parameters, numeric mode, thresholds, and seeds;
- exact reproduction commands and exit codes;
- input, log, report, and output artifact paths plus SHA-256;
- expected versus actual counters and metrics;
- known warnings, waivers, limitations, and next dependency.

Use `python scripts/capture_fpga_evidence.py <project-root> ...` for deterministic Git/config/file/log/artifact inventory. It never runs FPGA tools. Pass only the relevant files/logs/artifacts; do not hash entire generated workspaces.

## Validate the claim boundary

- A code review or elaboration does not prove functional behavior.
- Behavioral simulation does not prove post-route timing.
- Synthesis timing is an estimate, not timing closure.
- A completed implementation does not prove board correctness.
- A BIT/XSA/ELF file does not prove that the board was programmed with it.
- Counter reductions demonstrate activity/work savings, not numerical equivalence.
- A screenshot does not replace command output, raw logs, or a self-checking result.
- Predicted, simulated, implemented, and measured values must be labeled separately.

If identity or a required check is missing, report `UNVERIFIED` or `NOT RUN`, not PASS. Preserve failing logs and useful negative tests rather than overwriting them with a later run.

## Compare changes

When comparing baseline and candidate:

- confirm compatible device, tool version, clock/constraints, top, workload, numeric mode, and report stage;
- show absolute values and deltas;
- identify confounders instead of attributing every delta to the intended change;
- keep the accepted/best candidate and its evidence addressable;
- state which downstream evidence was invalidated by the change.

## Deliver

Lead with scoped status and remaining gaps. Include reproduction commands, evidence paths, key metrics, artifact hashes, and known limitations. Prefer machine-readable JSON plus a concise human summary for release work. Do not commit bulky caches, unscoped logs, credentials, licenses, or duplicate generated sources just to preserve evidence.
