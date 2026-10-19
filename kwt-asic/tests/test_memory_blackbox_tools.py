"""Fail-closed guards for the SRAM pre-synthesis evidence checker."""
from decimal import Decimal
import importlib.util
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

SYNTH = Path(__file__).resolve().parents[1] / "scripts/synth"
sys.path.insert(0, str(SYNTH))
SPEC = importlib.util.spec_from_file_location("run_memory_blackbox", SYNTH/"run_memory_blackbox.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def fixture():
    cells = {}
    modules = {MOD.TOP: {"cells": cells}}
    for depth, count in ((128, 50), (1024, 22)):
        name = "box"+str(depth)
        modules[name] = {"attributes": {"blackbox": 1, "hdlname": "kwt_sram_1rw_blackbox"},
                         "parameter_default_values": {"WIDTH": 16, "DEPTH": depth}}
        for i in range(count):
            cells[name+"_"+str(i)] = {"type": name}
    for i in range(16):
        cells["mac"+str(i)] = {"type": "$mul", "parameters":
            {"A_WIDTH": 16, "B_WIDTH": 16, "Y_WIDTH": 32, "A_SIGNED": 1, "B_SIGNED": 1}}
    return {"modules": modules}


class MemoryBlackboxGuards(unittest.TestCase):
    def test_internal_tool_error_rejects_zero_exit_and_outer_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            log=Path(directory)/'mapping.log'
            for error in ('ABC: Error: The command has failed.','ERROR: missing output.blif'):
                log.write_text(error+'\n'+MOD.MAP_MARKER+'\nEnd of script.\n')
                with self.assertRaises(RuntimeError):
                    MOD.completed({'exit_code':0,'timed_out':False},log,MOD.MAP_MARKER)

    def test_buffered_mapping_requires_abc_stage_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            log=Path(directory)/'mapping.log'
            outer=MOD.MAP_MARKER+'\nEnd of script.\n'
            log.write_text(outer)
            with self.assertRaises(RuntimeError):
                MOD.completed({'exit_code':0,'timed_out':False},log,MOD.MAP_MARKER,True)
            log.write_text('ABC: KWT_SRAM_ABC_BUFFERED_COMPLETE\n'+outer)
            MOD.completed({'exit_code':0,'timed_out':False},log,MOD.MAP_MARKER,True)
            log.write_text('ABC: KWT_SRAM_ABC_BUFFERED_COMPLETE\n'+log.read_text())
            with self.assertRaises(RuntimeError):
                MOD.completed({'exit_code':0,'timed_out':False},log,MOD.MAP_MARKER,True)

    def test_full_inventory_required(self):
        result = MOD.inspect_structure(fixture())
        self.assertEqual(result["opaque_cell_count"], 72)
        self.assertEqual(result["configured_memory_bits"], 462848)
        self.assertEqual(result["logical_memory_bits"], 415744)

    def test_missing_macro_rejected(self):
        design = fixture()
        del design["modules"][MOD.TOP]["cells"]["box128_0"]
        with self.assertRaises(ValueError): MOD.inspect_structure(design)

    def test_memory_array_or_ff_expansion_rejected(self):
        for extra in ({"type": "$mem_v2"}, {"type": "$dff", "parameters": {"WIDTH": 415744}}):
            design = fixture()
            design["modules"][MOD.TOP]["cells"]["accidental_storage"] = extra
            with self.assertRaises(ValueError): MOD.inspect_structure(design)

    def test_unsigned_or_missing_mac_rejected(self):
        design = fixture()
        design["modules"][MOD.TOP]["cells"]["mac0"]["parameters"]["A_SIGNED"] = 0
        with self.assertRaises(ValueError): MOD.inspect_structure(design)

    def test_unknown_box_is_not_free_logic(self):
        design = fixture()
        design["modules"]["box128"]["attributes"]["hdlname"] = "unexplained_macro"
        with self.assertRaises(ValueError): MOD.inspect_structure(design)

    def test_mapping_excludes_unknown_sram_area(self):
        design = fixture()
        cells = design["modules"][MOD.TOP]["cells"]
        for key in list(cells):
            if key.startswith("mac"): del cells[key]
        cells["logic"] = {"type": "AND2_X1"}
        result = MOD.mapped_logic(design, {"box128", "box1024"}, {"AND2_X1": Decimal("1.064")})
        self.assertEqual(result["standard_cells"], 1)
        self.assertEqual(result["opaque_cell_count"], 72)
        self.assertIsNone(result["sram_area_mm2"])
        self.assertEqual(result["official_area_requirement"], "BLOCKED")
        cells["unmapped"] = {"type": "$logic_that_never_mapped"}
        with self.assertRaises(ValueError): MOD.mapped_logic(design, {"box128", "box1024"}, {"AND2_X1": Decimal("1.064")})

    def test_full_ff_requires_explicit_opt_in(self):
        run = subprocess.run([sys.executable, str(SYNTH/"run_memory_ff_reference.py"), "--full-engine"],
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertEqual(run.returncode, 2)
        self.assertIn("require --allow-full-ff", run.stdout)


if __name__ == "__main__":
    unittest.main()
