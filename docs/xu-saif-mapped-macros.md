# xu measured SRAM activity relocation

`tools/ppa/xu_saif_mapped_macros.py` is an independent bridge between an
already-normalized measured SAIF and the exact SRAM names exported from the
mapped PrimeTime design. It does not change the collector or normalizer.
Its receipt has status
`RELOCATED_NOT_CAPTURE_ANNOTATION_OR_POWER_QUALIFIED`. No energy is calculated.

```sh
python3 tools/ppa/xu_saif_mapped_macros.py \
  --saif task-normalized.saif \
  --mapping xu_sram_activity_alias.mapping.json \
  --inventory xu-mapped-sram-inventory.json \
  --strip-path tb_xu_soc_ppa/dut \
  --out task-mapped.saif
```

The Python API is
`relocate(saif, mapping_path, inventory_path, out, strip_path, receipt_path=None)`.
The default receipt is `<out>.receipt.json`. Both output paths must be new, and
all five input/output/receipt paths must differ. On failure a newly created
output or receipt is removed. All input SHA-256 identities are checked again
before a successful receipt is written.

## Inventory contract v1

The JSON object requires these fields. Extra metadata fields are retained in
the inventory artifact and therefore covered by its whole-file SHA-256.

| Field | Required value or shape |
| --- | --- |
| `schema` | `xu-mapped-sram-pin-inventory-v1` |
| `status` | `EXPORTED_REVIEW_PENDING` |
| `netlist` | Identity object with nonempty `path` and 64 lowercase hex `sha256`; optional nonnegative integral `bytes` |
| `libraries` | Nonempty list of identity objects |
| `provenance` | Nonempty object containing the exporting tool/evidence identities |
| `macro_count` | Integral count equal to `len(macros)` |
| `pin_bit_count` | Integral count equal to `67 * macro_count` |
| `macros` | Complete nonempty list of macro records below |

Each macro record requires:

| Field | Required value or shape |
| --- | --- |
| `instance` | Exact DUT-relative `get_object_name` of the actual mapped cell |
| `ref_name` | `RAMSP1024X16` |
| `lib_cell` | Exact `get_object_name` of its unique linked Liberty cell, `<library>/RAMSP1024X16` |
| `pins` | Exactly 67 pin records |

Each pin record has `name`, `full_name`, and `direction`. `name` is one of
`CLK`, `CEN`, `GWEN`, `RET1N`, `WEN[0:15]`, `A[0:9]`, `D[0:15]`,
`EMA[0:2]`, `EMAW[0:1]`, or `Q[0:15]`, with every bus bit written as a
separate record such as `D[0]`. `full_name` must exactly equal
`instance + "/" + name`. Direction is `out` for Q bits and `in` otherwise.
Duplicate JSON keys, cells, bits, and full pin names are rejected.

Export from the linked PT design using `get_cells -hierarchical` filtered by
`ref_name == RAMSP1024X16`. For every cell export its `get_object_name`,
`ref_name`, the unique `get_lib_cells -of_objects` object, and every
`get_pins -of_objects` full name and `direction`. Use collection iteration,
not whitespace splitting of Tcl object names. A raw TSV exporter may write
`kind`, `cell`, `ref_or_pin`, and `libcell_or_direction`; a checked converter
must derive the pin leaf by removing the exact `cell + "/"` prefix, preserve
the raw TSV identity, and produce the complete JSON pin records. The parent
power runner is responsible for verifying inventory netlist/library identities
against its actual inputs and freezing raw TSV, exporter Tcl, PT log, tool,
constraints, and other provenance identities.

## Exact mapping and preservation

`--strip-path` must exactly equal the original mapping's `dut_scope` with dots
replaced by slashes. The original mapping must use the unchanged recorded
normalizer and SAIF reader SHA. Remote absolute source paths in an archived
mapping are preserved as declarations; the bridge does not dereference them.
The full-SoC mode also requires the exact current source-guarded 336-macro list;
the explicit probe mode remains separately identified.

Only the explicitly inventoried macro cell names are compared after replacing
dots with slashes. Comparison keys must be unique and match the complete
canonical macro list. This comparison does not infer arbitrary RTL hierarchy.
The output is constructed from the original actual cell spelling, split only
at `/`. Thus actual cell
`u_shared/storage/macro_storage.depth_bank[0].width_lane[0].macro` creates
one literal leaf INSTANCE named
`macro_storage.depth_bank[0].width_lane[0].macro`, under `u_shared/storage`.

Every canonical pin needs measured NET and/or PORT statistics. If both kinds
exist they must agree, including the exact attribute key set. Existing actual
mapped NET and/or PORT records are reused only when every statistic agrees.
There is no missing-key-as-zero equivalence. Otherwise a PORT copies the
original measured statistic tokens to the actual mapped position. Relocated
canonical records are removed; canonical records already at the actual
position remain. Containers emptied by relocation are pruned, while unrelated
siblings and preexisting empty containers remain. Unknown or extra activity within an explicitly enumerated
macro, missing bits, collisions, duplicates, and conflicts fail closed.

Every other `(kind, path, statistics)` record is preserved exactly. All SAIF
headers, including DURATION and TIMESCALE tokens, are preserved. The bridge
checks the complete output signal set, every actual pin's statistics, time
base, headers, and immutable input identities before writing its receipt.
Receipt schema `xu-saif-mapped-macros-v1` records input SAIF, output SAIF,
mapping, inventory, and bridge identities; complete macro/pin counts;
relocated/reused/unchanged counts; and SHA-256 summaries of the macro bijection
and all per-bit comparisons.

The receipt proves name relocation and measured-statistic preservation. The
original capture source provenance and normalization receipt remain an upper
layer audit. Actual PT annotation, direct-versus-propagated/default activity,
Liberty power, and contest qualification still need separate evidence. The
host tests use synthetic inventories, including the complete 336-macro and
22,512-bit topology, and make no actual PT or power claim.

```sh
python3 -m unittest discover -s tests/host -p test_xu_saif_mapped_macros.py -v
```
