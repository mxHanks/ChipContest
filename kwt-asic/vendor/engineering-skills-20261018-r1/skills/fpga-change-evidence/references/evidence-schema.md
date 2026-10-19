# Evidence record schema

A durable record should contain these sections. Omit non-applicable fields rather than inventing values.

```text
claim
  label, scope, requested acceptance level
source
  repository, branch, base_sha, head_sha, dirty, changed_files
configuration
  tool/version, device, top, clock, parameters, interface tag,
  numeric mode, thresholds, workload, seed
execution[]
  stage, exact command, working directory, exit code, start/end,
  status (PASS/FAIL/BLOCKED/NOT RUN), log path and SHA-256
metrics
  counters, numerical error, timing, utilization, power, runtime
artifacts[]
  role, path, SHA-256, size, producer stage
findings
  warnings, waivers, limitations, invalidated evidence
conclusion
  proven claims, unverified claims, next required evidence
```

## Artifact identity

For a multi-tool chain, represent links explicitly:

```text
source/config -> Vivado run -> BIT + XSA
XSA -> platform/BSP/app build -> ELF
BIT/XSA/ELF + frozen inputs -> programming/run -> raw board log
```

If an XSA embeds a bitstream, compare its embedded BIT identity when the release process supports it. Never pair artifacts solely because their filenames or timestamps look related.

## Storage

Use small JSON/CSV/Markdown summaries in version control when project policy permits. Keep large raw logs and generated products in the project's established artifact location with hashes and a manifest. Respect canonical-source rules: evidence must point to sources, not duplicate them.

