#!/usr/bin/env python3
"""Compare every physical reference used by the frozen B mapping to official LEF."""
import csv
from decimal import Decimal
import json
from pathlib import Path

from run_formality import SOURCE, check, sha

ROOT = Path(__file__).resolve().parent
STANDARD = ROOT / "std-rvt.lef"
SRAM = Path("/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/lef/RAMSP1024X16.lef")
LEAF = SOURCE / "leaf-inventory.tsv"


def geometry(path):
    macros = {}
    current = None
    for line in path.read_text().splitlines():
        words = line.split()
        if len(words) >= 2 and words[0] == "MACRO":
            current = words[1]
        elif current is not None and len(words) >= 4 and words[0] == "SIZE" and words[2] == "BY":
            if current in macros:
                raise ValueError("Duplicate macro SIZE: " + current)
            macros[current] = (Decimal(words[1]), Decimal(words[3]))
        elif words == ["END", current]:
            current = None
    return macros


def main():
    check(LEAF, "471e2ec9819adff79cd6ca79126bd6efbe0fb889bea6d3436a5234ad8652f60a")
    check(SRAM, "365316061e2c2ecd47e288eb1eb216d6b2bf5086924fa3b2bdcd2f217aa18327")
    physical = {"standard_cell": geometry(STANDARD), "SRAM": geometry(SRAM)}
    used = {}
    shared = 0
    with LEAF.open() as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            scope = row["classification"]
            if scope == "native_constant":
                continue
            ref = row["reference"]
            area = Decimal(row["area_library_units"])
            cell = used.setdefault(ref, {"area": area, "kind": scope, "instances": 0})
            if (area, scope) != (cell["area"], cell["kind"]):
                raise ValueError("Inconsistent library area: " + ref)
            cell["instances"] += 1
            if scope == "SRAM" and row["instance"].startswith("u_shared/"):
                shared += 1
    if shared != 256 or sum(c["instances"] for c in used.values()) != 200769:
        raise ValueError("Unexpected physical instance inventory")
    mismatches = []
    for ref, cell in sorted(used.items()):
        size = physical[cell["kind"]].get(ref)
        tolerance = Decimal("0.0005" if cell["kind"] == "SRAM" else "0.00001")
        discrepancy = size[0] * size[1] - cell["area"] if size else None
        cell.update(size_um=size, geometry_minus_db=discrepancy)
        if discrepancy is None or abs(discrepancy) > tolerance:
            mismatches.append(ref)
    receipt = {
        "reference_count": len(used), "mismatches": mismatches,
        "shared_sram_count": shared, "inputs": {str(p): sha(p) for p in (STANDARD, SRAM, LEAF)},
        "references": used,
    }
    with (ROOT / "area-geometry.json").open("x") as stream:
        json.dump(receipt, stream, default=str, indent=2)
        stream.write("\n")
    print("LEF_AREA_REVIEW", len(used), "references", len(mismatches), "mismatches", mismatches[:20])
    print("SHARED_SRAM", shared, "AREA_PER_MACRO", used["RAMSP1024X16"]["area"])
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
