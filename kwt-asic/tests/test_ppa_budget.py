"""Synthetic intake fixtures test accounting, never establish real technology PPA."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/synth/check_ppa_budget.py"
spec = importlib.util.spec_from_file_location("ppa_budget", SCRIPT)
ppa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ppa)


class PPABudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kwt-ppa-unit-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.data = ppa.template("opt_1x8_pipe1")
        self.data.update(run_id="SYNTHETIC-UNIT-TEST", technology_status="official_designated")
        self.data["notes"] = ["Synthetic numbers/files: NOT a project PPA result."]
        def artifact(name):
            p = self.directory / name
            p.write_text("SYNTHETIC UNIT TEST ONLY " + name + "\n")
            return ppa.ref(p)
        self.artifact = artifact
        self.data["artifacts"] = {name: artifact(name) for name in ppa.ARTIFACTS}
        corners = {role: role + "-synthetic-corner" for role in ppa.ROLES}
        self.data["libraries"] = {
            role: {"corner_id": corners[role], "process": "SYNTHETIC", "voltage_v": 1,
                   "temperature_c": 25, "standard_cells": [artifact(role + ".lib")]}
            for role in ppa.ROLES}
        self.data["analysis_conditions"] = {
            name: artifact(name) for name in self.data["analysis_conditions"]}
        self.basis = artifact("unit-basis")
        def item(value, instances):
            return {"value": value, "unit": "mm2", "unit_basis": self.basis,
                    "instances": instances, "zero_justification": None}
        area = self.data["area"]
        area.update(inventory_complete=True, core=item(.7, ["soc/acc/mac"]),
                    new_interface=item(.1, ["soc/acc/iface"]))
        area["macros"] = [{"cell_name": "TEST_SP", "count": 2,
                           "per_instance_area": item(.01, []),
                           "instances": ["soc/acc/ram0", "soc/acc/ram1"],
                           "functional_model": artifact("internal-model.v"),
                           "libraries": {role: artifact("internal-" + role + ".lib") for role in ppa.ROLES},
                           "corner_ids": corners}]
        area["reused"] = {name: item(2, ["soc/" + name]) for name in
                          ("e203", "shared_sram", "interconnect", "fixed_peripherals")}
        area["reused"]["shared_sram"]["models"] = [
            {"cell_name": "TEST_SHARED", "instances": ["soc/shared_sram"],
             "functional_model": artifact("shared-model.v"),
             "libraries": {role: artifact("shared-" + role + ".lib") for role in ppa.ROLES},
             "corner_ids": corners}]
        timing = self.data["timing"]
        for key in timing:
            if key not in ("binding", "frequency_mhz"):
                timing[key] = 0
        timing.update(clock_period_ns=1000 / 150, setup_wns_ns=.1, hold_wns_ns=.05,
                      constraints_reviewed=True, all_required_modes_and_corners_covered=True)
        self.data["window"].update(start_cycle=0, end_cycle=120, tasks=[
            {"task_id": "layer-" + str(i), "layer": i, "start_cycle": i * 10,
             "end_cycle": (i + 1) * 10, "cache_cleared_before_load": True,
             "includes_all_loads": True, "includes_cpu_schedule": True,
             "writeback_complete": True} for i in range(12)])
        power = self.data["power"]
        power.update(full_hierarchy_covered=True, activity_matches_mapped_netlist=True)
        for name, domain in power["domains"].items():
            if name in ("core", "new_interface"):
                instances = area[name]["instances"]
            elif name == "internal_sram":
                instances = area["macros"][0]["instances"]
            else:
                instances = area["reused"][name]["instances"]
            domain.update(dynamic=1, leakage=.1, unit="mW", instances=instances,
                          activity_required_objects=10, activity_annotated_objects=10)
        self.rebind()

    def rebind(self):
        binding = {name + "_sha256": self.data["artifacts"][name]["sha256"]
                   for name in ("configuration", "netlist", "sdc")}
        binding.update(run_id=self.data["run_id"],
                       analysis_context_sha256=ppa.canonical_hash(ppa.analysis_context(self.data)))
        for name in ("area", "timing", "power"):
            self.data[name]["binding"] = dict(binding)
        wh = ppa.canonical_hash(self.data["window"])
        self.data["power"]["window_sha256"] = wh
        self.data["artifact_bindings"] = {name: dict(binding, window_sha256=wh) for name in ppa.GENERATED}

    def result(self):
        return ppa.check(self.data)

    def assert_status(self, status):
        result = self.result()
        self.assertEqual(result["status"], status, result["issues"])
        return result

    def cli(self, content=None, *extra):
        source = self.directory / "input.json"
        source.write_text(json.dumps(self.data) if content is None else content)
        return subprocess.run([sys.executable, "-B", str(SCRIPT), "--input", str(source), *extra],
                              text=True, capture_output=True)

    def test_complete_synthetic_intake_and_arithmetic(self):
        r = self.assert_status("PASS")
        self.assertEqual(r["official_physical_acceptance"], "NOT_RUN")
        self.assertFalse(r["physical_authenticity_independently_verified"])
        self.assertEqual(r["metrics"]["incremental_area_mm2"], .82)
        self.assertEqual(r["metrics"]["reused_area_mm2_report_only"], 8)
        self.assertAlmostEqual(r["metrics"]["whole_system_average_w"], .0077)
        self.assertAlmostEqual(r["metrics"]["whole_window_energy_j"], .0077 * 120 / 150e6)
        self.assertAlmostEqual(r["metrics"]["energy_per_task_j"], .0077 * 10 / 150e6)

    def test_missing_template_is_blocked_not_zero(self):
        r = ppa.check(ppa.template("opt_1x8_pipe1"))
        self.assertEqual(r["status"], "BLOCKED")
        for key in ("incremental_area_mm2", "whole_system_average_w", "whole_window_energy_j"):
            self.assertIsNone(r["metrics"][key])
        self.assertFalse(r["metrics_usable_for_comparison"])

    def test_strict_area_boundary(self):
        for area, status in ((2.129999, "PASS"), (2.13, "FAIL"), (2.130001, "FAIL")):
            with self.subTest(area=area):
                self.data["area"]["core"]["value"] = area
                self.assert_status(status)

    def test_um2_conversion(self):
        self.data["area"]["core"].update(value=700000, unit="um2")
        self.assertEqual(self.assert_status("PASS")["metrics"]["incremental_area_mm2"], .82)

    def test_unknown_unit_is_fail(self):
        self.data["area"]["core"]["unit"] = "library_area"
        self.assert_status("FAIL")

    def test_missing_core_measurement_is_blocked(self):
        self.data["area"]["core"]["value"] = None
        self.assert_status("BLOCKED")

    def test_missing_library_file_is_blocked(self):
        Path(self.data["libraries"]["setup"]["standard_cells"][0]["path"]).unlink()
        self.assert_status("BLOCKED")

    def test_file_tamper_is_fail(self):
        Path(self.data["artifacts"]["netlist"]["path"]).write_text("changed\n")
        self.assert_status("FAIL")

    def test_empty_report_is_fail(self):
        p = Path(self.data["artifacts"]["area_report"]["path"])
        p.write_text("")
        self.data["artifacts"]["area_report"] = ppa.ref(p)
        self.assert_status("FAIL")

    def test_duplicate_area_instance_is_fail(self):
        self.data["area"]["new_interface"]["instances"] = ["soc/acc/mac"]
        self.assert_status("FAIL")

    def test_parent_and_descendant_area_is_fail(self):
        self.data["area"]["new_interface"]["instances"] = ["soc/acc"]
        self.assert_status("FAIL")

    def test_macro_count_mismatch_is_fail(self):
        self.data["area"]["macros"][0]["count"] = 3
        self.rebind()
        self.assert_status("FAIL")

    def test_macro_corner_mismatch_is_fail(self):
        self.data["area"]["macros"][0]["corner_ids"] = dict.fromkeys(ppa.ROLES, "wrong")
        self.rebind()
        self.assert_status("FAIL")

    def test_stale_pvt_context_is_fail(self):
        self.data["libraries"]["power"]["voltage_v"] = .9
        self.assert_status("FAIL")

    def test_mixed_netlist_binding_is_fail(self):
        self.data["power"]["binding"]["netlist_sha256"] = "a" * 64
        self.assert_status("FAIL")

    def test_negative_setup_and_hold_fail(self):
        for key in ("setup_wns_ns", "hold_wns_ns"):
            with self.subTest(key=key):
                old = self.data["timing"][key]
                self.data["timing"][key] = -.001
                self.assert_status("FAIL")
                self.data["timing"][key] = old

    def test_unconstrained_path_fail(self):
        self.data["timing"]["unconstrained_endpoints"] = 1
        self.assert_status("FAIL")

    def test_clock_mismatch_fail(self):
        self.data["timing"]["clock_period_ns"] = 10
        self.assert_status("FAIL")

    def test_whole_window_must_include_final_writeback(self):
        self.data["window"]["tasks"][-1]["end_cycle"] = 119
        self.rebind()
        self.assert_status("FAIL")

    def test_tasks_cannot_overlap(self):
        self.data["window"]["tasks"][1]["start_cycle"] = 9
        self.rebind()
        self.assert_status("FAIL")

    def test_layer_coverage_fail(self):
        self.data["window"]["tasks"][-1]["layer"] = 10
        self.rebind()
        self.assert_status("FAIL")

    def test_cache_clear_assertion_false_fails(self):
        self.data["window"]["tasks"][0]["cache_cleared_before_load"] = False
        self.rebind()
        self.assert_status("FAIL")

    def test_power_window_mismatch_fail(self):
        self.data["power"]["window_sha256"] = "a" * 64
        self.assert_status("FAIL")

    def test_activity_binding_mismatch_fail(self):
        self.data["artifact_bindings"]["activity"]["window_sha256"] = "b" * 64
        self.assert_status("FAIL")

    def test_missing_reused_domain_power_blocks(self):
        self.data["power"]["domains"]["e203"]["leakage"] = None
        self.assert_status("BLOCKED")

    def test_power_omits_instance_fail(self):
        self.data["power"]["domains"]["internal_sram"]["instances"] = ["soc/acc/ram0"]
        self.assert_status("FAIL")

    def test_uncovered_activity_blocks(self):
        self.data["power"]["domains"]["core"]["activity_annotated_objects"] = 9
        self.assert_status("BLOCKED")

    def test_unjustified_zero_power_blocks(self):
        self.data["power"]["domains"]["shared_sram"]["dynamic"] = 0
        self.assert_status("BLOCKED")

    def test_missing_shared_sram_models_blocks(self):
        self.data["area"]["reused"]["shared_sram"]["models"] = None
        self.rebind()
        self.assert_status("BLOCKED")

    def test_boolean_or_nonfinite_measurement_fails(self):
        for value in (True, float("inf"), float("nan"), -1, 10**500):
            with self.subTest(value=str(value)[:20]):
                self.data["area"]["core"]["value"] = value
                self.assert_status("FAIL")

    def test_cli_rejects_duplicate_keys_and_nonfinite(self):
        for content in ('{"schema": "a", "schema": "b"}', '{"x": NaN}', '[]'):
            with self.subTest(content=content):
                result = self.cli(content)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)["status"], "FAIL")

    def test_cli_pass_has_provenance_and_blocked_exit(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = json.loads(result.stdout)
        self.assertEqual(data["checker_evidence"]["sha256"], ppa.sha256(SCRIPT))
        result = self.cli(json.dumps(ppa.template("opt_1x8_pipe1")))
        self.assertEqual(result.returncode, 3)

    def test_cli_protects_input_and_report_files(self):
        for destination in (self.directory / "input.json", Path(self.data["artifacts"]["area_report"]["path"])):
            with self.subTest(path=str(destination)):
                result = self.cli(None, "--output", str(destination))
                self.assertEqual(result.returncode, 2)
                self.assertIn("refusing to overwrite", result.stderr)

    def test_cli_protects_failed_evidence(self):
        destination = Path(self.data["artifacts"]["area_report"]["path"])
        destination.write_text("tampered but must not overwrite\n")
        result = self.cli(None, "--output", str(destination))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(destination.read_text(), "tampered but must not overwrite\n")


if __name__ == "__main__":
    unittest.main()
