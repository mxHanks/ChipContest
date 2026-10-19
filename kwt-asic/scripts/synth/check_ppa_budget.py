#!/usr/bin/env python3
"""Fail-closed PPA evidence intake. This does not run or certify an EDA flow."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "kwt-ppa-evidence-v1"
DOMAINS = ("core", "new_interface", "internal_sram", "e203", "interconnect",
           "shared_sram", "fixed_peripherals")
PHASES = {"parameter_load", "input_load", "cpu_schedule", "compute", "writeback"}
ARTIFACTS = ("configuration", "netlist", "sdc", "official_technology_manifest",
             "task_manifest", "area_report", "timing_report", "power_report",
             "activity", "activity_coverage_report", "macro_inventory_report",
             "cell_inventory_report", "constraint_coverage_report", "clock_report",
             "full_window_trace")
UNITS = {"mm2": Decimal(1), "um2": Decimal("0.000001")}
POWER_UNITS = {"W": Decimal(1), "mW": Decimal("0.001"), "uW": Decimal("0.000001")}
ROLES = ("setup", "hold", "power")
GENERATED = tuple(x for x in ARTIFACTS if x not in
                  ("configuration", "netlist", "sdc", "official_technology_manifest", "task_manifest"))


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError("non-finite JSON constant " + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def ref(path):
    return {"path": str(path), "sha256": sha256(path)}


def unknown_ref():
    return {"path": None, "sha256": None}


def referenced_paths(value, root):
    """Protect declared inputs even when their digest is wrong or they are empty."""
    result = set()
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and "sha256" in value:
            path = Path(value["path"])
            result.add((path if path.is_absolute() else Path(root) / path).resolve())
        for child in value.values():
            result.update(referenced_paths(child, root))
    elif isinstance(value, list):
        for child in value:
            result.update(referenced_paths(child, root))
    return result


def template(config_id, root=ROOT):
    root = Path(root)
    budget = json.loads((root / "configs/optimization-area-budget.json").read_text())
    configs = {x["id"]: x for x in budget["configurations"]}
    if config_id not in configs:
        raise ValueError("unknown analytical config_id; select one from the area-budget file")
    binding = {"configuration_sha256": None, "netlist_sha256": None,
               "sdc_sha256": None, "run_id": None, "analysis_context_sha256": None}
    def area_item():
        return {"value": None, "unit": None, "unit_basis": unknown_ref(),
                "instances": None, "zero_justification": None}
    return {
        "schema": SCHEMA, "config_id": config_id,
        "budget_reference": ref(root / "configs/optimization-area-budget.json"),
        "requirements_reference": ref(root / "docs/requirements/UNDERGRAD_REQUIREMENTS.md"),
        "run_id": None, "technology_status": None,
        "artifacts": {name: unknown_ref() for name in ARTIFACTS},
        "artifact_bindings": {name: dict(binding, window_sha256=None) for name in GENERATED},
        "libraries": {role: {"corner_id": None, "process": None, "voltage_v": None,
                             "temperature_c": None, "standard_cells": [unknown_ref()]}
                      for role in ROLES},
        "analysis_conditions": {"interconnect_model": unknown_ref(),
                                "load_model": unknown_ref(), "tool_versions": unknown_ref(),
                                "required_modes_and_corners": unknown_ref()},
        "area": {"binding": dict(binding), "inventory_complete": None,
                 "core": area_item(), "new_interface": area_item(),
                 "macros": None,
                 "reused": {name: dict(area_item(), **({"models": None} if name == "shared_sram" else {})) for name in
                            ("e203", "shared_sram", "interconnect", "fixed_peripherals")}},
        "timing": {"binding": dict(binding), "frequency_mhz": 150,
                   "clock_period_ns": None, "setup_wns_ns": None, "hold_wns_ns": None,
                   "setup_violations": None, "hold_violations": None,
                   "unconstrained_endpoints": None, "unclocked_registers": None,
                   "unconstrained_io": None, "unresolved_cells": None,
                   "invalid_exceptions": None, "constraints_reviewed": None,
                   "all_required_modes_and_corners_covered": None,
                   "max_transition_violations": None, "max_capacitance_violations": None,
                   "max_fanout_violations": None},
        "window": {"frequency_mhz": 150, "start_cycle": None, "end_cycle": None,
                   "included_phases": sorted(PHASES), "tasks": None},
        "power": {"binding": dict(binding), "window_sha256": None,
                  "full_hierarchy_covered": None, "activity_matches_mapped_netlist": None,
                  "domains": {name: {"dynamic": None, "leakage": None, "unit": None,
                                     "instances": None,
                                     "activity_required_objects": None,
                                     "activity_annotated_objects": None,
                                     "zero_justification": None} for name in DOMAINS}},
        "notes": ["Unknown values must remain null. Analytical macro counts are not mapped evidence.",
                  "PASS means file/binding/accounting checks passed; it does not certify physical results."]}


def analysis_context(data):
    """The SAME corner manifest is bound to every report, not the same PVT for all analyses."""
    area = data.get("area") if isinstance(data.get("area"), dict) else {}
    reused = area.get("reused") if isinstance(area.get("reused"), dict) else {}
    shared = reused.get("shared_sram") if isinstance(reused.get("shared_sram"), dict) else {}
    artifacts = data.get("artifacts") if isinstance(data.get("artifacts"), dict) else {}
    return {"technology_status": data.get("technology_status"),
            "libraries": data.get("libraries"),
            "conditions": data.get("analysis_conditions"),
            "internal_macros": area.get("macros"),
            "shared_sram_models": shared.get("models"),
            "official_technology_manifest": artifacts.get("official_technology_manifest")}


class Check:
    def __init__(self, root):
        self.root = Path(root)
        self.issues = []
        self.verified_files = {}

    def issue(self, field, message, status="BLOCKED"):
        self.issues.append({"status": status, "field": field, "message": message})

    def obj(self, value, field):
        if value is None:
            self.issue(field, "required object missing")
        elif not isinstance(value, dict):
            self.issue(field, "expected object", "FAIL")
        else:
            return value
        return {}

    def text(self, value, field):
        if value is None or value == "":
            self.issue(field, "required text missing")
        elif not isinstance(value, str) or not value.strip():
            self.issue(field, "expected nonempty text", "FAIL")
        else:
            return value
        return None

    def num(self, value, field, minimum=None, positive=False, integer=False):
        if value is None:
            self.issue(field, "measurement missing; never substitute zero")
            return None
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or isinstance(value, float) and not math.isfinite(value)):
            self.issue(field, "expected finite numeric measurement", "FAIL")
            return None
        n = Decimal(str(value))
        if abs(n) > Decimal("1e100"):
            self.issue(field, "measurement exceeds supported numeric range", "FAIL")
            return None
        if integer and n != n.to_integral_value():
            self.issue(field, "expected integer", "FAIL")
            return None
        if (positive and n <= 0) or (minimum is not None and n < minimum):
            self.issue(field, "measurement outside allowed range", "FAIL")
            return None
        return n

    def yes(self, value, field):
        if value is not True:
            self.issue(field, "required true assertion unsupported or false",
                       "BLOCKED" if value is None else "FAIL")

    def artifact(self, value, field):
        x = self.obj(value, field)
        path, expected = x.get("path"), x.get("sha256")
        if not self.text(path, field + ".path") or not self.text(expected, field + ".sha256"):
            return None
        if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            self.issue(field, "SHA-256 must be 64 lowercase hexadecimal characters", "FAIL")
            return None
        p = Path(path)
        if not p.is_absolute():
            p = self.root / p
        try:
            if not p.is_file():
                self.issue(field, "referenced file is absent or not a regular file")
                return None
            if p.stat().st_size == 0:
                self.issue(field, "empty file is not evidence", "FAIL")
                return None
            actual = sha256(p)
        except OSError as exc:
            self.issue(field, "cannot read evidence: " + str(exc))
            return None
        if actual != expected:
            self.issue(field, "file content does not match declared SHA-256", "FAIL")
            return None
        self.verified_files[field] = {"path": str(p.resolve()), "sha256": actual}
        return actual

    def binding(self, value, field, hashes, run_id, context_hash):
        x = self.obj(value, field)
        for key in ("configuration", "netlist", "sdc"):
            actual = self.text(x.get(key + "_sha256"), field + "." + key + "_sha256")
            if actual and hashes.get(key) and actual != hashes[key]:
                self.issue(field, "mixed configuration/netlist/SDC evidence", "FAIL")
        actual = self.text(x.get("run_id"), field + ".run_id")
        if actual and run_id and actual != run_id:
            self.issue(field, "mixed analysis run", "FAIL")
        actual = self.text(x.get("analysis_context_sha256"), field + ".analysis_context_sha256")
        if actual and actual != context_hash:
            self.issue(field, "mixed PVT/library/interconnect/load/tool context", "FAIL")

    def area_value(self, value, field, allow_zero=False):
        x = self.obj(value, field)
        n = self.num(x.get("value"), field + ".value", minimum=0, positive=not allow_zero)
        unit = x.get("unit")
        if unit is None:
            self.issue(field + ".unit", "area unit missing")
        elif not isinstance(unit, str) or unit not in UNITS:
            self.issue(field + ".unit", "use mm2 or um2; library area units need documented conversion", "FAIL")
        self.artifact(x.get("unit_basis"), field + ".unit_basis")
        if n == 0:
            self.text(x.get("zero_justification"), field + ".zero_justification")
        return n * UNITS[unit] if n is not None and isinstance(unit, str) and unit in UNITS else None

    def instances(self, value, field, seen, allow_empty=False):
        if value is None:
            self.issue(field, "complete instance list missing")
            return
        if not isinstance(value, list) or (not value and not allow_empty):
            self.issue(field, "expected nonempty instance list", "FAIL")
            return
        for name in value:
            if self.text(name, field):
                if name in seen:
                    self.issue(field, "instance counted in more than one area category: " + name, "FAIL")
                if any(name.startswith(old + "/") or old.startswith(name + "/") for old in seen):
                    self.issue(field, "hierarchy and descendant cannot both be counted; list leaf instances", "FAIL")
                seen.add(name)


def check(data, root=ROOT):
    c = Check(root)
    data = c.obj(data, "input")
    if data.get("schema") != SCHEMA:
        c.issue("schema", "unsupported evidence schema", "FAIL")
    run_id = c.text(data.get("run_id"), "run_id")
    if data.get("technology_status") != "official_designated":
        c.issue("technology_status", "designated technology and authority document required")
    for name in ("budget_reference", "requirements_reference"):
        c.artifact(data.get(name), name)
    budget_path = Path(root) / "configs/optimization-area-budget.json"
    budget = strict_json(budget_path.read_text())
    constraints = budget["constraints"]
    # These are project/user limits; a submitted budget cannot relax them.
    if (constraints["incremental_area_limit_mm2"] != 2.25 or constraints["target_frequency_mhz"] != 150
            or constraints.get("area_comparison") != "strict_less_than"):
        c.issue("budget_reference", "project limits unexpectedly changed", "FAIL")
    for name, path in (("budget_reference", budget_path),
                       ("requirements_reference", Path(root) / "docs/requirements/UNDERGRAD_REQUIREMENTS.md")):
        if name in c.verified_files and c.verified_files[name]["sha256"] != sha256(path):
            c.issue(name, "reference differs from current project requirements", "FAIL")
    ids = {x["id"] for x in budget["configurations"]}
    if data.get("config_id") not in ids:
        c.issue("config_id", "unknown analytical configuration; update capacity plan before intake", "FAIL")
    artifacts = c.obj(data.get("artifacts"), "artifacts")
    hashes = {name: c.artifact(artifacts.get(name), "artifacts." + name) for name in ARTIFACTS}
    context_hash = canonical_hash(analysis_context(data))
    libraries = c.obj(data.get("libraries"), "libraries")
    for role in ROLES:
        lib = c.obj(libraries.get(role), "libraries." + role)
        c.text(lib.get("corner_id"), "libraries." + role + ".corner_id")
        c.text(lib.get("process"), "libraries." + role + ".process")
        c.num(lib.get("voltage_v"), "libraries." + role + ".voltage_v", positive=True)
        temperature = c.num(lib.get("temperature_c"), "libraries." + role + ".temperature_c")
        if temperature is not None and temperature < Decimal("-273.15"):
            c.issue("libraries." + role, "temperature is below absolute zero", "FAIL")
        refs = lib.get("standard_cells")
        if not isinstance(refs, list) or not refs:
            c.issue("libraries." + role, "designated standard-cell libraries missing")
        else:
            for i, record in enumerate(refs):
                c.artifact(record, f"libraries.{role}.standard_cells[{i}]")
    conditions = c.obj(data.get("analysis_conditions"), "analysis_conditions")
    for name in ("interconnect_model", "load_model", "tool_versions", "required_modes_and_corners"):
        c.artifact(conditions.get(name), "analysis_conditions." + name)
    area = c.obj(data.get("area"), "area")
    c.binding(area.get("binding"), "area.binding", hashes, run_id, context_hash)
    c.yes(area.get("inventory_complete"), "area.inventory_complete")
    seen = set()
    core = c.area_value(area.get("core"), "area.core")
    interface = c.area_value(area.get("new_interface"), "area.new_interface", allow_zero=True)
    for name in ("core", "new_interface"):
        item = c.obj(area.get(name), "area." + name)
        c.instances(item.get("instances"), "area." + name + ".instances", seen,
                    allow_empty=name == "new_interface" and interface == 0)
        if name == "new_interface" and interface == 0 and item.get("instances"):
            c.issue("area.new_interface", "zero area requires an empty instance inventory", "FAIL")
    macros = area.get("macros")
    macro_sum = Decimal(0)
    if not isinstance(macros, list) or not macros:
        c.issue("area.macros", "actual mapped internal SRAM macro inventory missing")
        macro_sum = None
    else:
        cells = set()
        for i, record in enumerate(macros):
            field = f"area.macros[{i}]"
            m = c.obj(record, field)
            name = c.text(m.get("cell_name"), field + ".cell_name")
            if name in cells:
                c.issue(field, "duplicate cell type; combine all instances", "FAIL")
            cells.add(name)
            n = c.num(m.get("count"), field + ".count", positive=True, integer=True)
            a = c.area_value(m.get("per_instance_area"), field + ".per_instance_area")
            c.instances(m.get("instances"), field + ".instances", seen)
            if isinstance(m.get("instances"), list) and n is not None and len(m["instances"]) != n:
                c.issue(field, "macro count does not match instance inventory", "FAIL")
            c.artifact(m.get("functional_model"), field + ".functional_model")
            mlibs = c.obj(m.get("libraries"), field + ".libraries")
            for role in ROLES:
                c.artifact(mlibs.get(role), field + ".libraries." + role)
            corners = c.obj(m.get("corner_ids"), field + ".corner_ids")
            for role in ROLES:
                corner = c.text(corners.get(role), field + ".corner_ids." + role)
                expected = libraries.get(role, {})
                if corner and isinstance(expected, dict) and corner != expected.get("corner_id"):
                    c.issue(field, "macro library corner differs from analysis corner", "FAIL")
            if a is None or n is None:
                macro_sum = None
            elif macro_sum is not None:
                macro_sum += n * a
    reused = c.obj(area.get("reused"), "area.reused")
    reused_sum = Decimal(0)
    for name in ("e203", "shared_sram", "interconnect", "fixed_peripherals"):
        item = c.obj(reused.get(name), "area.reused." + name)
        n = c.area_value(item, "area.reused." + name, allow_zero=name == "fixed_peripherals")
        c.instances(item.get("instances"), "area.reused." + name + ".instances", seen,
                    allow_empty=name == "fixed_peripherals" and n == 0)
        if name == "fixed_peripherals" and n == 0 and item.get("instances"):
            c.issue("area.reused." + name, "zero area requires an empty instance inventory", "FAIL")
        reused_sum = None if n is None or reused_sum is None else reused_sum + n
    shared = reused.get("shared_sram") if isinstance(reused.get("shared_sram"), dict) else {}
    shared_models = shared.get("models")
    shared_instances = set()
    if not isinstance(shared_models, list) or not shared_models:
        c.issue("area.reused.shared_sram.models", "shared SRAM functional/timing/power models missing")
    else:
        for i, value in enumerate(shared_models):
            field = f"area.reused.shared_sram.models[{i}]"
            m = c.obj(value, field)
            c.text(m.get("cell_name"), field + ".cell_name")
            c.instances(m.get("instances"), field + ".instances", shared_instances)
            c.artifact(m.get("functional_model"), field + ".functional_model")
            mlibs = c.obj(m.get("libraries"), field + ".libraries")
            corners = c.obj(m.get("corner_ids"), field + ".corner_ids")
            for role in ROLES:
                c.artifact(mlibs.get(role), field + ".libraries." + role)
                corner = c.text(corners.get(role), field + ".corner_ids." + role)
                expected = libraries.get(role, {})
                if corner and isinstance(expected, dict) and corner != expected.get("corner_id"):
                    c.issue(field, "shared SRAM corner differs from analysis corner", "FAIL")
        expected = shared.get("instances")
        if isinstance(expected, list) and all(isinstance(x, str) for x in expected) and shared_instances != set(expected):
            c.issue("area.reused.shared_sram.models", "model coverage differs from shared SRAM inventory", "FAIL")
    total = None if any(x is None for x in (core, interface, macro_sum)) else core + interface + macro_sum
    if total is not None and total >= Decimal("2.25"):
        c.issue("area", "incremental area must be STRICTLY less than 2.25 mm2", "FAIL")

    timing = c.obj(data.get("timing"), "timing")
    c.binding(timing.get("binding"), "timing.binding", hashes, run_id, context_hash)
    freq = c.num(timing.get("frequency_mhz"), "timing.frequency_mhz", positive=True)
    period = c.num(timing.get("clock_period_ns"), "timing.clock_period_ns", positive=True)
    if freq is not None and freq != 150:
        c.issue("timing.frequency_mhz", "contest evaluation uses 150 MHz", "FAIL")
    if period is not None and abs(period - Decimal(1000) / Decimal(150)) > Decimal("0.000001"):
        c.issue("timing.clock_period_ns", "period inconsistent with 150 MHz", "FAIL")
    for key in ("setup_wns_ns", "hold_wns_ns"):
        slack = c.num(timing.get(key), "timing." + key)
        if slack is not None and slack < 0:
            c.issue("timing." + key, "negative slack", "FAIL")
    for key in ("setup_violations", "hold_violations", "unconstrained_endpoints",
                "unclocked_registers", "unconstrained_io", "unresolved_cells", "invalid_exceptions",
                "max_transition_violations", "max_capacitance_violations", "max_fanout_violations"):
        n = c.num(timing.get(key), "timing." + key, minimum=0, integer=True)
        if n is not None and n != 0:
            c.issue("timing." + key, "unresolved constraints or design-rule violations", "FAIL")
    for key in ("constraints_reviewed", "all_required_modes_and_corners_covered"):
        c.yes(timing.get(key), "timing." + key)

    window = c.obj(data.get("window"), "window")
    wf = c.num(window.get("frequency_mhz"), "window.frequency_mhz", positive=True)
    start = c.num(window.get("start_cycle"), "window.start_cycle", minimum=0, integer=True)
    end = c.num(window.get("end_cycle"), "window.end_cycle", minimum=0, integer=True)
    if wf is not None and wf != 150:
        c.issue("window.frequency_mhz", "window frequency must be 150 MHz", "FAIL")
    phases = window.get("included_phases")
    if (not isinstance(phases, list) or not all(isinstance(x, str) for x in phases)
            or set(phases) != PHASES or len(phases) != len(PHASES)):
        c.issue("window.included_phases", "must include load, CPU scheduling, compute and all writeback")
    duration = None
    if start is not None and end is not None and wf is not None:
        if end <= start:
            c.issue("window", "end_cycle must exceed start_cycle", "FAIL")
        else:
            duration = (end - start) / (wf * Decimal(1_000_000))
    tasks = window.get("tasks")
    task_count = None
    if not isinstance(tasks, list) or len(tasks) != 12:
        c.issue("window.tasks", "exactly 12 independent layer tasks required")
    else:
        task_count, previous_end, layers, task_ids = 12, None, set(), set()
        for i, value in enumerate(tasks):
            field = f"window.tasks[{i}]"
            t = c.obj(value, field)
            task_id = c.text(t.get("task_id"), field + ".task_id")
            if task_id in task_ids:
                c.issue(field, "duplicate task identity", "FAIL")
            task_ids.add(task_id)
            layer = c.num(t.get("layer"), field + ".layer", minimum=0, integer=True)
            if layer is not None:
                layers.add(layer)
            a = c.num(t.get("start_cycle"), field + ".start_cycle", minimum=0, integer=True)
            b = c.num(t.get("end_cycle"), field + ".end_cycle", minimum=0, integer=True)
            if a is not None and b is not None:
                if b <= a or (start is not None and a < start) or (end is not None and b > end):
                    c.issue(field, "invalid task boundaries", "FAIL")
                if previous_end is not None and a < previous_end:
                    c.issue(field, "tasks overlap or are out of order", "FAIL")
                if (i == 0 and a != start) or (i == 11 and b != end):
                    c.issue(field, "whole window must include first load through final writeback", "FAIL")
                previous_end = b
            for key in ("cache_cleared_before_load", "includes_all_loads", "includes_cpu_schedule", "writeback_complete"):
                c.yes(t.get(key), field + "." + key)
        if layers != set(map(Decimal, range(12))):
            c.issue("window.tasks", "must cover each of layers 0..11 exactly once", "FAIL")

    power = c.obj(data.get("power"), "power")
    c.binding(power.get("binding"), "power.binding", hashes, run_id, context_hash)
    wh = c.text(power.get("window_sha256"), "power.window_sha256")
    try:
        actual_wh = canonical_hash(window)
    except (ValueError, TypeError):
        actual_wh = None
    if wh and wh != actual_wh:
        c.issue("power.window_sha256", "power activity and performance window differ", "FAIL")
    report_bindings = c.obj(data.get("artifact_bindings"), "artifact_bindings")
    for name in GENERATED:
        field = "artifact_bindings." + name
        b = c.obj(report_bindings.get(name), field)
        c.binding(b, field, hashes, run_id, context_hash)
        declared = c.text(b.get("window_sha256"), field + ".window_sha256")
        if declared and declared != actual_wh:
            c.issue(field, "report/trace/activity belongs to a different full window", "FAIL")
    for key in ("full_hierarchy_covered", "activity_matches_mapped_netlist"):
        c.yes(power.get(key), "power." + key)
    domains = c.obj(power.get("domains"), "power.domains")
    if set(domains) - set(DOMAINS):
        c.issue("power.domains", "unknown domains: split into the documented disjoint categories", "FAIL")
    watts = Decimal(0)
    expected_instances = {"core": c.obj(area.get("core"), "area.core").get("instances"),
                          "new_interface": c.obj(area.get("new_interface"), "area.new_interface").get("instances"),
                          "internal_sram": []}
    if isinstance(macros, list):
        for m in macros:
            if isinstance(m, dict) and isinstance(m.get("instances"), list):
                expected_instances["internal_sram"].extend(m["instances"])
    for name in ("e203", "interconnect", "shared_sram", "fixed_peripherals"):
        expected_instances[name] = c.obj(reused.get(name), "area.reused." + name).get("instances")
    power_seen = set()
    for name in DOMAINS:
        field = "power.domains." + name
        d = c.obj(domains.get(name), field)
        dynamic = c.num(d.get("dynamic"), field + ".dynamic", minimum=0)
        leakage = c.num(d.get("leakage"), field + ".leakage", minimum=0)
        unit = d.get("unit")
        if unit is None:
            c.issue(field + ".unit", "power unit missing")
        elif not isinstance(unit, str) or unit not in POWER_UNITS:
            c.issue(field + ".unit", "use W, mW or uW", "FAIL")
        if dynamic == 0 or leakage == 0:
            c.text(d.get("zero_justification"), field + ".zero_justification")
        c.instances(d.get("instances"), field + ".instances", power_seen,
                    allow_empty=dynamic == 0 and leakage == 0)
        expected, observed = expected_instances[name], d.get("instances")
        if (isinstance(expected, list) and isinstance(observed, list)
                and all(isinstance(x, str) for x in expected + observed)):
            if set(expected) != set(observed):
                c.issue(field, "power domain instances differ from disjoint area inventory", "FAIL")
            if not observed and (dynamic != 0 or leakage != 0):
                c.issue(field, "nonzero power for an empty domain", "FAIL")
        required = c.num(d.get("activity_required_objects"), field + ".activity_required_objects",
                         minimum=0, integer=True)
        annotated = c.num(d.get("activity_annotated_objects"), field + ".activity_annotated_objects",
                          minimum=0, integer=True)
        if required is not None and annotated is not None:
            if annotated > required:
                c.issue(field, "annotated object count exceeds eligible activity population", "FAIL")
            elif annotated < required:
                c.issue(field, "incomplete activity coverage; no zero/default substitution permitted")
            elif required == 0:
                c.text(d.get("zero_justification"), field + ".zero_justification")
        if dynamic is None or leakage is None or not isinstance(unit, str) or unit not in POWER_UNITS:
            watts = None
        elif watts is not None:
            watts += (dynamic + leakage) * POWER_UNITS[unit]
    if watts is not None and watts <= 0:
        c.issue("power", "whole functioning system power must be positive", "FAIL")
    # A file changed during intake cannot be used in this result.
    for field, verified in c.verified_files.items():
        try:
            if sha256(verified["path"]) != verified["sha256"]:
                c.issue(field, "evidence changed while checking", "FAIL")
        except OSError:
            c.issue(field, "evidence disappeared while checking", "FAIL")
    status = "FAIL" if any(x["status"] == "FAIL" for x in c.issues) else "BLOCKED" if c.issues else "PASS"
    def f(value):
        return None if value is None else float(value)
    return {"schema": "kwt-ppa-intake-result-v1", "status": status,
            "scope": "evidence file integrity, declared bindings, arithmetic and qualification thresholds only",
            "official_physical_acceptance": "NOT_RUN",
            "physical_authenticity_independently_verified": False,
            "analysis_context_sha256": context_hash,
            "config_id": data.get("config_id"), "run_id": run_id,
            "metrics": {"incremental_area_mm2": f(total), "core_area_mm2": f(core),
                        "new_interface_area_mm2": f(interface), "internal_sram_area_mm2": f(macro_sum),
                        "reused_area_mm2_report_only": f(reused_sum),
                        "area_margin_mm2": f(None if total is None else Decimal("2.25") - total),
                        "strict_area_threshold_satisfied": None if total is None else total < Decimal("2.25"),
                        "whole_window_seconds": f(duration), "tasks": task_count,
                        "whole_system_average_w": f(watts),
                        "whole_window_energy_j": f(None if duration is None or watts is None else duration * watts),
                        "energy_per_task_j": f(None if duration is None or watts is None or not task_count else duration * watts / task_count),
                        "throughput_tasks_per_second": f(None if duration is None or not task_count else Decimal(task_count) / duration)},
            "metrics_usable_for_comparison": status == "PASS",
            "issues": c.issues, "verified_files": c.verified_files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input", type=Path)
    mode.add_argument("--template", action="store_true")
    parser.add_argument("--config-id", default="opt_1x8_pipe1")
    parser.add_argument("--root", type=Path, default=ROOT, help="base for relative evidence paths")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = None
    try:
        if args.template:
            result, code = template(args.config_id, args.root), 0
        else:
            input_hash = sha256(args.input)
            data = strict_json(args.input.read_text())
            result = check(data, args.root)
            result["input_evidence"] = ref(args.input)
            if result["input_evidence"]["sha256"] != input_hash:
                raise ValueError("input changed while checking")
            result["checker_evidence"] = ref(Path(__file__).resolve())
            result["command"] = [sys.executable, *sys.argv]
            code = {"PASS": 0, "FAIL": 2, "BLOCKED": 3}[result["status"]]
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        result = {"schema": "kwt-ppa-intake-result-v1", "status": "FAIL",
                  "official_physical_acceptance": "NOT_RUN", "error": str(exc)}
        code = 2
    if not args.template or code:
        result["exit_code"] = code
        result["end_marker"] = "PPA_INTAKE_COMPLETE"
    rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        protected = referenced_paths(data, args.root) | referenced_paths(result, args.root)
        if args.input:
            protected.add(args.input.resolve())
        protected.add(Path(__file__).resolve())
        if args.output.resolve() in protected:
            print("refusing to overwrite input/evidence/checker", file=sys.stderr)
            return 2
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered)
        except OSError as exc:
            print("cannot write result: " + str(exc), file=sys.stderr)
            return 2
        print(json.dumps({"status": result.get("status", "TEMPLATE"), "output": str(args.output),
                          "exit_code": code, "end_marker": "PPA_INTAKE_COMPLETE"}))
    else:
        print(rendered, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
