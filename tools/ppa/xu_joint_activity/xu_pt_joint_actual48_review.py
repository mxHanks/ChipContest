#!/usr/bin/env python3
"""Read-only, offline review of the twelve original actual48 export files.

``review(read_input)`` reads bytes through a caller-supplied function accepting
an export-relative path. The caller owns export/manifest verification. No EDA,
filesystem access, Tcl evaluation, source rewrite, or complete freeze/energy
qualification is performed here. Invalid evidence raises ValueError.
"""

import csv
import hashlib
import io
import json
import math
import re
from collections import Counter


PREFIX = "pt-joint-state-condition-20261103-48/"
FILES = (
    "actual-library-cell.rpt",
    "conditional-queries.tsv",
    "fixture-coverage.rpt",
    "fixture-power-diagnostic-only.rpt",
    "measured-joint-projection.json",
    "pt.log",
    "pt_shell_command.log",
    "query.tcl",
    "state.json",
    "units.rpt",
    "update-power.rpt",
    "version.rpt",
)
DONE = "XU_JOINT_CONDITIONAL_API_PROBE_DONE_NOT_ENERGY_QUALIFIED"
REJECT = "XU_JOINT_CONDITIONAL_API_REJECT"
LEAKAGE = "MEASURED_KNOWN_LEAKAGE_DWELL"
STABLE = "MEASURED_KNOWN_STABLE_BINARY_ACTIVITY"
SUBSET = "DIAGNOSTIC_KNOWN_BINARY_SUBSET_WITH_RETAINED_RESIDUAL"
UNRESOLVED = "UNRESOLVED_RESIDUAL_NO_STABLE_EDGE_NOT_ANNOTATED"
PHASES = ("before_update", "after_update")
LIB_CELL = "RAMSP1024X16_ss_0p99v_0p99v_125c/RAMSP1024X16"
VERSION = "T-2022.03-SP5-1"


def _require(ok, message):
    if not ok:
        raise ValueError("actual48 review: " + message)


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON field " + key)
        result[key] = value
    return result


def _lines_matching(text, pattern):
    return [
        i for i, line in enumerate(text.splitlines(), 1)
        if re.search(pattern, line)
    ]


def _counter_vector(value, length, label):
    _require(isinstance(value, list) and len(value) == length,
             label + " shape differs")
    _require(all(type(item) is int and item >= 0 for item in value),
             label + " contains an invalid counter")
    return value


def _close(actual, expected):
    # get_switching_activity prints about six significant decimal digits.
    return math.isfinite(actual) and math.isclose(
        actual, expected, rel_tol=8e-6, abs_tol=5e-7
    )


def _parse_answer(splitlist, row):
    try:
        outer = splitlist(row["raw_query"])
        _require(len(outer) == 1, "raw query is not a single Tcl result list")
        values = list(splitlist(outer[0]))
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("actual48 review: invalid Tcl list result") from error
    return values


def review(read_input):
    """Return a complete receipt after strict offline evidence checks pass.

    read_input(relative_export_path) must return bytes. Read errors propagate;
    evidence inconsistencies raise ValueError. Tcl is used only as a list
    parser through splitlist; no exported Tcl command is executed.
    """
    import tkinter

    blobs = {}
    for name in FILES:
        data = read_input(PREFIX + name)
        _require(type(data) is bytes, "read_input must return bytes: " + name)
        blobs[name] = data
    texts = {name: data.decode("utf-8") for name, data in blobs.items()}
    identities = [dict(
        path=PREFIX + name, bytes=len(blobs[name]),
        sha256=hashlib.sha256(blobs[name]).hexdigest()
    ) for name in FILES]
    identity_by_name = {item["path"][len(PREFIX):]: item for item in identities}
    state = json.loads(texts["state.json"], object_pairs_hook=_unique_json)
    projection = json.loads(texts["measured-joint-projection.json"],
                            object_pairs_hook=_unique_json)

    done_lines = _lines_matching(texts["pt.log"], "^" + DONE + "$")
    reject_lines = _lines_matching(texts["pt.log"], "^" + REJECT + r"(?:\s|$)")
    error_lines = _lines_matching(texts["pt.log"], r"^\s*Error:")
    echoed_reject_lines = _lines_matching(
        texts["pt.log"], r'puts stderr "' + REJECT + r" \$xu_error"
    )
    echoed_done_lines = _lines_matching(texts["pt.log"], r"^puts \{" + DONE + r"\}$")
    _require(type(state.get("returncode")) is int and state["returncode"] == 0,
             "recorded PT returncode is not zero")
    _require(len(done_lines) == 1, "exactly one independent DONE line required")
    _require(not reject_lines and not error_lines, "actual PT error/reject output found")
    _require(len(echoed_reject_lines) == len(echoed_done_lines) == 1,
             "expected source echo of DONE/REJECT differs")
    _require(state.get("status") == "FAIL", "legacy status is no longer the original FAIL")
    _require(texts["version.rpt"].strip() == VERSION, "PT version differs")
    _require(texts["actual-library-cell.rpt"].splitlines()[0] == LIB_CELL,
             "reported actual library cell differs")
    _require("successfully linked." in texts["pt.log"], "successful link output missing")
    _require("redirect -file update-power.rpt {update_power}" in texts["query.tcl"],
             "expected power update command missing")
    _require("Time_unit                   : 1e-09 Second" in texts["units.rpt"],
             "reported PT time unit differs")

    window = projection["window"]
    duration_ticks = window["duration_ticks"]
    _require(type(duration_ticks) is int and duration_ticks == 524000000,
             "actual48 window duration differs")
    _require(window["timescale_fs"] == 1 and window["macro_count"] == 1
             and window["pin_bits_per_macro"] == 67
             and window["liberty_arc_count"] == 121,
             "actual48 window dimensions differ")
    _require(window["end_tick"] - window["start_tick"] == duration_ticks,
             "window endpoints differ from duration")
    period_ns = duration_ticks * window["timescale_fs"] / 1000000.0
    _require(projection["status"] ==
             "MEASURED_PARTIAL_BINARY_PROJECTION_NOT_COMPLETE_ACTIVITY_OR_ENERGY",
             "projection qualification status differs")
    arcs = projection["arcs"]
    _require(len(arcs) == 121 and [arc["arc_id"] for arc in arcs] == list(range(121)),
             "projection arc IDs are not exactly 0..120")
    policy_counts = Counter(arc["pt_annotation_policy"] for arc in arcs)
    _require(policy_counts == Counter({LEAKAGE: 2, STABLE: 26, SUBSET: 56, UNRESOLVED: 37}),
             "arc policy counts differ")
    for arc in arcs:
        dwell = _counter_vector(arc["condition_dwell_false_true_unknown"], 3, "condition dwell")
        _require(sum(dwell) == duration_ticks, "condition dwell does not cover window")
        if arc["kind"] == "internal":
            _counter_vector(arc["diagnostic_stable_known_binary_rise_fall"], 2, "stable activity")
            before = _counter_vector(arc["stable_known_true_binary_rise_fall_before_timestamp_exclusion"],
                                     2, "activity before timestamp exclusion")
            excluded = _counter_vector(arc["uncertain_same_timestamp_stable_binary_rise_fall"],
                                       2, "timestamp exclusion")
            _require([a - b for a, b in zip(before, excluded)] ==
                     arc["diagnostic_stable_known_binary_rise_fall"],
                     "stable activity/timestamp subtraction differs")
        else:
            _require(arc["kind"] == "leakage" and arc["pt_annotation_policy"] == LEAKAGE,
                     "unexpected arc kind/policy")
    _require(all(arc["when"] == "default" for arc in arcs
                 if arc["pt_annotation_policy"] == STABLE),
             "unexpected fully stable nontrivial conditional arc")
    _require(arcs[0]["measured_leakage_known_true_ticks"] == 259000000
             and arcs[1]["measured_leakage_known_true_ticks"] == 265000000
             and arcs[1]["default_policy"] ==
             "known complement of sole explicit !RET1N leakage condition; no independent additive default=1",
             "leakage complement policy/dwell differs")

    reader = csv.DictReader(io.StringIO(texts["conditional-queries.tsv"]), delimiter="\t")
    _require(reader.fieldnames == ["phase", "arc_id", "kind", "pin", "condition",
                                  "direction", "annotation_policy", "raw_query"],
             "TSV columns differ")
    rows = list(reader)
    _require(len(rows) == 606, "TSV does not contain exactly 606 data rows")
    index = {}
    row_receipts = []
    row_class_counts = Counter()
    source_counts = Counter()
    splitlist = tkinter.Tcl().splitlist
    for row in rows:
        _require(None not in row and all(value is not None for value in row.values()),
                 "malformed TSV row")
        _require(row["phase"] in PHASES and row["arc_id"].isdigit(), "invalid phase/arc ID")
        arc_id = int(row["arc_id"])
        _require(0 <= arc_id < 121, "TSV arc ID outside ledger")
        arc = arcs[arc_id]
        expected_pin = "-" if arc["kind"] == "leakage" else arc["toggling_pin"]
        _require((row["kind"], row["pin"], row["condition"], row["annotation_policy"]) ==
                 (arc["kind"], expected_pin, arc["when"], arc["pt_annotation_policy"]),
                 "TSV/projection metadata differs")
        directions = ("both",) if arc["kind"] == "leakage" or arc["when"] == "default" else (
            "both", "rise", "fall"
        )
        _require(row["direction"] in directions, "unexpected query direction")
        key = (row["phase"], arc_id, row["direction"])
        _require(key not in index, "duplicate TSV phase/arc/direction")
        index[key] = row
        values = _parse_answer(splitlist, row)
        obj = "m" if arc["kind"] == "leakage" else "m/" + arc["toggling_pin"]
        _require(values and values[0] == obj, "queried object differs")
        conditional = arc["kind"] == "leakage" or arc["when"] != "default"
        prefix = 2 if conditional else 1
        if conditional:
            _require(len(values) >= 2 and values[1] == arc["when"], "queried condition differs")
        expected_pairs = 1 if arc["kind"] == "leakage" else (
            4 if conditional and row["direction"] == "both" else 2
        )
        _require(len(values) == prefix + 2 * expected_pairs, "raw result dimensions differ")
        try:
            observed = [float(value) for value in values[prefix::2]]
        except ValueError as error:
            raise ValueError("actual48 review: nonnumeric result") from error
        sources = values[prefix + 1::2]
        source_counts.update(sources)
        policy = arc["pt_annotation_policy"]
        if arc["kind"] == "leakage":
            expected = [arc["measured_leakage_known_true_ticks"] / float(duration_ticks)]
            _require(sources == ["A"], "leakage source is not asserted A")
            row_class_counts["leakage_rows"] += 1
        elif policy == UNRESOLVED:
            if row["phase"] == "before_update":
                expected = [-1.0] * expected_pairs
                expected_source = "UNINITIALIZED"
            else:
                rate = 0.05 if arc["toggling_pin"].startswith("Q[") else (
                    0.025 if arc["toggling_pin"] == "RET1N" else 0.0125
                )
                expected = [rate, rate, 0.0, 0.0] if expected_pairs == 4 else [rate, 0.0]
                expected_source = "Default"
            _require(set(sources) == {expected_source}, "unresolved source differs")
            row_class_counts["unresolved_rows"] += 1
        else:
            rise, fall = arc["diagnostic_stable_known_binary_rise_fall"]
            if not conditional:
                expected = [(rise + fall) / period_ns, 0.0]
            elif row["direction"] == "both":
                expected = [rise / period_ns, fall / period_ns, 0.0, 0.0]
            else:
                expected = [(rise if row["direction"] == "rise" else fall) / period_ns, 0.0]
            _require(set(sources) == {"set_switching_activity"}, "annotated activity source differs")
            row_class_counts["annotated_activity_rows"] += 1
        _require(all(_close(a, b) for a, b in zip(observed, expected)),
                 "numeric result differs for %s/%s/%s" % key)
        row_receipts.append(dict(phase=row["phase"], arc_id=arc_id, direction=row["direction"],
                                 observed=observed, expected=expected, sources=sources))

    arc_receipts = []
    for arc in arcs:
        arc_id = arc["arc_id"]
        directions = ("both",) if arc["kind"] == "leakage" or arc["when"] == "default" else (
            "both", "rise", "fall"
        )
        for phase in PHASES:
            _require(all((phase, arc_id, direction) in index for direction in directions),
                     "missing phase/arc/direction coverage")
        identical = all(index[(PHASES[0], arc_id, direction)]["raw_query"] ==
                        index[(PHASES[1], arc_id, direction)]["raw_query"]
                        for direction in directions)
        unresolved = arc["pt_annotation_policy"] == UNRESOLVED
        _require(identical != unresolved, "before/after preservation class differs")
        arc_receipts.append(dict(
            arc_id=arc_id, kind=arc["kind"], pin=arc["toggling_pin"], condition=arc["when"],
            annotation_policy=arc["pt_annotation_policy"], directions=list(directions),
            before_after_raw_identical=identical,
            result_class="UNINITIALIZED_TO_DEFAULT_NOT_MEASURED" if unresolved else
                         "ASSERTED_VALUE_PRESERVED_API_ONLY",
        ))
    _require(row_class_counts == Counter(leakage_rows=4, annotated_activity_rows=380,
                                         unresolved_rows=222), "numeric row totals differ")

    # Only these two before-listed source files are actually among the twelve
    # inputs. Remote paths and stored hashes are not evidence of current bytes.
    before_inputs = state["input_identities_before"]
    _require(isinstance(before_inputs, list), "before input identities missing")
    source_matches = []
    for name in ("query.tcl", "measured-joint-projection.json"):
        matching = [item for item in before_inputs if item.get("path", "").endswith("/" + PREFIX + name)]
        _require(len(matching) == 1, "unique before source identity missing: " + name)
        recorded = matching[0]
        observed = identity_by_name[name]
        _require(recorded.get("bytes") == observed["bytes"]
                 and recorded.get("sha256") == observed["sha256"],
                 "available source does not match before identity: " + name)
        source_matches.append(dict(recorded_path=recorded["path"], available_path=observed["path"],
                                   bytes=observed["bytes"], sha256=observed["sha256"], matches=True))
    unavailable_before = [item for item in before_inputs
                          if item.get("path") not in {item["recorded_path"] for item in source_matches}]
    _require("input_identities_after" not in state, "original actual48 unexpectedly has after identities")

    power = texts["fixture-power-diagnostic-only.rpt"]
    match = re.search(r"^Total Power\s*=\s*([0-9.eE+-]+)", power, re.MULTILINE)
    _require(match is not None, "diagnostic fixture power report missing total")
    _require("67 nets with no annotation" in texts["fixture-coverage.rpt"],
             "expected incomplete static-probability coverage differs")
    coverage_rows = re.findall(r"^\s+Nets\s+(.+)$", texts["fixture-coverage.rpt"], re.MULTILINE)
    _require(len(coverage_rows) == 2, "toggle/static coverage summary rows differ")
    coverage_counts = [
        [int(value) for value in re.findall(r"(\d+)\([0-9.]+%\)", line)]
        for line in coverage_rows
    ]
    _require(coverage_counts == [
        [0, 28, 0, 0, 0, 0, 39, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 67, 0, 0, 0],
    ] and all(re.search(r"\s67\s*$", line) for line in coverage_rows),
        "asserted/default toggle or static-probability coverage differs")
    nontrivial_subset = sum(arc["pt_annotation_policy"] == SUBSET and arc["when"] != "default"
                           for arc in arcs)
    _require(nontrivial_subset == 54, "nontrivial conditional subset count differs")
    return dict(
        schema="xu-pt-joint-actual48-offline-review-v1",
        status="PASS_OFFLINE_PARTIAL_API_REVIEW_NOT_ENERGY_QUALIFIED",
        export_prefix=PREFIX,
        input_files=identities,
        manifest_verification="CALLER_RESPONSIBILITY_NOT_PERFORMED_BY_THIS_MODULE",
        pt_completion=dict(
            actual_status="ACTUAL_PT_COMPLETED_API_PROBE_NOT_ENERGY_QUALIFIED",
            returncode=state["returncode"], independent_done_lines=done_lines,
            actual_reject_lines=reject_lines, actual_error_lines=error_lines,
            echoed_reject_source_lines=echoed_reject_lines,
            echoed_done_source_lines=echoed_done_lines,
            legacy_state_status=state["status"], legacy_state_error=state.get("error"),
            legacy_fail_contradicts_completion=True,
            echo_reject_is_not_executed_rejection=True,
            exact_legacy_runner_failure_cause="NOT_PROVABLE_FROM_THESE_TWELVE_FILES",
            version=VERSION, actual_library_cell=LIB_CELL,
        ),
        projection=dict(status=projection["status"], window=window,
                        policy_counts=dict(policy_counts),
                        nontrivial_conditional_annotated_subset_arcs=nontrivial_subset,
                        fully_stable_activity_arcs_are_default_only=True,
                        raw_stats_identity_recorded_only=projection["raw_stats"],
                        raw_sidecar_identity_recorded_only=projection["raw_sidecar"],
                        micro_state_identity_recorded_only=projection["actual_micro_state"]),
        queries=dict(
            total_rows=606, rows_per_phase={phase: 303 for phase in PHASES},
            arcs_per_phase={phase: 121 for phase in PHASES},
            numeric_class_counts=dict(row_class_counts), numeric_mismatches=0,
            source_token_counts=dict(source_counts),
            numeric_tolerance=dict(relative=8e-6, absolute=5e-7),
            preserved_asserted_arcs=84, unresolved_to_default_arcs=37,
            changed_rows=111, unchanged_rows=192,
            comparison_row_counts_are_per_phase=True,
            arc_receipts=arc_receipts, row_receipts=row_receipts,
        ),
        source_identity_scope=dict(
            state_has_before_identities=True, state_has_after_identities=False,
            before_identity_count=len(before_inputs),
            available_before_source_matches=source_matches,
            unavailable_before_identity_count=len(unavailable_before),
            unavailable_before_identities=unavailable_before,
            complete_freeze_authenticated=False, raw_capture_rederived=False,
        ),
        fixture_diagnostic=dict(
            total_power_w=float(match.group(1)), energy_qualified=False,
            no_clock_warning="PWR-171" in texts["update-power.rpt"],
            missing_static_probability_warning="PSW-191" in texts["update-power.rpt"],
            all_67_static_probabilities_default=True,
            toggle_nets_asserted=28, toggle_nets_default=39,
        ),
        limitations=[
            "The twelve-file manifest must be verified by the caller.",
            "Completion and set/get agreement prove API behavior only, not power-engine joint semantics or contest eligibility.",
            "The 54 annotated nontrivial conditional dynamic arcs are diagnostic binary subsets with retained unresolved residuals.",
            "The 37 unannotated arcs acquire tool defaults after update_power; those defaults are not measured joint activity or physical zero.",
            "Only available query/projection bytes match stored before identities; no after snapshot or complete source freeze is authenticated.",
            "Raw stats, simultaneous sidecar and micro-state identities are recorded references; their bytes and capture provenance are not independently checked here.",
            "Fixture power contains default activity/static probabilities and no defined clock; it is not a full SoC power or energy result.",
        ],
        next_steps=[
            "Preserve the original legacy FAIL evidence and attach this separate offline correction receipt.",
            "Match independent error/reject output lines together with returncode and independent DONE, rather than matching tokens in echoed Tcl source.",
            "Require actual before/after source identities and independent raw-capture and power-engine semantics evidence before broader qualification.",
        ],
    )
