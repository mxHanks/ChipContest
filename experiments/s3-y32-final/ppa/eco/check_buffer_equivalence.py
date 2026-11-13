#!/usr/bin/env python3
"""Prove mapped connectivity equality after contracting native-proven buffers.

No standard-cell function is invented. Yosys reads hierarchy and flattens only
defined design modules; undefined mapped leaf cells remain opaque and named.
Every original leaf instance/type/parameter/port/bit and every top port is
retained. Added cells may only be native-proven BUFV2_12TR40/BUFV4_12TR40.

This is a structural buffer-contraction proof, not RTL-to-mapping formal
equivalence, delay/hold/clock-glitch proof, analog multiple-driver validation,
SRAM model validation or a replacement for post-ECO timing. Added buffer input
provenance, cycles and top-input driving are checked, but undefined original
leaf pin directions are not guessed.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ALLOWED = {"BUFV2_12TR40", "BUFV4_12TR40"}
STD_DB = "f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723"
SRAM_DB = "c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Rejected(Exception):
    def __init__(self, code, detail):
        self.code, self.detail = code, detail
        super().__init__(code + ": " + str(detail))


def require(condition, code, detail):
    if not condition:
        raise Rejected(code, detail)


def load_native_functions(proof_path, allow_fixture=False):
    """Consume exact native pin/function bytes bound by an execution receipt.

Proof JSON schema:
  schema: xu-native-buffer-function-proof-v1
  native_execution: {path: relative/or/absolute, sha256: ...}
  report: {path: relative/or/absolute, sha256: ...}
  direction_report: {path: relative/or/absolute, sha256: ...}

The native report MUST be in execution.outputs, with SHA256 and byte length.
TSV columns: library_cell, reference, pin, direction, function, is_sequential.
Each allowed reference must have exactly I(in) and Z(out), Z.function=I, and
is_sequential=false for both. The standard_cell DB hash is fixed to this
campaign's S40 baseline. A name or manually written PASS field is insufficient.
"""
    obj = json.loads(proof_path.read_text())
    require(obj.get("schema") == "xu-native-buffer-function-proof-v1", "FUNCTION_PROOF_SCHEMA", obj.get("schema"))

    def pinned(field):
        entry = obj[field]
        p = Path(entry["path"])
        if not p.is_absolute():
            p = proof_path.parent / p
        p = p.resolve()
        require(p.is_file() and sha(p) == entry["sha256"], "FUNCTION_PROOF_IDENTITY", str(p))
        return p

    execution, report = pinned("native_execution"), pinned("report")
    native = json.loads(execution.read_text())
    require(allow_fixture or not native.get("synthetic_fixture"), "SYNTHETIC_FUNCTION_PROOF_NOT_NATIVE", str(execution))
    require(native.get("returncode") == 0 and native.get("completion_marker") is True,
            "FUNCTION_NATIVE_RUN_INCOMPLETE", str(execution))
    libs = {x["role"]: x["sha256"] for x in native.get("libraries", [])}
    require(libs.get("standard_cell") == STD_DB and libs.get("sram") == SRAM_DB,
            "FUNCTION_LIBRARY_IDENTITY", libs)
    try:
        relative = report.relative_to(execution.parent).as_posix()
    except ValueError:
        raise Rejected("FUNCTION_REPORT_OUTSIDE_NATIVE_OUTPUT", str(report))
    require(native.get("outputs", {}).get(relative) == {"sha256": sha(report), "bytes": report.stat().st_size},
            "FUNCTION_REPORT_NOT_SEALED", relative)
    raw = report.read_text()
    if raw.startswith(r"library_cell\treference\t"):
        raw = raw.replace(r"\t", "\t")
    rows = list(csv.DictReader(raw.splitlines(), delimiter="\t"))
    require(rows and set(rows[0]) == {"library_cell", "reference", "pin", "direction", "function", "is_sequential"},
            "FUNCTION_NATIVE_COLUMNS", sorted(rows[0]) if rows else [])
    cells = defaultdict(list)
    for row in rows:
        require(row["reference"] in ALLOWED, "FUNCTION_UNEXPECTED_REFERENCE", row)
        require(row["library_cell"].rsplit("/", 1)[-1] == row["reference"], "FUNCTION_REFERENCE_MISMATCH", row)
        require(row["is_sequential"].lower() in {"false", "0"}, "FUNCTION_SEQUENTIAL_CELL", row)
        cells[row["reference"]].append(row)
    proven = {}
    for ref, pins in cells.items():
        require(len(pins) == 2 and {r["pin"] for r in pins} == {"I", "Z"},
                "FUNCTION_NOT_EXACT_UNARY_I_Z", [ref, pins])
        require(len({r["library_cell"] for r in pins}) == 1, "FUNCTION_LIBRARY_AMBIGUOUS", ref)
        pin = {r["pin"]: r for r in pins}
        require(pin["I"]["direction"] in {"in", "input"} and pin["Z"]["direction"] in {"out", "output"},
                "FUNCTION_WRONG_PIN_DIRECTION", pins)
        # Only parentheses/whitespace around a single identity variable are
        # accepted. No arbitrary expression evaluation or name-based inference.
        function = pin["Z"]["function"].strip().strip('"')
        require(re.fullmatch(r"\(*\s*I\s*\)*", function) and function.count("(") == function.count(")"),
                "FUNCTION_NOT_PROVEN_NONINVERTING", [ref, function])
        require(pin["I"]["function"].strip() in {"", "-"}, "INPUT_PIN_HAS_FUNCTION", pin["I"])
        proven[ref] = {"input": "I", "output": "Z", "library_cell": pin["Z"]["library_cell"]}
    direction_report = pinned("direction_report")
    try:
        relative = direction_report.relative_to(execution.parent).as_posix()
    except ValueError:
        raise Rejected("DIRECTION_REPORT_OUTSIDE_NATIVE_OUTPUT", str(direction_report))
    require(native.get("outputs", {}).get(relative) ==
            {"sha256": sha(direction_report), "bytes": direction_report.stat().st_size},
            "DIRECTION_REPORT_NOT_SEALED", relative)
    text = direction_report.read_text()
    if r"\t" in text.splitlines()[0]:
        text = text.replace(r"\t", "\t")
    records = list(csv.DictReader(text.splitlines(), delimiter="\t"))
    require(records and set(records[0]) == {"reference", "library_cell", "pin", "direction"},
            "DIRECTION_NATIVE_COLUMNS", sorted(records[0]) if records else [])
    directions = {}
    for row in records:
        require(row["library_cell"].rsplit("/", 1)[-1] == row["reference"], "DIRECTION_REFERENCE_MISMATCH", row)
        direction = {"input": "in", "output": "out"}.get(row["direction"], row["direction"])
        require(direction in {"in", "out", "inout"}, "UNKNOWN_NATIVE_PIN_DIRECTION", row)
        key = (row["reference"], row["pin"])
        require(key not in directions, "DUPLICATE_NATIVE_PIN_DIRECTION", row)
        directions[key] = direction
    return proven, directions, {"proof_sha256": sha(proof_path), "execution_sha256": sha(execution),
                    "report_sha256": sha(report), "standard_cell_db_sha256": STD_DB,
                    "direction_report_sha256": sha(direction_report), "sram_db_sha256": SRAM_DB,
                    "native_reference_pin_direction_rows": len(directions),
                    "synthetic_fixture": bool(native.get("synthetic_fixture"))}


class Union:
    def __init__(self):
        self.parent = {}

    def find(self, value):
        if value not in self.parent:
            self.parent[value] = value
        root = value
        while self.parent[root] != root:
            root = self.parent[root]
        while value != root:
            value, self.parent[value] = self.parent[value], root
        return root

    def join(self, left, right):
        left, right = self.find(left), self.find(right)
        if left != right:
            self.parent[right] = left


def bit_node(bit):
    require(isinstance(bit, int) and bit >= 0 or isinstance(bit, str) and bit in {"0", "1", "x", "z"},
            "UNKNOWN_BIT_ENCODING", bit)
    return ("net", bit) if isinstance(bit, int) else ("constant", bit)


def labelled_nets(module, cell_names):
    result = {}
    for port, data in module["ports"].items():
        for i, bit in enumerate(data["bits"]):
            result[("top", port, i)] = bit_node(bit)
    for cell in sorted(cell_names):
        for port, bits in module["cells"][cell]["connections"].items():
            for i, bit in enumerate(bits):
                result[("leaf", cell, port, i)] = bit_node(bit)
    # Constants are explicit labels, even when absent from a given netlist.
    for value in ("0", "1", "x", "z"):
        result[("constant", value)] = ("constant", value)
    return result


def partition(labels, union):
    buckets = defaultdict(list)
    for label, node in labels.items():
        buckets[union.find(node)].append(label)
    # Each observable pin label points to the complete set of labels sharing
    # its net. Comparing the resulting canonical classes catches every split
    # and merge, including a previously tied original pin or output constant.
    classes = sorted(tuple(sorted(values)) for values in buckets.values())
    return classes


def compare(original, candidate, functions, directions=None):
    for side, mod in (("original", original), ("candidate", candidate)):
        require(not mod.get("memories"), "UNFLATTENED_MEMORY", side)
        require(not mod.get("processes"), "BEHAVIORAL_PROCESS", side)
        require(not any("init" in n.get("attributes", {}) for n in mod.get("netnames", {}).values()),
                "INITIAL_STATE_ANNOTATION_NOT_SUPPORTED", side)
    oc, cc = original.get("cells", {}), candidate.get("cells", {})
    require(oc, "EMPTY_ORIGINAL_LEAF_SCOPE", "no original leaf cells")
    missing = sorted(set(oc) - set(cc))
    require(not missing, "MISSING_OR_RENAMED_ORIGINAL_LEAF", missing[:50])
    require(set(original["ports"]) == set(candidate["ports"]), "TOP_PORT_NAMES_CHANGED",
            {"original": sorted(original["ports"]), "candidate": sorted(candidate["ports"])})
    for port, data in original["ports"].items():
        other = candidate["ports"][port]
        require({k: v for k, v in data.items() if k != "bits"} ==
                {k: v for k, v in other.items() if k != "bits"} and len(data["bits"]) == len(other["bits"]),
                "TOP_PORT_SHAPE_CHANGED", port)
    for name, cell in oc.items():
        other = cc[name]
        require(cell["type"] == other["type"], "ORIGINAL_LEAF_REFERENCE_CHANGED",
                {"instance": name, "original": cell["type"], "candidate": other["type"]})
        require(cell.get("parameters", {}) == other.get("parameters", {}),
                "ORIGINAL_LEAF_PARAMETERS_CHANGED", name)
        require(cell.get("port_directions", {}) == other.get("port_directions", {}),
                "ORIGINAL_LEAF_PORT_DIRECTIONS_CHANGED", name)
        require({p: len(b) for p, b in cell["connections"].items()} ==
                {p: len(b) for p, b in other["connections"].items()},
                "ORIGINAL_LEAF_PORT_NAMES_OR_WIDTH_CHANGED", name)
    added = sorted(set(cc) - set(oc))
    before_labels = labelled_nets(original, oc)
    after_labels = labelled_nets(candidate, oc)
    require(set(before_labels) == set(after_labels), "OBSERVABLE_LABELS_CHANGED", "original pin label scope differs")
    union_before, union_after = Union(), Union()
    edges, producers = [], defaultdict(list)
    original_anchor_nodes = set(after_labels.values())
    top_input_nodes = {bit_node(bit) for data in candidate["ports"].values()
                       if data["direction"] in {"input", "inout"} for bit in data["bits"]}
    for name in added:
        cell, ref = cc[name], cc[name]["type"]
        require(ref in ALLOWED, "UNKNOWN_OR_NONBUFFER_ADDED_LEAF", [name, ref])
        require(ref in functions, "MISSING_NATIVE_NONINVERTING_FUNCTION_PROOF", [name, ref])
        require(not cell.get("parameters"), "ADDED_BUFFER_PARAMETERS", name)
        require(set(cell["connections"]) == {"I", "Z"} and
                len(cell["connections"]["I"]) == len(cell["connections"]["Z"]) == 1,
                "ADDED_BUFFER_PORTS_NOT_UNARY", name)
        pin, pout = bit_node(cell["connections"]["I"][0]), bit_node(cell["connections"]["Z"][0])
        require(pin != pout, "ADDED_BUFFER_SELF_LOOP", name)
        require(pout not in top_input_nodes, "ADDED_BUFFER_DRIVES_TOP_INPUT", name)
        require(pout[0] != "constant", "ADDED_BUFFER_DRIVES_LITERAL_CONSTANT", name)
        producers[pout].append(name)
        edges.append((name, pin, pout))
        union_after.join(pin, pout)
    require(all(len(names) == 1 for names in producers.values()), "MULTIPLE_ADDED_BUFFER_DRIVERS",
            {str(k): v for k, v in producers.items() if len(v) > 1})
    if added:
        require(directions, "MISSING_NATIVE_ORIGINAL_LEAF_PIN_DIRECTIONS", "No original leaf driver direction is guessed")
        drivers, original_drivers, inouts = defaultdict(list), defaultdict(list), set()
        for name, cell in oc.items():
            ref = cell["type"]
            for port, bits in cell["connections"].items():
                for i, bit in enumerate(bits):
                    native_pin = port if len(bits) == 1 and (ref, port) in directions else port + "[" + str(i) + "]"
                    require((ref, native_pin) in directions, "UNKNOWN_ORIGINAL_LEAF_PIN_DIRECTION", [name, ref, port, i])
                    direction = directions[(ref, native_pin)]
                    label = ("leaf", name, port, i)
                    if direction == "out":
                        drivers[after_labels[label]].append(label)
                        original_drivers[before_labels[label]].append(label)
                    elif direction == "inout":
                        inouts.add(after_labels[label])
        for port, data in original["ports"].items():
            for i, bit in enumerate(data["bits"]):
                label = ("top", port, i)
                if data["direction"] == "input":
                    drivers[after_labels[label]].append(label)
                    original_drivers[before_labels[label]].append(label)
                elif data["direction"] == "inout":
                    inouts.add(after_labels[label])
        for name, pin, pout in edges:
            drivers[pout].append(("new_buffer_output", name))
            require(pin not in {("constant", "x"), ("constant", "z")},
                    "BUFFER_DRIVEN_BY_LITERAL_X_Z_NOT_PROVEN", name)
        touched = {node for _, pin, pout in edges for node in (pin, pout)}
        components = {union_after.find(node) for node in touched}
        for node in inouts:
            require(union_after.find(node) not in components, "BUFFER_COMPONENT_CONTAINS_BIDIRECTIONAL_PIN", str(node))
        for node in touched:
            if node[0] != "constant":
                require(len(drivers[node]) == 1, "BUFFER_COMPONENT_WRONG_DRIVER_COUNT",
                        {"node": str(node), "drivers": [list(x) for x in drivers[node]]})
        # The unchanged original component must itself have one source; this
        # avoids claiming that wire contraction proves bus-resolution behavior.
        for label, node in after_labels.items():
            if union_after.find(node) in components and before_labels[label][0] != "constant":
                require(len(original_drivers[before_labels[label]]) == 1,
                        "ORIGINAL_BUFFER_COMPONENT_MULTIDRIVEN_OR_UNDRIVEN", list(label))
    # No floating-input added source or buffer-only cycle can be hidden by
    # treating the newly introduced internal node as an unconstrained driver.
    pending = list(edges)
    grounded = (set(drivers) - set(producers)) | {("constant", x) for x in ("0", "1")} if added else original_anchor_nodes
    while pending:
        ready = [edge for edge in pending if edge[1] in grounded]
        require(ready, "UNROOTED_OR_CYCLIC_ADDED_BUFFER_NETWORK", [edge[0] for edge in pending[:50]])
        for edge in ready:
            grounded.add(edge[2])
            pending.remove(edge)
    first, second = partition(before_labels, union_before), partition(after_labels, union_after)
    if first != second:
        orig_set, cand_set = set(first), set(second)
        changed = sorted(orig_set - cand_set)
        new = sorted(cand_set - orig_set)
        raise Rejected("ORIGINAL_PIN_NETWORK_PARTITION_CHANGED", {
            "original_changed_groups": [[list(x) for x in group[:20]] for group in changed[:12]],
            "candidate_changed_groups": [[list(x) for x in group[:20]] for group in new[:12]],
            "original_changed_group_count": len(changed), "candidate_changed_group_count": len(new)})
    return {"original_leaf_instances": len(oc), "candidate_leaf_instances": len(cc),
            "original_leaf_types": dict(sorted(Counter(c["type"] for c in oc.values()).items())),
            "original_leaf_pin_and_top_constant_labels": len(before_labels),
            "network_equivalence_classes": len(first), "added_buffers": added,
            "added_buffer_type_counts": dict(Counter(cc[n]["type"] for n in added)),
            "native_driver_direction_required_for_added_buffers": bool(added),
            "complete_original_network_partition_equal": True}


def flatten(path, top, directory, yosys):
    directory.mkdir()
    output, script, log = directory / "flattened.json", directory / "flatten.ys", directory / "yosys.log"
    script.write_text("read_verilog " + json.dumps(str(path.resolve())) + "\n" +
                      "hierarchy -top " + top + "\nflatten -noscopeinfo\n" +
                      "write_json " + json.dumps(str(output.resolve())) + "\n")
    command = [yosys, "-s", str(script.resolve())]
    start = time.time()
    with log.open("x") as handle:
        process = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, timeout=300)
    receipt = {"command": command, "returncode": process.returncode, "elapsed_seconds": time.time() - start,
               "source_sha256": sha(path), "script_sha256": sha(script), "log_sha256": sha(log)}
    require(process.returncode == 0 and output.is_file(), "YOSYS_READ_FLATTEN_FAILED", receipt)
    obj = json.loads(output.read_text())
    require(top in obj["modules"], "MISSING_FLATTENED_TOP", top)
    require(not obj["modules"][top].get("attributes", {}).get("blackbox"),
            "TOP_IS_BLACKBOX", top)
    # A remaining cell type may have a declared blackbox module, or be an
    # undefined mapped leaf. A defined live module must never remain unexpanded.
    module = obj["modules"][top]
    for cell in module.get("cells", {}).values():
        definition = obj["modules"].get(cell["type"])
        require(definition is None or str(definition.get("attributes", {}).get("blackbox", "0")).strip("0") in {"1"},
                "HIERARCHY_NOT_FULLY_FLATTENED", cell["type"])
    receipt["flattened_json_sha256"] = sha(output)
    return module, receipt


def audit_files(original, candidate, top, out, proof=None, yosys="yosys"):
    require(re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", top), "INVALID_TOP_IDENTIFIER", top)
    executable = shutil.which(yosys)
    require(executable, "YOSYS_NOT_FOUND", yosys)
    version = subprocess.check_output([executable, "-V"], text=True).strip()
    functions, directions, proof_identity = load_native_functions(proof) if proof else ({}, {}, None)
    first, a = flatten(original, top, out / "original", executable)
    second, b = flatten(candidate, top, out / "candidate", executable)
    result = compare(first, second, functions, directions)
    return dict(result, inputs={"original": {"path": str(original.resolve()), "sha256": sha(original)},
                                "candidate": {"path": str(candidate.resolve()), "sha256": sha(candidate)}},
                yosys={"path": executable, "sha256": sha(Path(executable)), "version": version},
                flatten_runs={"original": a, "candidate": b}, native_function_proof=proof_identity)


def self_test(out, yosys):
    base = """module top(input clk,input a,input b,output y,output c);
 wire q,d; assign d=a; assign c=1'b0;
 DFF state(.CK(clk),.D(d),.Q(q)); RAMSP1024X16 memory(.CLK(clk),.D(q),.Q(y));
 endmodule\n"""
    original = out / "fixture-original.v"
    original.write_text(base)
    # Synthetic function data is test-local only. Production --function-proof
    # requires a sealed native execution and raw library-pin report.
    functions = {ref: {"input": "I", "output": "Z"} for ref in ALLOWED}
    directions = {(ref, pin): direction for ref in ("DFF", "RAMSP1024X16")
                  for pin, direction in (("CK", "in"), ("CLK", "in"), ("D", "in"), ("Q", "out"))}
    tests = [
        ("self", base, True),
        ("legal_buffer", base.replace("assign d=a;", "BUFV2_12TR40 eco(.I(a),.Z(d));"), True),
        ("original_pin_reconnected", base.replace(".D(d)", ".D(b)"), False),
        ("inverting_added_cell", base.replace("assign d=a;", "INV_12TR40 eco(.I(a),.ZN(d));"), False),
        ("wrong_added_buffer", base.replace("assign d=a;", "BUFV8_12TR40 eco(.I(a),.Z(d));"), False),
        ("register_reference_changed", base.replace("DFF state", "OTHER_DFF state"), False),
        ("output_constant_changed", base.replace("assign c=1'b0;", "assign c=1'b1;"), False),
        ("missing_original_pin", base.replace(".D(d),", ""), False),
        ("wrong_original_pin_width", base.replace(".D(d)", ".D({d,b})"), False),
        ("renamed_original_state", base.replace("state(", "renamed("), False),
        ("reverse_buffer_top_input", base.replace("assign d=a;", "BUFV2_12TR40 eco(.I(d),.Z(a));"), False),
        ("floating_added_source", base.replace("assign d=a;", "wire floating; BUFV2_12TR40 eco(.I(floating),.Z(d));"), False),
    ]
    executable = shutil.which(yosys)
    require(executable, "YOSYS_NOT_FOUND", yosys)
    first, first_run = flatten(original, "top", out / "fixture-original", executable)
    results = []
    for name, source, expected in tests:
        candidate = out / ("fixture-" + name + ".v")
        candidate.write_text(source)
        reason, actual = None, False
        try:
            second, receipt = flatten(candidate, "top", out / ("case-" + name), executable)
            compare(first, second, functions, directions)
            actual = True
        except Rejected as error:
            reason = {"code": error.code, "detail": error.detail}
        require(actual == expected, "SELF_TEST_EXPECTATION_FAILED", {"case": name, "expected": expected, "actual": actual, "reason": reason})
        results.append({"case": name, "expected_equivalent": expected, "actual_equivalent": actual,
                        "result": "PASS", "rejection": reason})
    # Missing native function proof must fail even for a legally wired buffer.
    candidate = out / "fixture-legal_buffer.v"
    second, receipt = flatten(candidate, "top", out / "case-missing-function-proof", executable)
    try:
        compare(first, second, {})
    except Rejected as error:
        require(error.code == "MISSING_NATIVE_NONINVERTING_FUNCTION_PROOF", "WRONG_FUNCTION_REJECTION", error.code)
        results.append({"case": "native_function_proof_required", "result": "PASS", "rejection": error.code})
    else:
        raise Rejected("SELF_TEST_EXPECTATION_FAILED", "missing native function proof accepted")
    return {"status": "SELF_TEST_PASS", "synthetic_fixture": True, "native_library_function_proof": False,
            "scope": "Structural checker positive/negative fixtures, not real ECO equivalence or native buffer characterization.",
            "tests": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--top", default="xu_soc_ppa_top")
    parser.add_argument("--function-proof", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--yosys", default="yosys")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if not args.self_test and (not args.original or not args.candidate):
        parser.error("supply original and candidate mapped Verilog")
    args.out_dir.mkdir(parents=True, exist_ok=False)
    try:
        if args.self_test:
            result = self_test(args.out_dir, args.yosys)
        else:
            result = audit_files(args.original, args.candidate, args.top, args.out_dir, args.function_proof, args.yosys)
            result.update(status="BUFFER_CONTRACTION_STRUCTURAL_EQUIVALENCE_PASS",
                          scope="All original mapped leaf instances/parameters/ports/bits and top ports; native-proven identity buffers contracted; constants 0/1/x/z explicit.",
                          limitations=["Not RTL-to-mapped formal equivalence", "Not STA, reset/clock glitch or delay proof",
                                       "Original opaque leaf functions and unresolved leaf directions are not invented",
                                       "No analog or four-state multiply-driven-net signoff"])
    except (Rejected, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        result = {"status": "STRUCTURAL_EQUIVALENCE_FAIL",
                  "failure": {"code": error.code if isinstance(error, Rejected) else type(error).__name__,
                              "detail": error.detail if isinstance(error, Rejected) else str(error)}}
    result["schema"] = "xu-buffer-contraction-structural-equivalence-v1"
    result["checker_sha256"] = sha(Path(__file__))
    (args.out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(result["status"])
    if "failure" in result:
        print(json.dumps(result["failure"], sort_keys=True))
    return int(result["status"] not in {"BUFFER_CONTRACTION_STRUCTURAL_EQUIVALENCE_PASS", "SELF_TEST_PASS"})


if __name__ == "__main__":
    sys.exit(main())
