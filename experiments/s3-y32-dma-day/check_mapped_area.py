#!/usr/bin/env python3
"""Independently reconcile a flattened Yosys mapped netlist/stat with Liberty.

This does not invoke synthesis or claim macro area, STA, power, or equivalence.
"""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def liberty_areas(path):
    # Cell declarations are top-level one-per-block in the pinned Nangate file.
    text = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
    starts = list(re.finditer(r"(?m)^\s*cell\s*\(\s*([^\s)]+)\s*\)\s*\{", text))
    result = {}
    for i, match in enumerate(starts):
        name = match[1].strip('"')
        assert name not in result, "Duplicate Liberty cell: " + name
        body = text[match.end():starts[i + 1].start() if i + 1 < len(starts) else len(text)]
        values = re.findall(r"(?m)^\s*area\s*:\s*([0-9.eE+\-]+)\s*;", body)
        assert len(values) == 1, "Missing/duplicate cell area: " + name
        value = Decimal(values[0])
        assert value.is_finite() and value >= 0, "Invalid cell area: " + name
        result[name] = value
    assert result, "No Liberty cells parsed"
    return result


def audit(netlist, statistics, liberty, top, macros=(), metadata=()):
    areas = liberty_areas(liberty)
    net = json.loads(netlist.read_text())
    stat = json.loads(statistics.read_text(), parse_float=Decimal)
    assert top in net["modules"], "Missing top in netlist: " + top
    module = net["modules"][top]
    assert not module.get("memories"), "Unmapped memories remain"
    counts = Counter(c["type"] for c in module.get("cells", {}).values())
    assert counts, "Empty mapped top"
    top_stat = stat["modules"].get("\\" + top, stat["modules"].get(top))
    assert top_stat is not None, "Missing top in stat: " + top
    assert dict(counts) == top_stat["num_cells_by_type"], "Per-cell counts differ: netlist/stat"
    assert sum(counts.values()) == top_stat["num_cells"], "Total cell counts differ"
    allowed_macro, allowed_metadata = set(macros), set(metadata)
    assert allowed_macro.isdisjoint(areas), "Library cell cannot be an excluded macro"
    assert allowed_metadata <= {"$scopeinfo"}, "Only explicit metadata $scopeinfo can be excluded"
    unknown = set(counts) - set(areas) - allowed_macro - allowed_metadata
    assert not unknown, "Unmapped, hierarchical, or unknown cells remain: " + repr(sorted(unknown))
    macro_counts = {}
    for name in sorted(set(counts) & allowed_macro):
        definition = net["modules"].get(name)
        assert definition is not None, "Macro declaration absent: " + name
        attr = definition.get("attributes", {}).get("blackbox", "0")
        assert int(str(attr), 2) != 0, "Excluded macro not declared blackbox: " + name
        assert not definition.get("cells") and not definition.get("memories"), "Macro contains logic"
        macro_counts[name] = counts[name]
    per_cell = {name: {"count": counts[name], "area_each": str(areas[name]),
                       "subtotal": str(areas[name] * counts[name])}
                for name in sorted(set(counts) & set(areas))}
    recomputed = sum((areas[name] * counts[name] for name in set(counts) & set(areas)), Decimal(0))
    reported = Decimal(str(top_stat["area"]))
    assert abs(recomputed - reported) <= Decimal("0.00001"), "Area mismatch: recomputed/stat"
    return {"status": "MAPPED_AREA_RECONCILIATION_PASS", "top": top,
            "inputs": {str(p.resolve()): sha(p) for p in (netlist, statistics, liberty)},
            "all_top_cells": sum(counts.values()), "standard_cells": sum(counts[n] for n in per_cell),
            "standard_cell_area_liberty_units": str(recomputed), "yosys_reported_area": str(reported),
            "excluded_macro_counts": macro_counts,
            "metadata_counts": {n: counts[n] for n in sorted(set(counts) & allowed_metadata)},
            "per_cell": per_cell,
            "scope": "Flattened netlist area/count reconciliation only; excluded macros have no area. No STA, power, or functional equivalence claim."}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--netlist-json", type=Path, required=True)
    ap.add_argument("--stat-json", type=Path, required=True)
    ap.add_argument("--liberty", type=Path, required=True)
    ap.add_argument("--top", required=True)
    ap.add_argument("--macro", action="append", default=[])
    ap.add_argument("--metadata", action="append", default=[])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    result = audit(a.netlist_json, a.stat_json, a.liberty, a.top, a.macro, a.metadata)
    with a.out.open("x") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(result["status"], a.top, result["standard_cell_area_liberty_units"])


if __name__ == "__main__":
    main()
