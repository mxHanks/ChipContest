#!/usr/bin/env python3
"""Generate, but never run, fresh actual48 baseline/Q-SP0/Q-SP1 PT cases.

Each case reuses the original fixture setup and all original annotations and
conditional queries. The Q overrides are hypothetical absolute annotations,
not measured Q activity. Run each generated Tcl in a separate fresh directory
and fresh PT process. Outer packaging/manifest validation belongs to the caller.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re


PREFIX = "pt-joint-state-condition-20261103-48/"
CASES = (("baseline", None), ("q-sp0-tr0", 0), ("q-sp1-tr0", 1))


def require(ok, message):
    if not ok:
        raise ValueError("Q absolute sweep preparation: " + message)


def brace(value):
    require(isinstance(value, str) and not any(c in value for c in "{}\\\t\r\n"),
            "unsafe Tcl literal")
    return "{" + value + "}"


SNAPSHOT_TCL = r'''
proc xu_q_sha {path} {
  if {![file isfile $path]} {error "missing regular input $path"}
  set answer [exec /usr/bin/sha256sum -- $path]
  if {![regexp {^([0-9a-f]{64})[ \t]} $answer -> sha]} {error {invalid sha256sum output}}
  return [list [file size $path] $sha]
}
proc xu_q_snapshot {phase} {
  set f [open "input-sha-$phase.tsv" {WRONLY CREAT EXCL}]
  puts $f "phase\tpath\tbytes\tsha256\texpected_sha256"
  set result [list]
  foreach spec [concat $::xu_q_frozen_inputs [list [list $::xu_q_self_script {}]]] {
    lassign $spec path expected
    lassign [xu_q_sha $path] bytes sha
    puts $f [join [list $phase $path $bytes $sha $expected] "\t"]
    if {$expected ne {} && $sha ne $expected} {close $f;error "frozen input SHA differs $path"}
    lappend result [list $path $bytes $sha]
  }
  close $f
  return $result
}
proc xu_q_activity {phase} {
  set f [open "all-macro-pin-activity-$phase.tsv" {WRONLY CREAT EXCL}]
  puts $f "case\tphase\tpin\tstatic_probability_raw\ttoggle_glitch_raw"
  set pins [get_pins -quiet -of_objects [get_cells m]]
  if {[sizeof_collection $pins] != 67} {error {fixture does not have 67 signal pins}}
  foreach_in_collection pin $pins {
    set name [get_object_name $pin]
    set sp [get_switching_activity -static_probability $pin]
    set tr [get_switching_activity -toggle_rate -glitch_rate $pin]
    foreach value [list $name $sp $tr] {
      if {[regexp {[\t\r\n]} $value]} {error {TSV control in activity query}}
    }
    puts $f [join [list $::xu_q_case $phase $name $sp $tr] "\t"]
  }
  close $f
  redirect -file "coverage-$phase.rpt" {report_switching_activity -list_not_annotated}
}
proc xu_q_request {phase} {
  foreach name $::xu_q_targets {
    puts $::xu_q_request_f [join [list $::xu_q_case $phase $name $::xu_q_requested_sp $::xu_q_requested_tr HYPOTHETICAL_ABSOLUTE_Q_SIDE_EFFECT_ONLY] "\t"]
  }
}
'''


def prepare(read_input):
    """Return {plan: JSON-compatible dict, files: {relative_name: bytes}}.

    read_input accepts export-relative names and returns bytes. This function
    reads three existing export files and only generates text; it does not
    inspect remote source paths, invoke a shell, or execute EDA or Tcl.
    """
    inputs = {}
    for name in ("query.tcl", "state.json", "fixture-power-diagnostic-only.rpt"):
        data = read_input(PREFIX + name)
        require(type(data) is bytes, "read_input must return bytes")
        inputs[name] = data
    query = inputs["query.tcl"].decode("utf-8")
    state = json.loads(inputs["state.json"])
    recorded = state["input_identities_before"]
    before = {item["path"]: item for item in recorded}
    require(len(before) == len(recorded), "duplicate before input path")
    original_query = [path for path in before if path.endswith("/" + PREFIX + "query.tcl")]
    require(len(original_query) == 1, "original query identity missing")
    require(hashlib.sha256(inputs["query.tcl"]).hexdigest() == before[original_query[0]]["sha256"]
            and len(inputs["query.tcl"]) == before[original_query[0]]["bytes"],
            "original query bytes differ from before identity")
    lines = query.splitlines()
    require(lines[0] == "if {[catch {", "original query wrapper differs")
    first_query = re.search(r"^xu_query \{before_update\}", query, re.MULTILINE)
    require(first_query is not None, "original before queries missing")
    # Preserve even literal control characters in the original query proc's
    # regex; splitlines/rejoin would silently alter its source.
    setup = query[query.index("\n") + 1:first_query.start()]
    annotations = [line for line in setup.splitlines() if line.startswith("set_switching_activity ")]
    require(len(annotations) == 84 and not any("m/Q[" in line for line in annotations),
            "original annotation inventory differs")
    before_queries = [line for line in lines if line.startswith("xu_query {before_update}")]
    after_queries = [line for line in lines if line.startswith("xu_query {after_update}")]
    require(len(before_queries) == len(after_queries) == 303, "conditional query counts differ")
    require([line.replace("{before_update}", "{after_update}", 1) for line in before_queries]
            == after_queries, "before/after query inventories differ")
    dbs = re.findall(r"\{([^{}\r\n]+\.db)\}", next(
        line for line in lines if line.startswith("set_app_var link_path ")))
    netlists = re.findall(r"^read_verilog \{([^{}\r\n]+)\}$", query, re.MULTILINE)
    projection_paths = [path for path in before
                        if path.endswith("/" + PREFIX + "measured-joint-projection.json")]
    require(len(dbs) == 2 and len(netlists) == len(projection_paths) == 1,
            "two DBs, one netlist and projection identity required")
    frozen_paths = dbs + netlists + original_query + projection_paths
    require(len(set(frozen_paths)) == 5 and all(path in before for path in frozen_paths),
            "fixture input is absent from recorded before identities")
    frozen = [before[path] for path in frozen_paths]
    frozen_tcl = "set xu_q_frozen_inputs [list " + " ".join(
        "[list %s %s]" % (brace(item["path"]), brace(item["sha256"])) for item in frozen
    ) + "]\n"
    files = {}
    case_plan = []
    for case, sp in CASES:
        body = "if {[catch {\nset xu_q_self_script [file normalize [info script]]]\n"
        body += frozen_tcl + SNAPSHOT_TCL
        body += "set xu_q_before [xu_q_snapshot before]\n" + setup
        body += "set xu_q_case " + brace(case) + "\n"
        body += "set xu_q_requested_sp " + brace("UNCHANGED" if sp is None else str(sp)) + "\n"
        body += "set xu_q_requested_tr " + brace("UNCHANGED" if sp is None else "0") + "\n"
        body += "set xu_q_targets [list]\n"
        body += '''for {set i 0} {$i < 16} {incr i} {
  set name [format {m/Q[%d]} $i]
  set pin [get_pins -quiet $name]
  if {[sizeof_collection $pin] != 1 || [get_object_name $pin] ne $name} {error {exact Q pin not found}}
  lappend xu_q_targets $name
'''
        if sp is not None:
            body += "  set_switching_activity -static_probability %d -toggle_rate 0 -glitch_rate 0 -period 524 -rise_ratio 0.5 $pin\n" % sp
        body += "}\n"
        body += "set xu_q_request_f [open q-absolute-request.tsv {WRONLY CREAT EXCL}]\n"
        body += 'puts $xu_q_request_f "case\\tphase\\tpin\\trequested_static_probability\\trequested_toggle_rate\\tpolicy"\n'
        body += "xu_q_request before\n" + "\n".join(before_queries) + "\nxu_q_activity before\n"
        body += '''redirect -file update-power.rpt {update_power}
redirect -file fixture-power-diagnostic-only.rpt {report_power -verbose}
if {[catch {redirect -file macro-power-diagnostic-only.rpt {
  puts {XU_Q_ABSOLUTE_FIXTURE_MACRO_ONLY_NOT_MEASURED_ZERO_OR_SOC_ENERGY}
  report_power -cell_power -nosplit -include_lib_cells [get_cells m]
}} xu_q_macro_report_error]} {
  set f [open macro-report-unavailable.rpt {WRONLY CREAT EXCL}]
  puts $f $xu_q_macro_report_error
  close $f
}
set f [open macro-power-attributes.rpt {WRONLY CREAT EXCL}]
puts $f {XU_Q_ABSOLUTE_MACRO_ATTRIBUTES_OPTIONAL_NOT_ENERGY_QUALIFIED}
foreach attribute {internal_power switching_power leakage_power total_power} {
  set status AVAILABLE
  if {[catch {get_attribute -quiet [get_cells m] $attribute} value]} {set status UNAVAILABLE}
  puts $f [list $attribute $status $value]
}
close $f
'''
        body += "\n".join(after_queries) + "\nxu_q_activity after\nxu_q_request after\nclose $xu_q_request_f\nclose $xu_f\n"
        body += '''set xu_q_after [xu_q_snapshot after]
if {$xu_q_before ne $xu_q_after} {error {input identity changed during fixture run}}
puts {XU_Q_ABSOLUTE_SWEEP_CASE_DONE_NOT_ZERO_Q_OR_ENERGY_QUALIFIED}
} xu_q_error]} {puts stderr "XU_Q_ABSOLUTE_SWEEP_REJECT $xu_q_error";exit 2}
exit
'''
        name = case + "/query.tcl"
        files[name] = body.encode("utf-8")
        case_plan.append(dict(
            case=case, query=name, query_sha256=hashlib.sha256(files[name]).hexdigest(),
            requested_Q_static_probability=sp, requested_Q_toggle_rate=None if sp is None else 0,
            Q_pin_count=16, original_annotation_count=84,
            original_conditional_query_rows_per_phase=303,
            fresh_process_and_case_directory_required=True,
        ))
    power_match = re.search(rb"^Total Power\s*=\s*([0-9.eE+-]+)",
                            inputs["fixture-power-diagnostic-only.rpt"], re.MULTILINE)
    require(power_match is not None, "original diagnostic power total missing")
    plan = dict(
        schema="xu-pt-q-absolute-sweep-generation-v1",
        status="GENERATED_NOT_RUN_NOT_ZERO_Q_OR_ENERGY_QUALIFIED",
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        source_export_prefix=PREFIX,
        reused_setup_sha256=hashlib.sha256(setup.encode("utf-8")).hexdigest(),
        source_files=[dict(path=PREFIX + name, bytes=len(data),
                           sha256=hashlib.sha256(data).hexdigest()) for name, data in inputs.items()],
        original_fixture_diagnostic_power_w=float(power_match.group(1)),
        expected_frozen_runtime_inputs=frozen,
        runtime_sha_scope="Five fixture/source inputs plus each generated Tcl itself, before and after; not a complete toolchain freeze.",
        cases=case_plan,
        expected_case_outputs=[
            "version.rpt", "units.rpt", "actual-library-cell.rpt", "q-absolute-request.tsv",
            "conditional-queries.tsv", "all-macro-pin-activity-before.tsv",
            "all-macro-pin-activity-after.tsv", "coverage-before.rpt", "coverage-after.rpt",
            "update-power.rpt", "fixture-power-diagnostic-only.rpt",
            "macro-power-attributes.rpt", "input-sha-before.tsv", "input-sha-after.tsv",
        ],
        optional_case_outputs=["macro-power-diagnostic-only.rpt", "macro-report-unavailable.rpt"],
        limitations=[
            "This helper generates only. No PT or other EDA process is invoked.",
            "Run each case in a separate fresh PT process and case directory; preserve the same DB/netlist/setup and original annotations.",
            "Original annotation_policy fields remain source classifications; Q overrides do not make unresolved Q condition arcs measured.",
            "SP0/SP1 with TR0 are hypothetical absolute annotations for observing side effects. They do not prove real Q zero activity or valid Q conditions.",
            "Report group and exact macro internal/switching/leakage/total power, conditional results and all pin activity sources; compare them against the fresh baseline.",
            "The fixture has one SRAM and deliberately retains the original default and missing-clock limitations. No whole-SoC or contest energy qualification follows.",
            "Runtime input SHA checks must pass both before and after. Outer artifact manifests and tool invocation provenance remain the runner's responsibility.",
        ],
    )
    return dict(plan=plan, files=files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    source = args.export_root.resolve()
    target = args.output_root.resolve()
    require(source != target and source not in target.parents,
            "output must be outside the immutable source export")
    generated = prepare(lambda name: (source / name).read_bytes())
    target.mkdir(parents=True, exist_ok=False)
    for name, data in generated["files"].items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    with (target / "xu-q-absolute-sweep-plan.json").open("x", encoding="utf-8") as stream:
        json.dump(generated["plan"], stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(json.dumps(dict(status=generated["plan"]["status"], output_root=str(target), cases=3)))


if __name__ == "__main__":
    main()
