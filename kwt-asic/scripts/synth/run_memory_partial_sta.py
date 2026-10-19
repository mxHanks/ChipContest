#!/usr/bin/env python3
"""Reference STA of mapped standard logic with SRAM explicitly cut at ports.

SRAM boundary paths are intentionally not given invented timing budgets. This
reports covered register/ordinary-I/O paths and unmodeled boundaries separately;
even positive reference slack never qualifies complete competition timing.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import re
import uuid

from run_structural import ROOT, record, run_command
from run_memory_blackbox import TOP, LIB_SHA256

MARKER = "KWT_SRAM_PARTIAL_STA_COMPLETE"


def reference_wire_load(liberty_text):
    defaults=re.findall(r'\bdefault_wire_load\s*:\s*"([^"]+)"\s*;',liberty_text)
    if len(defaults)!=1 or not re.search(r'\bwire_load\s*\(\s*"?'+re.escape(defaults[0])+r'"?\s*\)',liberty_text):
        raise ValueError('missing or ambiguous reference library wire-load model')
    return defaults[0]


def accept_sta_log(command,log):
    if (command['exit_code'] or command['timed_out'] or
        len(re.findall('^'+MARKER+'$',log,re.M))!=1 or
        re.search(r'^\s*(?:%?ERROR|FATAL|FAIL)\b',log,re.M|re.I)):
        raise RuntimeError('OpenSTA failed/incomplete; inspect sta.log')


def minimum_categories(text):
    blocks=text.split('Startpoint:')[1:]
    if not blocks:raise ValueError('no minimum timing paths reported')
    categories={}
    for block in blocks:
        slacks=re.findall(r'(-?\d+(?:\.\d+)?)\s+slack \(',block)
        endpoint=re.search(r'^Endpoint:\s*(\S+)',block,re.M)
        if len(slacks)!=1 or not endpoint:raise ValueError('truncated minimum timing path')
        kind=('removal' if 'library removal time' in block else
              'hold' if 'library hold time' in block else 'external_or_other_minimum')
        value=float(slacks[0])
        item=categories.setdefault(kind,{'reported_paths':0,'reported_endpoints':set(),'worst_slack_ns':value})
        item['reported_paths']+=1;item['reported_endpoints'].add(endpoint[1])
        item['worst_slack_ns']=min(item['worst_slack_ns'],value)
    for item in categories.values():item['reported_endpoints']=len(item['reported_endpoints'])
    return categories


def timing_metrics(log,min_text,data_min_text):
    result={}
    for key,pattern in (('reference_wns_ns',r'^wns\s+(-?\d+(?:\.\d+)?)\s*$'),
                        ('reference_tns_ns',r'^tns\s+(-?\d+(?:\.\d+)?)\s*$'),
                        ('reference_worst_slack_ns',r'^worst slack\s+(-?\d+(?:\.\d+)?)\s*$')):
        found=re.findall(pattern,log,re.M)
        if len(found)!=1:raise ValueError('missing or duplicate STA metric: '+key)
        result[key]=float(found[0])
    categories=minimum_categories(min_text)
    data=minimum_categories(data_min_text)
    if 'hold' not in data:raise ValueError('no register data hold checks reported')
    minimum=min(x['worst_slack_ns'] for x in categories.values())
    result.update(minimum_check_categories=categories,reference_min_worst_slack_ns=minimum,
        reference_data_hold_worst_slack_ns=data['hold']['worst_slack_ns'],
        # Compatibility alias: old reports used this name for ALL min checks,
        # including removal. New consumers must use the explicit fields.
        reference_hold_worst_slack_ns=minimum,
        reference_hold_legacy_field_scope='all minimum checks, including reset removal',
        covered_path_status=('FAIL' if result['reference_wns_ns']<0 or result['reference_tns_ns']<0 or
            minimum<0 or data['hold']['worst_slack_ns']<0 else 'PASS_UNDER_REFERENCE_ASSUMPTIONS'))
    return result


def cut_boxes(netlist, types, top=TOP):
    cut = deepcopy(netlist)
    module = cut["modules"][top]
    boundaries = []
    for name, cell in sorted(list(module["cells"].items())):
        if cell["type"] not in types: continue
        ports = []
        directions = cell.get("port_directions", {})
        for port, bits in sorted(cell["connections"].items()):
            if port == "clk": continue
            if port not in directions or directions[port] not in ("input", "output"):
                raise ValueError("unsupported opaque macro port: "+port)
            direction = "input" if directions[port] == "output" else "output"
            new = f"sram_cut_{len(boundaries):03d}_{port}"
            if new in module["ports"] or new in module["netnames"]:
                raise ValueError("cut boundary name collision")
            module["ports"][new] = {"direction": direction, "bits": bits}
            module["netnames"][new] = {"hide_name": 0, "bits": bits, "attributes": {}}
            ports.append({"name": new, "macro_port": port, "direction": direction, "width": len(bits)})
        del module["cells"][name]
        boundaries.append({"opaque_instance": name, "ports": ports})
    if len(boundaries) != 72:
        raise ValueError("must cut exactly 72 known SRAM primitives")
    return cut, boundaries


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mapping-report", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--output-dir", type=Path)
    args = p.parse_args()
    if args.timeout <= 0: p.error("timeout must be positive")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out = (args.output_dir or ROOT/"artifacts/runs"/(stamp+"-sram-partial-sta-"+uuid.uuid4().hex[:8])).resolve()
    out.mkdir(parents=True, exist_ok=False)
    result = {"schema": "kwt-sram-partial-sta-v1", "status": "FAIL", "run_directory": str(out),
              "scope": "Nangate45 typical standard-logic STA; 72 SRAM boundaries intentionally unmodeled",
              "full_system_timing": "BLOCKED", "official_150mhz": "BLOCKED",
              "sram_timing": "UNMODELED", "sram_input_capacitance": "UNMODELED",
              "constraints": {"period_ns": 6.666666667, "clock_uncertainty_ns": .1,
                  "ordinary_io_max_delay_ns": .5, "ordinary_io_min_delay_ns": .1,
                  "ordinary_input_transition_ns": .1, "ordinary_output_load_fF": 10,
                  "wire_parasitics": "Liberty default statistical wire-load model; no placed/extracted parasitics", "clock": "ideal",
                  "basis": "explicit development assumptions; not official budgets",
                  "sram_boundary_delays": "NOT_SET; unconstrained, not assumed zero",
                  "reset_input_delays": "NOT_SET; reset recovery/removal not qualified",
                  "timing_exceptions": "NONE"}, "inputs": [], "commands": []}
    try:
        report_path = args.mapping_report.resolve()
        mapping = json.loads(report_path.read_text())
        if mapping.get("status") != "PASS" or mapping.get("reference_logic_mapping") != "PASS":
            raise ValueError("require successful full-engine blackbox mapping report")
        top = mapping["configuration"]["top"]
        if top not in (TOP, "kwt_icb_slave_sram"):
            raise ValueError("unsupported mapping top")
        result["configuration"] = mapping["configuration"]
        for item in mapping["inputs"]:
            if record(item["path"])["sha256"] != item["sha256"]:
                raise ValueError("mapping input has changed; remap before STA: "+item["path"])
        mapped_path = Path(mapping["run_directory"])/"mapped.json"
        recorded = {x["path"]:x for x in mapping["outputs"]}
        if str(mapped_path) not in recorded or record(mapped_path)["sha256"] != recorded[str(mapped_path)]["sha256"]:
            raise ValueError("mapped JSON differs from mapping evidence")
        sta = ROOT/".tools/opensta/usr/bin/sta"
        yosys = ROOT/".tools/bin/yosys"
        lib = ROOT/"ChipContest/assets/libs/nangate45/NangateOpenCellLibrary_typical.lib"
        if record(lib)["sha256"] != LIB_SHA256: raise ValueError("reference library SHA mismatch")
        wire_load=reference_wire_load(lib.read_text())
        result['constraints']['wire_load_model']=wire_load
        result["inputs"] = [record(x) for x in (report_path, mapped_path, sta, yosys, lib, Path(__file__))]
        netlist = json.loads(mapped_path.read_text())
        original = netlist["modules"][top]["ports"]
        ordinary_inputs = [n for n, v in original.items() if v["direction"] == "input" and n not in ("clk", "rst_n")]
        ordinary_outputs = [n for n, v in original.items() if v["direction"] == "output"]
        cut, boundaries = cut_boxes(netlist, set(mapping["mapped_logic"]["opaque_cells_excluded"]), top)
        result["unmodeled_boundaries"] = boundaries
        result["sram_boundary_port_count"] = sum(len(x["ports"]) for x in boundaries)
        (out/"boundary.json").write_text(json.dumps(cut)+"\n")
        (out/"write.ys").write_text("read_json boundary.json\nwrite_verilog -noattr -noexpr boundary.v\nlog KWT_SRAM_STA_NETLIST_COMPLETE\n")
        (out/"reference.sdc").write_text("\n".join([
            "create_clock -name core -period 6.666666667 [get_ports clk]",
            "set_wire_load_model -name "+wire_load,
            "set_clock_uncertainty 0.1 [get_clocks core]",
            "set_input_delay -clock core -max 0.5 [get_ports {"+" ".join(ordinary_inputs)+"}]",
            "set_input_delay -clock core -min 0.1 [get_ports {"+" ".join(ordinary_inputs)+"}]",
            "set_input_transition 0.1 [get_ports {"+" ".join(ordinary_inputs)+"}]",
            "set_output_delay -clock core -max 0.5 [get_ports {"+" ".join(ordinary_outputs)+"}]",
            "set_output_delay -clock core -min 0.1 [get_ports {"+" ".join(ordinary_outputs)+"}]",
            "set_load 10 [get_ports {"+" ".join(ordinary_outputs)+"}]", ""]))
        (out/"run.tcl").write_text("\n".join([
            "read_liberty {"+str(lib)+"}", "read_verilog boundary.v", "link_design "+top,
            "read_sdc reference.sdc", "check_setup -verbose > coverage.rpt",
            "report_checks -path_delay max -group_count 20 -digits 6 > setup.rpt",
            "report_checks -path_delay min -group_count 20 -digits 6 > hold.rpt",
            "report_checks -unconstrained -path_delay max -group_count 20 -digits 6 > unconstrained.rpt",
            "report_checks -from [all_registers -clock core -output_pins] -to [all_registers -clock core -data_pins] -path_delay max -group_count 20 -digits 6 > register_setup.rpt",
            "report_checks -from [all_registers -clock core -output_pins] -to [all_registers -clock core -data_pins] -path_delay min -group_count 20 -digits 6 > register_hold.rpt",
            "report_net -connections -verbose -digits 6 {u_engine.rst_n} > reset_net.rpt" if top=='kwt_icb_slave_sram' else "# core-only reset net separately unqualified",
            "report_checks -path_delay min -group_count 20 -fields {capacitance slew input_pin net} -digits 6 > minimum_electrical.rpt",
            "report_wns -digits 6", "report_tns -digits 6", "report_worst_slack -digits 6",
            'puts "'+MARKER+'"', "exit", ""]))
        with (ROOT/".tools/synth/structural.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            write = run_command([str(yosys), "-Q", "-s", "write.ys"], out, out/"write.log", args.timeout)
            result["commands"].append(write)
            if write["exit_code"] or write["timed_out"]: raise RuntimeError("cut netlist emission failed")
            version = run_command([str(sta), "-version"], out, out/"version.log", 15)
            result["commands"].append(version)
            result["tool_version"] = (out/"version.log").read_text().strip()
            run = run_command([str(sta), "-no_init", "-exit", "run.tcl"], out, out/"sta.log", args.timeout)
            result["commands"].append(run)
        log = (out/"sta.log").read_text()
        accept_sta_log(run,log)
        required = ("setup.rpt", "hold.rpt", "register_setup.rpt", "register_hold.rpt", "coverage.rpt", "unconstrained.rpt")
        if any(not (out/x).is_file() or not (out/x).stat().st_size for x in required):
            raise ValueError("missing/empty required STA report")
        result.update(timing_metrics(log,(out/'hold.rpt').read_text(),(out/'register_hold.rpt').read_text()))
        coverage = (out/"coverage.rpt").read_text()
        result["coverage_counts"] = {"inputs_missing_delay": 0, "outputs_missing_delay": 0, "unconstrained_endpoints": 0}
        for key, pattern in (("inputs_missing_delay",r"There are (\d+) input ports missing set_input_delay"),
                             ("outputs_missing_delay",r"There are (\d+) output ports missing set_output_delay"),
                             ("unconstrained_endpoints",r"There are (\d+) unconstrained endpoints")):
            match = re.search(pattern, coverage)
            if match: result["coverage_counts"][key] = int(match.group(1))
        expected_inputs = 1 + sum(p["width"] for b in boundaries for p in b["ports"] if p["direction"] == "input")
        expected_outputs = sum(p["width"] for b in boundaries for p in b["ports"] if p["direction"] == "output")
        if result["coverage_counts"] != {"inputs_missing_delay": expected_inputs,
                                         "outputs_missing_delay": expected_outputs,
                                         "unconstrained_endpoints": expected_outputs}:
            raise ValueError("coverage warnings do not match the explicit SRAM/reset cut inventory")
        if re.search(r"Warning:.*(?:no clock|combinational loop|multiple clock|generated clock)", coverage, re.I):
            raise ValueError("unexpected clock/loop coverage issue")
        result["constraint_coverage"] = "PARTIAL_BY_DESIGN; SRAM boundary and reset paths unqualified"
        if "Startpoint:" not in (out/"register_setup.rpt").read_text():
            raise ValueError("no register-to-register timing paths reported")
        for item in result["inputs"]:
            if record(item["path"])["sha256"] != item["sha256"]: raise ValueError("STA input changed")
        result["status"] = "PASS"
    except Exception as exc:
        result["error"] = type(exc).__name__+": "+str(exc)
    result["outputs"] = [record(x) for x in sorted(out.iterdir()) if x.is_file() and x.name != "result.json"]
    (out/"result.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"status":result["status"],"report":str(out/"result.json"),"reference_wns_ns":result.get("reference_wns_ns"),"full_system_timing":"BLOCKED","error":result.get("error")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())
