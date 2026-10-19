#!/usr/bin/env python3
"""Reference Nangate45 logic mapping with payload RAM cut at explicit ports.

This maps logic surrounding logical memories, not SRAM macros or a complete SoC.
No clock closure, physical area qualification or power result is claimed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import json
from pathlib import Path
import re
import sys
import uuid

from run_structural import integer, lower_casts, record, run_command, summarize

ROOT = Path(__file__).resolve().parents[2]
LIB_SHA256 = "8d540a4d4cf6d09d27c87ad067857a9c0c2eeb023ab7a56e058cd3113db4e9b1"
PREP_MARKER = "KWT_NANGATE_PREPARE_COMPLETE"
MAP_MARKER = "KWT_NANGATE_LOGIC_MAPPING_COMPLETE"
AREA_SOURCE = "https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD-flow-scripts/master/flow/platforms/nangate45/lef/NangateOpenCellLibrary.macro.lef"


def cut_memories(netlist, top):
    """Expose both directions of each collected RAM; retain surrounding logic.

    RD_DATA becomes a top input. Every request/control/write-data RAM input
    becomes a top output, so the optimizer cannot remove address/enable logic.
    Absorbed memory read registers remain inside the removed memory boundary.
    """
    cut = deepcopy(netlist)
    if set(cut["modules"]) != {top}:
        raise ValueError("require one elaborated module before cutting memories")
    module = cut["modules"][top]
    if module.get("memories"):
        raise ValueError("uncollected memory remains in input JSON")
    boundaries = []
    for name, cell in sorted(list(module["cells"].items())):
        if cell["type"] != "$mem_v2":
            if cell["type"].startswith("$mem"):
                raise ValueError("unsupported memory cell: "+cell["type"])
            continue
        params = cell["parameters"]
        ports = cell["port_directions"]
        connections = cell["connections"]
        if set(ports) != set(connections) or set(k for k, d in ports.items() if d == "output") != {"RD_DATA"}:
            raise ValueError("unexpected collected memory port directions")
        boundary = {"original_name": name,
                    "width": integer(params["WIDTH"]), "words": integer(params["SIZE"]),
                    "read_ports": integer(params["RD_PORTS"]),
                    "write_ports": integer(params["WR_PORTS"]),
                    "address_bits": integer(params["ABITS"]),
                    "read_clock_enable_mask": integer(params["RD_CLK_ENABLE"]),
                    "write_clock_enable_mask": integer(params["WR_CLK_ENABLE"]),
                    "read_transparency_mask": integer(params["RD_TRANSPARENCY_MASK"]),
                    "read_collision_x_mask": integer(params["RD_COLLISION_X_MASK"]),
                    "exposed_ports": []}
        boundary["bits"] = boundary["width"] * boundary["words"]
        for port, direction in sorted(ports.items()):
            bits = connections[port]
            if direction not in ("input", "output") or not bits:
                raise ValueError("empty/unrecognized memory port")
            if direction == "output" and (not all(isinstance(b, int) for b in bits) or len(set(bits)) != len(bits)):
                raise ValueError("unexpected memory data output alias/constant")
            port_name = f"ref_mem_{len(boundaries):03d}_{port.lower()}"
            if port_name in module["ports"] or port_name in module["netnames"]:
                raise ValueError("generated boundary port name collision")
            new_direction = "input" if direction == "output" else "output"
            module["ports"][port_name] = {"direction": new_direction, "bits": bits}
            module["netnames"][port_name] = {"hide_name": 0, "bits": bits, "attributes": {}}
            boundary["exposed_ports"].append({"name": port_name, "memory_port": port,
                                             "direction": new_direction, "width": len(bits)})
        del module["cells"][name]
        boundaries.append(boundary)
    if not boundaries:
        raise ValueError("no payload memories found; refuse an accidental FF-expanded area run")
    if any(c["type"].startswith("$mem") for c in module["cells"].values()):
        raise ValueError("memory cell remains after cut")
    return cut, boundaries


def library_areas(text):
    """Read this pinned Liberty's per-cell area without a nested-block parser."""
    headers = list(re.finditer(r"^\s*cell\s*\(\s*([\w]+)\s*\)\s*\{", text, re.M))
    result = {}
    for index, header in enumerate(headers):
        end = headers[index+1].start() if index+1 < len(headers) else len(text)
        values = re.findall(r"^\s*area\s*:\s*([\d.+eE-]+)\s*;", text[header.end():end], re.M)
        name = header.group(1)
        if len(values) != 1 or name in result:
            raise ValueError("nonunique/missing library cell area: "+name)
        area = Decimal(values[0])
        if not area.is_finite() or area <= 0:
            raise ValueError("invalid area for "+name)
        result[name] = area
    if len(result) != 135:
        raise ValueError("pinned library cell count changed")
    # These match the published LEF AND2_X1 geometry 0.76 x 1.4 um.
    if result.get("AND2_X1") != Decimal("1.064000"):
        raise ValueError("reference area unit cross-check failed")
    return result


def measured_logic(netlist, top, areas):
    module = netlist["modules"][top]
    if module.get("memories"):
        raise ValueError("unexpected retained memory after mapping")
    counts = Counter(cell["type"] for cell in module["cells"].values())
    # Metadata emitted by newer Yosys versions is not hardware. This local
    # 0.33 flow normally emits none; all actual unmapped hardware is rejected.
    metadata = {k: v for k, v in counts.items() if k == "$scopeinfo"}
    hardware = {k: v for k, v in counts.items() if k not in metadata}
    unresolved = {k: v for k, v in hardware.items() if k not in areas}
    if unresolved:
        raise ValueError("unresolved/unmapped hardware cells: "+json.dumps(unresolved, sort_keys=True))
    total = sum((areas[k] * v for k, v in hardware.items()), Decimal(0))
    return {"cells": sum(hardware.values()), "cell_types": dict(sorted(hardware.items())),
            "unresolved_hardware_cells": {}, "excluded_metadata_cells": metadata,
            "logic_area_library_units": str(total), "logic_area_um2": float(total),
            "logic_area_mm2": float(total / Decimal(1000000)),
            "area_units_basis": "Pinned Nangate AND2_X1 area=1.064 matches published LEF SIZE 0.76 BY 1.4 um",
            "area_units_primary_source": AREA_SOURCE}


def check_completed(command, logfile, marker):
    log = logfile.read_text()
    count = len(re.findall(r"^"+re.escape(marker)+r"$", log, re.M))
    if command["exit_code"] != 0 or command["timed_out"] or count != 1 or "End of script." not in log:
        raise RuntimeError("Yosys failed/timed out/lacks complete unique end marker: "+str(logfile))
    return count


def self_test():
    """Fail-closed boundary tests; no synthesis process or user data involved."""
    from unittest import TestCase, TextTestRunner, TestLoader

    class BoundaryTests(TestCase):
        def fixture(self):
            params = {"WIDTH": 16, "SIZE": 128, "ABITS": 7, "RD_PORTS": 1, "WR_PORTS": 1,
                      "RD_CLK_ENABLE": 1, "WR_CLK_ENABLE": 1, "RD_TRANSPARENCY_MASK": 0,
                      "RD_COLLISION_X_MASK": 0}
            mem = {"type": "$mem_v2", "parameters": params,
                   "port_directions": {"RD_DATA": "output", "WR_DATA": "input", "WR_EN": "input"},
                   "connections": {"RD_DATA": list(range(2,18)), "WR_DATA": list(range(18,34)), "WR_EN": [34]}}
            return {"modules": {"top": {"ports": {}, "netnames": {}, "cells": {"ram": mem}}}}

        def test_directions_and_original_immutable(self):
            original = self.fixture()
            new, boundaries = cut_memories(original, "top")
            self.assertIn("ram", original["modules"]["top"]["cells"])
            self.assertFalse(new["modules"]["top"]["cells"])
            self.assertEqual(boundaries[0]["bits"], 2048)
            ports = new["modules"]["top"]["ports"]
            self.assertEqual(ports["ref_mem_000_rd_data"]["direction"], "input")
            self.assertEqual(ports["ref_mem_000_wr_data"]["direction"], "output")
            self.assertEqual(ports["ref_mem_000_wr_en"]["bits"], [34])

        def test_reject_no_memory(self):
            fixture = self.fixture()
            fixture["modules"]["top"]["cells"] = {}
            with self.assertRaises(ValueError):
                cut_memories(fixture, "top")

        def test_reject_data_alias(self):
            fixture = self.fixture()
            fixture["modules"]["top"]["cells"]["ram"]["connections"]["RD_DATA"] = [2,2]
            with self.assertRaises(ValueError):
                cut_memories(fixture, "top")

        def test_reject_unknown_port(self):
            fixture = self.fixture()
            fixture["modules"]["top"]["cells"]["ram"]["port_directions"]["WR_EN"] = "inout"
            with self.assertRaises(ValueError):
                cut_memories(fixture, "top")

        def test_reject_unmapped_hardware(self):
            fixture = self.fixture()
            with self.assertRaises(ValueError):
                measured_logic(fixture, "top", {"DFF_X1": Decimal("4.522")})

        def test_area_sum_and_metadata(self):
            fixture = self.fixture()
            fixture["modules"]["top"]["cells"] = {"a": {"type": "DFF_X1"}, "b": {"type": "$scopeinfo"}}
            got = measured_logic(fixture, "top", {"DFF_X1": Decimal("4.522")})
            self.assertEqual(got["logic_area_library_units"], "4.522")
            self.assertEqual(got["cells"], 1)
            self.assertEqual(got["logic_area_mm2"], 0.000004522)

    return 0 if TextTestRunner(verbosity=2).run(TestLoader().loadTestsFromTestCase(BoundaryTests)).wasSuccessful() else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("baseline", "opt", "banked", "rowpair"), default="rowpair")
    parser.add_argument("--lanes", type=int, choices=(8,16), default=8)
    parser.add_argument("--pipe-mul", type=int, choices=(0,1), default=1)
    parser.add_argument("--result-buffers", type=int, choices=(1,2), default=2)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--prepare-only", action="store_true", help="Elaborate/cut RAM only; do not invoke ABC")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.timeout <= 0 or (args.variant == "rowpair" and args.lanes != 8):
        parser.error("timeout must be positive; rowpair is fixed 2x8 MACs")
    top = {"baseline": "kwt_linear_engine", "opt": "kwt_linear_engine_opt",
           "banked": "kwt_linear_engine_banked", "rowpair": "kwt_linear_engine_rowpair"}[args.variant]
    source = ROOT/"src/rtl"/(top+".sv")
    lib = ROOT/"ChipContest/assets/libs/nangate45/NangateOpenCellLibrary_typical.lib"
    yosys = ROOT/".tools/bin/yosys"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out = (args.output_dir or ROOT/"artifacts/runs"/(stamp+"-nangate-reference-"+uuid.uuid4().hex[:8])).resolve()
    out.mkdir(parents=True, exist_ok=False)
    result = {"schema": "kwt-nangate-reference-v1", "status": "FAIL", "run_directory": str(out),
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "reference-Nangate45 logical-memory-boundary standard-cell area only",
              "configuration": {"variant": args.variant, "top": top,
                                "lanes": args.lanes, "rows_parallel": 2 if args.variant == "rowpair" else 1,
                                "pipe_mul": 0 if args.variant == "baseline" else args.pipe_mul,
                                "result_buffers": args.result_buffers if args.variant == "rowpair" else None},
              "abc_delay_target_ps": 6667, "abc_delay_is_sta": False,
              "sram_area": "NOT_INCLUDED", "physical_macro_mapping": "NOT_RUN",
              "new_soc_interface_area": "NOT_INCLUDED", "physical_macro_decode_and_output_mux": "NOT_INCLUDED",
              "static_timing": "NOT_RUN", "power": "NOT_RUN", "mapped_equivalence": "NOT_RUN", "soc": "NOT_RUN",
              "official_ppa": "BLOCKED", "inputs": [], "commands": [], "outputs": []}
    try:
        result["inputs"] = [record(p) for p in (source, Path(__file__), ROOT/"scripts/synth/run_structural.py",
                            lib, yosys, ROOT/".tools/synth/usr/bin/yosys", ROOT/".tools/synth/usr/bin/yosys-abc")]
        if record(lib)["sha256"] != LIB_SHA256:
            raise ValueError("reference Liberty differs from audited SHA256")
        lib_text = lib.read_text()
        if not re.search(r'time_unit\s*:\s*"1ns"', lib_text):
            raise ValueError("unexpected pinned library timing unit")
        areas = library_areas(lib_text)
        result["reference_pvt"] = {"corner": "typical/TypTyp", "voltage_V": 1.10,
                                   "temperature_C": 25, "library_time_unit": "1ns", "library_cells": len(areas)}
        lowered, adaptation = lower_casts(source.read_text())
        (out/"input.sv").write_text(lowered)
        result["source_adaptation"] = dict(adaptation, derived=record(out/"input.sv"))
        params = []
        if args.variant != "rowpair":
            params += ["-set", "LANES", str(args.lanes)]
        if args.variant != "baseline":
            params += ["-set", "PIPE_MUL", str(args.pipe_mul)]
        if args.variant == "rowpair":
            params += ["-set", "RESULT_BUFFERS", str(args.result_buffers)]
        (out/"prepare.ys").write_text("\n".join([
            "read_verilog -sv -defer input.sv", "chparam "+" ".join(params)+" "+top,
            "hierarchy -check -top "+top, "proc", "opt", "memory_dff", "memory_collect",
            "opt_clean", "check -assert", "write_json structure.json", "log "+PREP_MARKER, ""]))
        lock_path = ROOT/".tools/synth/structural.lock"
        with lock_path.open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("another synthesis owns project lock; retry after that run completes") from exc
            version = run_command([str(yosys), "-V"], out, out/"version.log", 15)
            result["commands"].append(version)
            if version["exit_code"] != 0 or version["timed_out"]:
                raise RuntimeError("Yosys version query failed")
            prepare = run_command([str(yosys), "-Q", "-s", "prepare.ys"], out, out/"prepare.log", args.timeout)
            result["commands"].append(prepare)
            result["prepare_marker_count"] = check_completed(prepare, out/"prepare.log", PREP_MARKER)
            structural = json.loads((out/"structure.json").read_text())
            result["structure_before_cut"] = summarize(structural, top)
            expected_bits = 373760 + (512*41*args.result_buffers if args.variant == "rowpair" else 0)
            if result["structure_before_cut"]["memory_bits"] != expected_bits:
                raise ValueError("unexpected memory payload bits; possible expansion or omitted memory")
            cut, boundaries = cut_memories(structural, top)
            (out/"logic-boundary.json").write_text(json.dumps(cut, indent=2)+"\n")
            result["memory_boundaries"] = boundaries
            result["removed_memory_bits"] = sum(m["bits"] for m in boundaries)
            result["boundary_semantics"] = (
                "RAM RD_DATA is independent top input; every RAM request/control/write-data input is a top output. "
                "Memory-internal output registers, data retention/read-hold logic, physical macro cascading and any "
                "physical port adaptation are excluded. Result is a reference logic experiment, not total accelerator area.")
            if not args.prepare_only:
                # Escaped spaces are avoided by Yosys quoting an absolute path.
                quoted_lib = '"'+str(lib).replace('\\','\\\\').replace('"','\\"')+'"'
                (out/"map.ys").write_text("\n".join([
                    "read_json logic-boundary.json", "read_liberty -lib "+quoted_lib,
                    "hierarchy -check -top "+top, "synth -top "+top+" -noabc",
                    "dfflibmap -liberty "+quoted_lib,
                    "abc -D 6667 -liberty "+quoted_lib,
                    "clean", "check -assert", "stat -liberty "+quoted_lib,
                    "tee -o mapped-stat.json stat -json -liberty "+quoted_lib,
                    "write_verilog -noattr -noexpr mapped.v", "write_json mapped.json", "log "+MAP_MARKER, ""]))
                mapped = run_command([str(yosys), "-Q", "-s", "map.ys"], out, out/"mapping.log", args.timeout)
                result["commands"].append(mapped)
                result["mapping_marker_count"] = check_completed(mapped, out/"mapping.log", MAP_MARKER)
                result["mapped_logic"] = measured_logic(json.loads((out/"mapped.json").read_text()), top, areas)
                # Independently reconcile actual mapped cell count/Liberty area
                # with Yosys's own final report; repeated stat emits same value.
                reported = re.findall(r"Chip area for (?:top )?module ['\\]*"+re.escape(top)+r"['\\]*:\s*([\d.]+)", (out/"mapping.log").read_text())
                if not reported:
                    raise ValueError("mapped log lacks Yosys top area for reconciliation")
                actual = Decimal(result["mapped_logic"]["logic_area_library_units"])
                if any(abs(Decimal(v)-actual) > Decimal("0.00001") for v in reported):
                    raise ValueError("mapped cell area sum differs from Yosys report")
                result["mapped_logic"]["yosys_reported_areas"] = reported
                result["reference_logic_mapping"] = "PASS"
            else:
                result["scope"] = "reference memory-cut preparation only; no cell area measured"
                result["reference_logic_mapping"] = "NOT_RUN"
        result["outputs"] = [record(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != "result.json"]
        for item in result["inputs"]:
            if record(item["path"])["sha256"] != item["sha256"]:
                raise RuntimeError("input changed while mapping: "+item["path"])
        result["status"] = "PASS"
    except Exception as exc:
        result["error"] = type(exc).__name__+": "+str(exc)
    (out/"result.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"status": result["status"], "report": str(out/"result.json"),
                      "scope": result["scope"], "mapped_logic": result.get("mapped_logic"),
                      "error": result.get("error")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
