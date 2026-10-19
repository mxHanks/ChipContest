# Replaceable SRAM boundary

`kwt_sram_1rw.sv` defines the generic storage contract used by the independent
SRAM-backed engine candidate. It is not a declaration of official SRAM pins.

| BACKEND | Meaning | Supported purpose |
| --- | --- | --- |
| 0 | BEHAVIORAL | Four-state functional simulation; rejected under `SYNTHESIS` |
| 1 | BLACKBOX | Opaque `kwt_sram_1rw_blackbox` for logic-only early synthesis; simulation refuses to run |
| 2 | FF_FALLBACK | Synthesizable FF/array reference; explicit `memory_map` may expand it to FF/MUX |
| 3 | OFFICIAL_MACRO | Requires an externally supplied `kwt_official_sram_adapter`; unavailable mode fails elaboration |

The common parameters are `WIDTH`, `DEPTH`, `BACKEND`, `CHECKS`, and `INIT_FILE`.
Ports are `clk`, `rst_n`, `wr_en`, `wr_addr`, `wr_data`, `rd_en`, `rd_addr`,
`rd_data`, and `rd_valid`. Address width is at least one bit and otherwise
`$clog2(DEPTH)`.

At a rising clock edge, a valid write commits one complete word. A read request
samples its address at that edge; registered `rd_data` and `rd_valid` are then
available during the following cycle. When no read occurs, Q holds its prior
value and `rd_valid` is zero. `rst_n` asynchronously clears `rd_valid` and gates
requests; it never clears payload, Q, or the simulation written bitmap. Loading
each task's input, weight, and bias remains the engine's responsibility.

This interface provides **one physical access per bank per cycle**. Any
simultaneous `rd_en && wr_en` is illegal, including different addresses.
Simulation with default `CHECKS=1` rejects collisions, unknown enables/data,
unknown/out-of-range addresses, and reads before initialization/write. No
read-during-write collision value is part of the supported contract. There is
no dual-port mode because the current candidate does not require one.

`INIT_FILE` is optional, simulation-side initialization for complete known HEX
images. A missing, short, or X-containing image is rejected. An empty filename
does not initialize or clear payload. The fallback also permits synthesis of
`$readmemh` where supported; this does not imply an ASIC SRAM has power-up
initialization support. No initialization behavior is promised for the opaque
or official backend.

`kwt_sram_bank.sv` composes the logical banks from 16-bit-wide storage slices
with capacity depths 4096, 1024, and 128. It registers the returning tile tag so
selection follows the one-cycle read response. Unused width/depth is padding,
not extra logical address space. These are capacity templates; official port,
control-polarity, latency, and collision details still need the actual model.

Run `make test-memory` from the repository root. The runner creates a new
`artifacts/runs/*-sram-unit-*/result.json` and saves commands, native exit codes,
tool versions, complete markers, source hashes, positive/negative tests, and
behavioral/FF read-data signatures. Negative tests pass only when the specified
fatal diagnostic and a nonzero native exit occur. Full engine and E203 tests
are separate evidence, rather than inferred from these unit tests.

BLACKBOX contains no Liberty timing arcs, area, or power. A positive logic-only
slack cannot establish a complete SRAM-to-logic timing result, and absent macro
area cannot be counted as zero for the competition's area limit.
