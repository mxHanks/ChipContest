#!/usr/bin/env python3
"""Plan and audit deletion of structurally unobservable mapped leaf cones.

Original mapped leaves remain opaque. Pin directions and sequential attributes
must come from sealed native reports for the exact library hashes; names such
as Q/ZN are never used to infer direction or state. The default protects every
sequential leaf and every SRAM. Candidate auditing permits only proven dead
deletions plus the existing checker's native-proven identity-buffer additions.
This is a mapped connectivity/unobservability proof, not RTL formal or STA.
"""
import argparse
from collections import Counter, defaultdict
import copy
import csv
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import check_buffer_equivalence as eq


def pinned_path(proof_path, entry):
    path = Path(entry["path"])
    if not path.is_absolute():
        path = proof_path.parent / path
    path = path.resolve()
    eq.require(path.is_file() and eq.sha(path) == entry["sha256"],
               "NATIVE_METADATA_IDENTITY", str(path))
    return path


def load_metadata(proof_path, report_path=None):
    proof = json.loads(proof_path.read_text())
    execution_path = pinned_path(proof_path, proof["native_execution"])
    execution = json.loads(execution_path.read_text())
    if report_path is None:
        field = "reference_metadata" if "reference_metadata" in proof else "reference_report"
        eq.require(field in proof, "MISSING_NATIVE_REFERENCE_REPORT",
                   "Provide reference_report in proof JSON or --reference-report")
        report_path = pinned_path(proof_path, proof[field])
    else:
        report_path = report_path.resolve()
    try:
        relative = report_path.relative_to(execution_path.parent).as_posix()
    except ValueError:
        raise eq.Rejected("REFERENCE_REPORT_OUTSIDE_NATIVE_EXECUTION", str(report_path))
    eq.require(execution.get("outputs", {}).get(relative) == {
        "sha256": eq.sha(report_path), "bytes": report_path.stat().st_size},
        "REFERENCE_REPORT_NOT_NATIVE_SEALED", relative)
    text = report_path.read_text()
    if r"\t" in text.splitlines()[0]:
        text = text.replace(r"\t", "\t")
    rows = list(csv.DictReader(text.splitlines(), delimiter="\t"))
    eq.require(rows and set(rows[0]) == {"reference", "library_cell", "is_sequential"},
               "REFERENCE_REPORT_COLUMNS", sorted(rows[0]) if rows else [])
    metadata = {}
    for row in rows:
        ref = row["reference"]
        eq.require(row["library_cell"].rsplit("/", 1)[-1] == ref,
                   "REFERENCE_LIBRARY_NAME_MISMATCH", row)
        value = row["is_sequential"].lower()
        eq.require(value in {"false", "true", "0", "1"},
                   "UNKNOWN_NATIVE_SEQUENTIAL_ATTRIBUTE", row)
        eq.require(ref not in metadata, "DUPLICATE_REFERENCE_METADATA", row)
        metadata[ref] = {"library_cell": row["library_cell"],
                         "is_sequential": value in {"true", "1"}}
    return metadata, {"path": str(report_path), "sha256": eq.sha(report_path),
                      "native_execution_sha256": eq.sha(execution_path), "rows": len(rows)}


def pin_direction(directions, ref, port, bits, index):
    pin = port if len(bits) == 1 and (ref, port) in directions else port + "[" + str(index) + "]"
    eq.require((ref, pin) in directions, "UNKNOWN_NATIVE_LEAF_DIRECTION", [ref, port, index])
    return directions[(ref, pin)]


def topology(module, directions, metadata, allow_state=False, expected_macros=353):
    eq.require(not module.get("memories") and not module.get("processes"),
               "NONOPAQUE_FLATTENED_SCOPE", "memory/process remains")
    cells = module.get("cells", {})
    eq.require(cells, "EMPTY_MAPPED_LEAF_SCOPE", "no mapped leaves")
    protected, outputs, consumers = {}, {}, defaultdict(set)
    macros = []
    for name, cell in cells.items():
        ref = cell["type"]
        eq.require(ref in metadata, "MISSING_NATIVE_REFERENCE_METADATA", [name, ref])
        if ref.startswith("RAMSP"):
            protected[name] = "SRAM_ALWAYS_PRESERVED"
            macros.append(name)
        elif metadata[ref]["is_sequential"] and not allow_state:
            protected[name] = "SEQUENTIAL_PROTECTED_FIRST_PASS"
        outs = set()
        for port, bits in cell["connections"].items():
            for i, bit in enumerate(bits):
                node = eq.bit_node(bit)
                direction = pin_direction(directions, ref, port, bits, i)
                if direction == "out":
                    outs.add(node)
                elif direction == "in":
                    consumers[node].add(name)
                else:
                    protected[name] = "BIDIRECTIONAL_LEAF_ALWAYS_PRESERVED"
                    consumers[node].add(name)
        if not outs:
            protected[name] = "NO_CONNECTED_OUTPUTS_NOT_CHARACTERIZED_FOR_DELETION"
        if any(node[0] == "constant" for node in outs):
            protected[name] = "OUTPUT_CONNECTED_TO_LITERAL_CONSTANT"
        outputs[name] = outs
    if expected_macros is not None:
        eq.require(len(macros) == expected_macros, "SRAM_MACRO_COUNT_CHANGED",
                   {"expected": expected_macros, "actual": len(macros)})
    # All top ports are protected, including input/inout nets. This also avoids
    # making any bus-resolution claim on a malformed input-driven net.
    top = {eq.bit_node(bit) for port in module["ports"].values() for bit in port["bits"]}
    active, waves = set(cells), []
    while True:
        ready = sorted(name for name in active if name not in protected and outputs[name]
                       and all(node not in top and not (consumers[node] & active)
                               for node in outputs[name]))
        if not ready:
            break
        waves.append(ready)
        active.difference_update(ready)
    return {"waves": waves, "removed": set(cells) - active, "retained": active,
            "protected": protected, "outputs": outputs, "consumers": consumers,
            "top_nodes": top, "macros": sorted(macros)}


def verify_deletions(original, candidate, info, functions, directions):
    oc, cc = original["cells"], candidate["cells"]
    removed = set(oc) - set(cc)
    eq.require(removed <= info["removed"], "REMOVAL_NOT_IN_PROVEN_DEAD_CONES",
               sorted(removed - info["removed"])[:50])
    retained = set(oc) - removed
    for name in sorted(removed):
        eq.require(name not in info["protected"], "PROTECTED_LEAF_REMOVED", name)
        for node in info["outputs"][name]:
            eq.require(node not in info["top_nodes"] and
                       not (info["consumers"][node] & retained),
                       "REMOVED_OUTPUT_STILL_OBSERVABLE",
                       {"cell": name, "node": list(node),
                        "retained_consumers": sorted(info["consumers"][node] & retained)})
    projected = copy.deepcopy(original)
    projected["cells"] = {name: cell for name, cell in oc.items() if name not in removed}
    result = eq.compare(projected, candidate, functions, directions)
    result.update(removed_leaves=sorted(removed), removed_leaf_count=len(removed),
                  removed_type_counts=dict(Counter(oc[name]["type"] for name in removed)),
                  all_removed_outputs_unobservable_to_retained_leaves_and_top=True,
                  all_original_SRAM_leaves_preserved=True)
    return result


def tcl_literal(value):
    eq.require(not any(x in value for x in "{}\\\r\n\t "), "UNSAFE_TCL_EXACT_NAME", value)
    return "{" + value + "}"


def native_instance(name, cell):
    """Use Yosys's original identifier tokens, preserving literal dots in a token."""
    tokens = cell.get("attributes", {}).get("hdlname", "").split()
    eq.require(tokens and ".".join(tokens) == name, "MISSING_OR_AMBIGUOUS_HDLNAME", name)
    result = "/".join(tokens)
    tcl_literal(result)
    return result


def write_tcl(path, original_path, original, info, original_sha, top):
    lines = [
        "# Exact dead-cone deletion plan. Source only in its separately receipted DC job.",
        "# The loaded map must be the SHA-bound original; no SDC or library changes.",
        "proc xu_dead_need {condition message} {if {!$condition} {error $message}}",
        "xu_dead_need [info exists ::xu_dead_original_map] {set ::xu_dead_original_map to the SHA-bound input map}",
        "set xu_dead_digest [lindex [exec sha256sum $::xu_dead_original_map] 0]",
        "xu_dead_need [expr {$xu_dead_digest eq {" + original_sha + "}}] {dead-cone original map SHA mismatch}",
        "xu_dead_need [expr {[get_object_name [current_design]] eq {" + top + "}}] {wrong dead-cone current_design}",
        "set xu_dead_macro_count [sizeof_collection [get_cells -hierarchical -filter {ref_name =~ RAMSP*}]]",
        "xu_dead_need [expr {$xu_dead_macro_count == " + str(len(info["macros"])) + "}] {original SRAM count mismatch}",
        "set xu_dead_removed 0",
    ]
    for wave_index, wave in enumerate(info["waves"]):
        lines.append("# Wave " + str(wave_index) + ": topology rechecked before any deletion in this wave.")
        native_names = {name: native_instance(name, original["cells"][name]) for name in wave}
        lines.append("set xu_dead_wave [list " + " ".join(tcl_literal(native_names[n]) for n in wave) + "]")
        lines.extend([
            "foreach xu_dead_name $xu_dead_wave {",
            "  set xu_dead_cell [get_cells -quiet $xu_dead_name]",
            "  xu_dead_need [expr {[sizeof_collection $xu_dead_cell] == 1 && [get_object_name $xu_dead_cell] eq $xu_dead_name}] {dead-cone exact leaf absent/ambiguous}",
            "  xu_dead_need [expr {![get_attribute $xu_dead_cell is_hierarchical]}] {refusing hierarchical-cell deletion}",
            "  foreach_in_collection xu_dead_pin [get_pins -of_objects $xu_dead_cell] {",
            "    if {[get_attribute $xu_dead_pin direction] ne {out}} {continue}",
            "    foreach_in_collection xu_dead_connected [all_connected -leaf $xu_dead_pin] {",
            "      xu_dead_need [expr {[get_attribute $xu_dead_connected object_class] ne {port}}] {dead output connected to top port}",
            "      if {[get_attribute $xu_dead_connected object_class] eq {pin}} {",
            "        set xu_dead_direction [get_attribute $xu_dead_connected direction]",
            "        xu_dead_need [expr {$xu_dead_direction eq {out}}] {dead output still drives a leaf input/inout}",
            "      }",
            "    }",
            "  }",
            "}",
        ])
        # Runtime reference identities are exact, not wildcards or name-derived
        # substitutes. The generated cell list always contains leaves only.
        for name in wave:
            ref = original["cells"][name]["type"]
            lines.append("xu_dead_need [expr {[get_attribute [get_cells " + tcl_literal(native_names[name]) +
                         "] ref_name] eq " + tcl_literal(ref) + "}] {dead-cone reference drift}")
        lines.extend([
            "foreach xu_dead_name $xu_dead_wave {remove_cell [get_cells $xu_dead_name]; incr xu_dead_removed}",
            "puts \"DEAD_CONE_WAVE_COMPLETE " + str(wave_index) + " removed=$xu_dead_removed\"",
        ])
    lines.extend([
        "xu_dead_need [expr {$xu_dead_removed == " + str(len(info["removed"])) + "}] {dead-cone removed count mismatch}",
        "xu_dead_need [expr {[sizeof_collection [get_cells -hierarchical -filter {ref_name =~ RAMSP*}]] == $xu_dead_macro_count}] {SRAM removed}",
        "puts {DEAD_CONE_PRUNING_EDITS_COMPLETE_NOT_STA_OR_FORMAL_SIGNOFF}",
    ])
    path.write_text("\n".join(lines) + "\n")


def self_test():
    def cell(ref, **con):
        return {"type": ref, "parameters": {}, "connections": {p: [b] for p, b in con.items()}}
    mod = {"ports": {"a": {"direction": "input", "bits": [1]},
                     "y": {"direction": "output", "bits": [2]}},
           "cells": {"live": cell("OPAQUE", A=1, O=2),
                     "dead_tail": cell("OPAQUE", A=3, O=4),
                     "dead_head": cell("OPAQUE", A=1, O=3),
                     "state": cell("STATE", D=1, Q=5),
                     "ram": cell("RAMSP", D=1, Q=6)}}
    directions = {(r, p): d for r, pinrows in {
        "OPAQUE": {"A": "in", "O": "out"}, "STATE": {"D": "in", "Q": "out"},
        "RAMSP": {"D": "in", "Q": "out"}}.items() for p, d in pinrows.items()}
    meta = {r: {"is_sequential": r in {"STATE", "RAMSP"}} for r in {"OPAQUE", "STATE", "RAMSP"}}
    info = topology(mod, directions, meta, expected_macros=1)
    eq.require(info["waves"] == [["dead_tail"], ["dead_head"]], "SELF_TEST_DEAD_WAVES", info["waves"])
    tests = []
    for name, removed, allowed in [
        ("legal_tail", {"dead_tail"}, True),
        ("legal_recursive_cone", {"dead_tail", "dead_head"}, True),
        ("head_still_drives_tail", {"dead_head"}, False),
        ("top_output_observable", {"live"}, False),
        ("default_state_protected", {"state"}, False),
        ("SRAM_always_protected", {"ram"}, False),
    ]:
        cand = copy.deepcopy(mod)
        cand["cells"] = {n: c for n, c in cand["cells"].items() if n not in removed}
        actual, reason = True, None
        try:
            verify_deletions(mod, cand, info, {}, directions)
        except eq.Rejected as error:
            actual, reason = False, error.code
        eq.require(actual == allowed, "SELF_TEST_EXPECTATION", [name, actual, allowed, reason])
        tests.append({"case": name, "result": "PASS", "rejection": reason})
    unknown = dict(directions)
    unknown.pop(("OPAQUE", "O"))
    try:
        topology(mod, unknown, meta, expected_macros=1)
    except eq.Rejected as error:
        eq.require(error.code == "UNKNOWN_NATIVE_LEAF_DIRECTION", "SELF_TEST_UNKNOWN_DIRECTION", error.code)
        tests.append({"case": "native_direction_required", "result": "PASS", "rejection": error.code})
    else:
        raise eq.Rejected("SELF_TEST_EXPECTATION", "unknown native pin direction accepted")
    return {"status": "SELF_TEST_PASS", "synthetic_fixture": True, "tests": tests}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--function-proof", type=Path)
    parser.add_argument("--reference-report", type=Path)
    parser.add_argument("--top", default="xu_soc_sysbus32_ppa_top")
    parser.add_argument("--expected-macros", type=int, default=353)
    parser.add_argument("--allow-unobservable-state", action="store_true",
                        help="Allow only structurally dead sequential outputs; SRAM always protected")
    parser.add_argument("--yosys", default="yosys")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if not args.self_test and (not args.original or not args.function_proof):
        parser.error("--original and --function-proof are required")
    args.out_dir.mkdir(parents=True, exist_ok=False)
    try:
        if args.self_test:
            result = self_test()
        else:
            eq.require(re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", args.top), "INVALID_TOP_NAME", args.top)
            functions, directions, proof = eq.load_native_functions(args.function_proof)
            metadata, metadata_identity = load_metadata(args.function_proof, args.reference_report)
            yosys = shutil.which(args.yosys)
            eq.require(yosys, "YOSYS_NOT_FOUND", args.yosys)
            original, flatten_receipt = eq.flatten(args.original, args.top, args.out_dir / "original", yosys)
            info = topology(original, directions, metadata, args.allow_unobservable_state, args.expected_macros)
            result = {"status": "DEAD_CONE_PLAN_SEALED_NOT_EXECUTED", "original": {
                "path": str(args.original.resolve()), "sha256": eq.sha(args.original)},
                "original_flatten": flatten_receipt, "native_function_and_direction_proof": proof,
                "native_reference_metadata": metadata_identity,
                "protect_sequential": not args.allow_unobservable_state,
                "preserved_SRAM_macros": info["macros"], "waves": info["waves"],
                "removed_leaf_count": len(info["removed"]),
                "removed_type_counts": dict(Counter(original["cells"][n]["type"] for n in info["removed"])),
                "protected_reason_counts": dict(Counter(info["protected"].values())),
                "yosys": {"path": yosys, "sha256": eq.sha(Path(yosys)),
                           "version": subprocess.check_output([yosys, "-V"], text=True).strip()}}
            write_tcl(args.out_dir / "delete-dead-cones.tcl", args.original, original, info,
                      eq.sha(args.original), args.top)
            result["draft_deletion_tcl_sha256"] = eq.sha(args.out_dir / "delete-dead-cones.tcl")
            if args.candidate:
                candidate, receipt = eq.flatten(args.candidate, args.top, args.out_dir / "candidate", yosys)
                result["candidate"] = {"path": str(args.candidate.resolve()), "sha256": eq.sha(args.candidate)}
                result["candidate_flatten"] = receipt
                result["audit"] = verify_deletions(original, candidate, info, functions, directions)
                result["status"] = "DEAD_CONE_AND_BUFFER_CONNECTIVITY_EQUIVALENCE_PASS"
            result["limitations"] = ["Mapped structural unobservability/connectivity only; opaque original leaf functions unchanged",
                "No RTL-to-mapped formal equivalence, STA, reset/clock glitch, delay or analog signoff",
                "Native all_connected/pin-direction verification in draft Tcl must pass before each deletion wave",
                "New mapped outputs, own SVF and full fresh PT reports remain mandatory"]
    except (eq.Rejected, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        result = {"status": "DEAD_CONE_PROOF_FAIL", "failure": {
            "code": error.code if isinstance(error, eq.Rejected) else type(error).__name__,
            "detail": error.detail if isinstance(error, eq.Rejected) else str(error)}}
    result["schema"] = "ingress1064-native-dead-cone-plan-and-proof-v1"
    result["checker_sha256"] = eq.sha(Path(__file__))
    (args.out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(result["status"])
    if "failure" in result:
        print(json.dumps(result["failure"], sort_keys=True))
    return int(result["status"] == "DEAD_CONE_PROOF_FAIL")


if __name__ == "__main__":
    sys.exit(main())
