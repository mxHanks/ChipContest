# E203 xu integration

Scope approved by the user's xu assignment and explicit execution request. Follow README and both main/feature quickstarts; work only on new feature branches. Keep the Chisel core, existing MMIO ABI and upstream CPU unchanged. Main base: 9d5f800; E203 base: 999913e.

## Approach

Use a small bare-metal C driver to schedule the existing eight-output LinearComputeCore for 99 rows and 32 groups. CPU loads all parameters from a shared-memory model and writes every signed 48-bit output back as a signed 64-bit word. No CPU/testbench substitutes accelerator arithmetic. A separate testbench compares accepted memory writes with independent supplied golden vectors.

Expose the SoC's existing system-memory ICB through an optional top-level parameter/ports; retain default legacy zero-response behavior for existing board/testbench instantiations. The new testbench connects a 512 KiB behavioral memory at 0xA0000000. This is a development platform, not the unavailable official SRAM/platform or a physical implementation.

Inputs: canonical row-major x.mem (6336 signed16), w.mem (16384 signed16), bias.mem (256 signed40), y.mem (25344 signed48), layer_00 through layer_11. Optional external vector directories support A's future exports. Synthetic regression data and the existing real-checkpoint silence fixture have separate labels. No whole-model accuracy claim.

Shared-memory offsets: X 0x00000 (32-bit slots), W 0x08000 (32-bit slots), bias 0x18000 (64-bit slots), Y 0x20000 (64-bit slots), host control 0x7F000. Host control contains task count and per-layer completion ACK. ACK is accepted only after all 50688 output-word writes and responses have completed and passed comparison; then host replaces inputs for the next layer. No reset between layers.

Regression must check signed/high-word results, complete output ordering and addresses, late/busy completion, timeouts, altered golden data, repeated tasks and all 12 parameter sets. Timing is development CPU-from-shared-memory through accepted final write response; TB preload and official parameter-loading interface are excluded and must be disclosed.

## Ownership / constraints

- Main: firmware/tests, runner, input validation, docs, reports.
- E203: optional external system-memory wiring only. No edits to generated accelerator arithmetic or Chisel.
- Preserve make clean/install/compile/run_test baseline and all four existing assembly tests.
- Test before milestone commits; push new E203 branch before committing/pushing its main-repo gitlink.
- Official server/SDK migration, real macro binding and formal PPA remain pending actual material.
- Store reproducible commands, tool/source/vector identity, failures and complete log markers.

## Acceptance

Existing five tests pass; synthetic and real 12-layer SoC runs each compare 304128 signed outputs/608256 writes without an intervening reset. Deliberately corrupted expected data is rejected. Runner rejects malformed/missing inputs and missing tools before simulation. README/quickstart explain new commands and limits. A fresh directory can reproduce the tests.
