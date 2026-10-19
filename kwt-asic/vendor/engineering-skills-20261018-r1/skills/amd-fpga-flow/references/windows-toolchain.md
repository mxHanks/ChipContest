# Windows Vivado/Vitis execution

## Environment

- Prefer the repository's checked entry scripts (`.bat`, `.ps1`, Tcl, or Python).
- Verify `vivado.bat`, `vitis.bat`, `vitis-run`, or `xsct.bat` is discoverable before launching an expensive run.
- Use the tool version declared by project configuration or release evidence. Do not silently fall back to another installed version.
- When the vendor `settings64.bat` is broken by an optional component, use the documented product-specific setup script only if the project already establishes that route.

## Paths and outputs

- Keep source paths stable. Use a short ASCII build/workspace path when a Vivado/Vitis/IP flow is sensitive to path length or non-ASCII characters.
- Prefer project-defined overrides for build root, XSA, or Vitis workspace.
- Do not write build caches into source directories unless the existing flow intentionally does so.
- Quote Windows paths and pass literal paths to PowerShell filesystem operations.

## Shell boundaries

- Run `.bat` entry points through `cmd.exe /c` only when needed; otherwise keep a PowerShell workflow in PowerShell.
- Preserve the child process exit code. Search logs after the process ends rather than treating console silence as success.
- Do not translate a working project Tcl flow into a new shell pipeline merely for convenience.

## Long runs

Capture the run directory and log path before starting. For synthesis/implementation, retain the tool log, run status, reports, and generated artifact paths. A timeout, license wait, or missing executable is an environment result, not an RTL failure.

