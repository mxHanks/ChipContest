#!/usr/bin/env python3
"""Fail-closed full-engine SRAM blackbox inspection and optional logic mapping.

No SRAM Liberty is available. A successful run proves retained opaque memory
boundaries and, with --map-logic, maps only surrounding logic to Nangate45.
It never proves complete 150 MHz timing, official area, or SRAM power.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import json
from pathlib import Path
import re
import sys
import uuid

from run_structural import ROOT, integer, record, run_command
from run_nangate_reference import LIB_SHA256, library_areas
sys.path.insert(0,str(ROOT/'scripts/verify'))
import sram_sources as SOURCES

TOP = "kwt_linear_engine_rowpair_sram"
PREP_MARKER = "KWT_SRAM_BLACKBOX_STRUCTURE_COMPLETE"
MAP_MARKER = "KWT_SRAM_BLACKBOX_LOGIC_MAPPING_COMPLETE"
ABC_MARKER = "KWT_SRAM_ABC_BUFFERED_COMPLETE"
LOGICAL = Counter({(16, 3200): 1, (16, 3136): 1, (16, 2048): 8,
                   (40, 32): 8, (41, 512): 2})
PHYSICAL = Counter({(16, 128): 50, (16, 1024): 22})


def number(value):
    return integer(value) if isinstance(value, (str, int)) else 0


def hdlname(module):
    names = str(module.get("attributes", {}).get("hdlname", "")).lstrip("\\").split()
    return names[0] if names else ""


def shape(module):
    params = module.get("parameter_default_values", {})
    return number(params["WIDTH"]), number(params["DEPTH"])


def logical_banks(netlist, top=TOP):
    """Count instantiated banks through hierarchy, never module definitions."""
    modules = netlist["modules"]
    found = []

    def visit(name, prefix, stack):
        if name in stack:
            raise ValueError("recursive design hierarchy")
        module = modules[name]
        if hdlname(module) == "kwt_sram_bank":
            width, depth = shape(module)
            found.append({"path": prefix, "width": width, "depth": depth,
                          "logical_bits": width * depth})
        for cellname, cell in module.get("cells", {}).items():
            typ = cell["type"]
            if typ in modules and not number(modules[typ].get("attributes", {}).get("blackbox", 0)):
                visit(typ, prefix + "." + cellname, stack + (name,))

    visit(top, top, ())
    actual = Counter((x["width"], x["depth"]) for x in found)
    if actual != LOGICAL:
        raise ValueError("logical bank inventory differs from accepted 20-bank layout: " + str(actual))
    return found


def inspect_structure(netlist, top=TOP):
    modules = netlist["modules"]
    module = modules[top]
    if module.get("memories"):
        raise ValueError("payload arrays remain in full top")
    boxes, multipliers, register_bits = [], [], 0
    counts = Counter()
    for name, cell in module.get("cells", {}).items():
        typ = cell["type"]
        counts[typ] += 1
        if typ.startswith("$mem"):
            raise ValueError("memory was not replaced by opaque primitives: " + name)
        target = modules.get(typ, {})
        if number(target.get("attributes", {}).get("blackbox", 0)):
            if hdlname(target) != "kwt_sram_1rw_blackbox":
                raise ValueError("unexpected unresolved blackbox: " + typ)
            width, depth = shape(target)
            boxes.append({"path": name, "type": typ, "width": width, "depth": depth,
                          "configured_bits": width * depth})
        elif typ in modules:
            raise ValueError("unexpected unflattened implementation module: " + typ)
        if typ == "$mul":
            p = cell["parameters"]
            item = tuple(number(p[k]) for k in ("A_WIDTH", "B_WIDTH", "Y_WIDTH", "A_SIGNED", "B_SIGNED"))
            multipliers.append(item)
        if typ.startswith(("$dff", "$adff", "$sdff")):
            register_bits += number(cell["parameters"]["WIDTH"])
    actual = Counter((x["width"], x["depth"]) for x in boxes)
    if actual != PHYSICAL:
        raise ValueError("opaque primitive inventory differs from 72 x 16-bit layout: " + str(actual))
    if len(multipliers) != 16 or any(x != (16, 16, 32, 1, 1) for x in multipliers):
        raise ValueError("expected exactly sixteen signed 16x16-to32 multipliers")
    # The payload is 415744 bits. This guard catches silent FF lowering even
    # if a mistaken source list leaves some unrelated boxes in the design.
    if register_bits >= 16384:
        raise ValueError("unexpectedly large non-memory register count; inspect possible FF expansion")
    return {"opaque_cells": boxes, "opaque_cell_count": len(boxes),
            "configured_memory_bits": sum(x["configured_bits"] for x in boxes),
            "configured_memory_KiB": sum(x["configured_bits"] for x in boxes) / 8192,
            "logical_memory_bits": sum(w*d*n for (w, d), n in LOGICAL.items()),
            "multipliers": len(multipliers), "register_bits_excluding_opaque_memory": register_bits,
            "cell_types": dict(sorted(counts.items())),
            "memory_array_cells": 0, "memory_to_ff_expansion": "NOT_PRESENT"}


def mapped_logic(netlist, expected_types, areas, top=TOP):
    module = netlist["modules"][top]
    counts = Counter(c["type"] for c in module["cells"].values())
    boxes = {k: v for k, v in counts.items() if k in expected_types}
    logic = {k: v for k, v in counts.items() if k not in boxes and k != "$scopeinfo"}
    unresolved = {k: v for k, v in logic.items() if k not in areas}
    if unresolved:
        raise ValueError("unmapped logic cells: " + json.dumps(unresolved, sort_keys=True))
    if sum(boxes.values()) != 72:
        raise ValueError("opaque memory lost or replicated during technology mapping")
    if module.get("memories") or any(k.startswith("$mem") for k in counts):
        raise ValueError("unexpected memory cell after logic mapping")
    total = sum((areas[k]*v for k, v in logic.items()), Decimal(0))
    return {"standard_cells": sum(logic.values()), "cell_types": dict(sorted(logic.items())),
            "opaque_cells_excluded": boxes, "opaque_cell_count": sum(boxes.values()),
            "logic_area_um2": float(total), "logic_area_mm2": float(total / Decimal(1000000)),
            "area_scope": ("Nangate45 accelerator plus new ICB adapter standard cells; includes bank decode/mux; excludes all SRAM and reused E203/shared SRAM"
                           if top == "kwt_icb_slave_sram" else
                           "Nangate45 core standard cells around opaque SRAM, including bank decode/mux; excludes all SRAM and E203 interface"),
            "sram_area_mm2": None, "official_incremental_area_mm2": None,
            "official_area_requirement": "BLOCKED"}


def completed(command, path, marker, buffered=False):
    log = path.read_text()
    count = len(re.findall("^" + re.escape(marker) + "$", log, re.M))
    internal_error=re.search(r'^\s*(?:ABC:\s*)?(?:ERROR|FAIL|FATAL)\b',log,re.M|re.I)
    abc_count=len(re.findall(r'^\s*ABC:\s*'+re.escape(ABC_MARKER)+r'\s*$',log,re.M))
    if (command["exit_code"] or command["timed_out"] or count != 1 or "End of script." not in log or
        internal_error or (buffered and abc_count!=1)):
        raise RuntimeError("Yosys failed/timed out/incomplete: " + str(path))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-logic", action="store_true", help="also map surrounding logic to audited Nangate45")
    parser.add_argument("--include-interface", action="store_true", help="use kwt_icb_slave_sram top to include the new ICB adapter")
    parser.add_argument("--buffered-reference", action="store_true", help="enable ABC buffer/upsize/dnsize with explicit reference drive/load assumptions")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    if args.buffered_reference and not args.map_logic:
        parser.error("--buffered-reference requires --map-logic")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out = (args.output_dir or ROOT/"artifacts/runs"/(stamp+"-sram-blackbox-"+uuid.uuid4().hex[:8])).resolve()
    out.mkdir(parents=True, exist_ok=False)
    top = "kwt_icb_slave_sram" if args.include_interface else TOP
    sources = [ROOT/"src/rtl"/(TOP+".sv"), ROOT/"src/rtl/memory/kwt_sram_bank.sv",
               ROOT/"src/rtl/memory/kwt_sram_1rw.sv", ROOT/"src/rtl/memory/kwt_sram_1rw_blackbox.sv"]
    if args.include_interface:
        sources.append(ROOT/"soc/kwt_icb_slave_sram.sv")
    yosys = ROOT/".tools/bin/yosys"
    lib = ROOT/"ChipContest/assets/libs/nangate45/NangateOpenCellLibrary_typical.lib"
    result = {"schema": "kwt-sram-blackbox-v1", "status": "FAIL", "run_directory": str(out),
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "full rowpair engine"+(" plus new ICB adapter" if args.include_interface else "")+", SRAM_BACKEND=1, 72 opaque 16-bit primitives",
              "configuration": {"top": top, "include_interface": args.include_interface, "pipe_mul": 1, "result_buffers": 2,
                                "sram_backend": "BLACKBOX", "mapping_profile": "fast-buffered-reference" if args.buffered_reference else "fast-unbuffered-reference"},
              "blackbox_structure": "NOT_RUN", "reference_logic_mapping": "NOT_RUN",
              "full_system_timing": "BLOCKED", "local_static_timing": "NOT_RUN",
              "timing_limitation": "No SRAM Liberty timing arcs; blackbox-to/from-macro paths are not fully evaluable. ABC target is not STA.",
              "official_ppa": "BLOCKED", "sram_area_mm2": None, "sram_power_mW": None,
              "power": "NOT_RUN", "functional_simulation": "NOT_APPLICABLE_BLACKBOX",
              "inputs": [], "commands": []}
    try:
        backend=SOURCES.select_backend('blackbox','synthesis')
        sources=backend['sources']+([ROOT/'soc/kwt_icb_slave_sram.sv'] if args.include_interface else [])
        paths = sources + backend['dependencies'] + [Path(__file__), Path(__file__).with_name("run_structural.py"),
                           Path(__file__).with_name("run_nangate_reference.py"), yosys,
                           ROOT/".tools/synth/usr/bin/yosys", ROOT/".tools/synth/usr/bin/yosys-abc"]
        if args.map_logic:
            paths.append(lib)
        result["inputs"] = [record(p) for p in paths]
        for index, source in enumerate(sources):
            (out/f"input-{index}.sv").write_bytes(source.read_bytes())
        prep = out/"prepare.ys"
        parameters = (f"chparam -set SRAM_BACKEND 1 {top}" if args.include_interface else
                      f"chparam -set SRAM_BACKEND 1 -set SRAM_CHECKS 0 -set PIPE_MUL 1 -set RESULT_BUFFERS 2 {top}")
        prep.write_text("\n".join([
            "read_verilog -sv -defer -D SYNTHESIS " + " ".join(f"input-{i}.sv" for i in range(len(sources))),
            parameters,
            f"hierarchy -check -top {top}", "proc", "opt", "memory_dff", "memory_collect", "opt_clean",
            "check -assert", "write_json hierarchical.json", "flatten", "opt_clean", "check -assert",
            "stat -width", "write_json blackbox-structure.json", "log "+PREP_MARKER, ""]))
        lock_path = ROOT/".tools/synth/structural.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("another EDA run owns synthesis lock") from exc
            version = run_command([str(yosys), "-V"], out, out/"version.log", 15)
            result["commands"].append(version)
            if version["exit_code"] or version["timed_out"]:
                raise RuntimeError("Yosys version probe failed")
            result["tool_version"] = (out/"version.log").read_text().strip()
            command = run_command([str(yosys), "-Q", "-s", "prepare.ys"], out, out/"prepare.log", args.timeout)
            result["commands"].append(command)
            completed(command, out/"prepare.log", PREP_MARKER)
            result["logical_banks"] = logical_banks(json.loads((out/"hierarchical.json").read_text()), top)
            structure = json.loads((out/"blackbox-structure.json").read_text())
            result["structure"] = inspect_structure(structure, top)
            result["blackbox_structure"] = "PASS"
            if args.map_logic:
                if record(lib)["sha256"] != LIB_SHA256:
                    raise ValueError("Nangate45 Liberty differs from audited SHA256")
                areas = library_areas(lib.read_text())
                result["reference_library"] = {"name": "NangateOpenCellLibrary_typical", "corner": "typical",
                    "voltage_V": 1.10, "temperature_C": 25, "official_competition_library": False,
                    "sram_liberty": "MISSING", "abc_target_ps": 6667, "abc_target_is_sta": False}
                constr = ""
                if args.buffered_reference:
                    (out/"abc.constr").write_text("set_driving_cell BUF_X2\nset_load 10\n")
                    # ABC buffer refuses dangling mapped nodes and can still
                    # return native exit 0. Clean after map; require the final
                    # inner marker as well as Yosys output and completion.
                    (out/"mapping.abc").write_text("\n".join([
                        "strash", "dretime", "retime -o -D 6667", "map -D 6667",
                        "cleanup", "buffer", "upsize -D 6667", "dnsize -D 6667",
                        "stime -p", "echo "+ABC_MARKER, ""]))
                    constr = " -constr abc.constr -script mapping.abc"
                    result["abc_boundary_assumptions"] = {"driving_cell": "BUF_X2", "output_load_fF": 10,
                        "scope": "development mapping assumption at every ABC boundary, not official macro capacitance or full SDC",
                        "enabled_script_steps": ["cleanup", "buffer", "upsize", "dnsize", "stime -p"],
                        "cleanup_basis": "actual-network buffer dangling-node failure; preserves observable logic"}
                quoted = '"'+str(lib).replace('\\', '\\\\').replace('"', '\\"')+'"'
                (out/"map.ys").write_text("\n".join([
                    "read_json blackbox-structure.json",
                    # Yosys 0.33 can reuse internal auto IDs after importing a
                    # flattened hierarchy from JSON. Give private objects safe
                    # names before techmap; ports and cell types stay unchanged.
                    "rename -enumerate -pattern kwt_internal_%_",
                    "read_liberty -lib "+quoted,
                    "hierarchy -check -top "+top, "synth -top "+top+" -noabc",
                    "dfflibmap -liberty "+quoted, "abc -fast -D 6667 -liberty "+quoted+constr,
                    "clean", "check -assert", "stat -liberty "+quoted,
                    "write_verilog -noattr -noexpr mapped.v", "write_json mapped.json", "log "+MAP_MARKER, ""]))
                mapped = run_command([str(yosys), "-Q", "-s", "map.ys"], out, out/"mapping.log", args.timeout)
                result["commands"].append(mapped)
                completed(mapped, out/"mapping.log", MAP_MARKER, args.buffered_reference)
                box_types = {x["type"] for x in result["structure"]["opaque_cells"]}
                result["mapped_logic"] = mapped_logic(json.loads((out/"mapped.json").read_text()), box_types, areas, top)
                result["reference_logic_mapping"] = "PASS"
        for item in result["inputs"]:
            if record(item["path"])["sha256"] != item["sha256"]:
                raise RuntimeError("input changed during run: "+item["path"])
        result["status"] = "PASS"
    except Exception as exc:
        result["error"] = type(exc).__name__+": "+str(exc)
    result["outputs"] = [record(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != "result.json"]
    (out/"result.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"status": result["status"], "report": str(out/"result.json"),
                      "blackbox_structure": result["blackbox_structure"],
                      "reference_logic_mapping": result["reference_logic_mapping"],
                      "error": result.get("error")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
