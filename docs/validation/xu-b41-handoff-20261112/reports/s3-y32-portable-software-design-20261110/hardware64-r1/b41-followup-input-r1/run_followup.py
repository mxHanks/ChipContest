#!/usr/bin/env python3
"""Prepare and run B41 first-source stall and expected CPU/DMA error cases."""
import argparse
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
FPT_PROJECT = Path("/work/leo/chipcontest-xu-own155-diagnosis-20261105")
NORMAL = "b41-strict-input-r1"
MANIFEST_SHA = "1d8cd861b75c377ecd7282edd1fa1bdb7dae7a166078d43d6308e3010335a6c6"
GUARD_SHA = "6fdce8ba674a7d84d8878d5894b8236468807e8c7d26967f76b045f6a830a80c"
FAULT_TB_SHA = "ea27d4f0fdce755ed6ef794f6897a88a4ca6c798d56990a0aa3f4f7a971c4fb8"
STALL_CYCLES = 31
PASS = "PASS_CPU64_B41_FOLLOWUP"


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def strict_inputs(root):
    guard = root / "run_native.py"
    if root.is_symlink() or guard.is_symlink() or sha(guard) != GUARD_SHA:
        raise ValueError("B41 strict supervisor identity differs")
    load("b41_normal_guard", guard).inputs(MANIFEST_SHA)
    return read(root / "prepared.json")


def prepare(out):
    base = ROOT.parent / "hardware64-r1"
    normal = base / NORMAL
    strict_inputs(normal)
    fixture = base / "fault-fixture-r1/tb_dma64_fault_soc.sv"
    if sha(fixture) != FAULT_TB_SHA:
        raise ValueError("Fault fixture differs from the linted fixture")
    supervisor = (normal / "run_native.py").read_text()
    for old, new in (
        ("str(ROOT/'run_strict.py')", "str(ROOT/'run_followup.py')"),
        ("PASS_STRICT_CPU64_FULL12", PASS),
        ("Missing strict full12 terminal result", "Missing B41 follow-up terminal result"),
    ):
        if supervisor.count(old) != 1:
            raise ValueError("Unexpected strict supervisor layout")
        supervisor = supervisor.replace(old, new, 1)
    compile(supervisor, "run_native.py", "exec")
    out.mkdir(mode=0o700)
    (out / "run_native.py").write_text(supervisor)
    shutil.copyfile(__file__, out / "run_followup.py")
    shutil.copyfile(fixture, out / fixture.name)
    manifest = out / "INPUT.sha256"
    manifest.write_text("".join(f"{sha(path)}  {path.name}\n" for path in sorted(out.iterdir())))
    print("B41_FOLLOWUP_INPUT_PREPARED", sha(manifest), out)


def accepted_full12(root, prepared):
    native_path = root / "native-r1/result.json"
    campaign_path = root / "native-r1/campaign/result.json"
    native, campaign = read(native_path), read(campaign_path)
    child = native["child"]
    if (
        native["status"] != "PASS" or native["input_checksum_sha256"] != MANIFEST_SHA
        or native["qualification"] != "DEVELOPMENT_RTL_ONLY"
        or campaign["status"] != "PASS_STRICT_CPU64_FULL12"
        or child["native_exit"] != 0 or not child["waitpid_completed"]
        or child["events"] or child["remaining_group"] or child["remaining_at_leader_exit"]
    ):
        raise ValueError("B41 strict full12 campaign did not pass and drain")
    if (
        native["campaign_sha256"] != sha(campaign_path)
        or child["log_sha256"] != sha(root / "native-r1/control/native.log")
    ):
        raise ValueError("B41 strict receipt identity differs")
    source = root / "source"
    sources = {p.relative_to(source).as_posix(): sha(p) for p in source.rglob("*") if p.is_file()}
    binary = root / "native-r1/campaign/obj/dma64_soc"
    preprocessed = campaign_path.with_name("preprocessed.sv")
    if (
        sources != prepared["source_sha256"] or sources != campaign["source_sha256"]
        or sha(binary) != campaign["simulator_sha256"]
        or sha(preprocessed) != campaign["preprocessed_sha256"]
        or campaign["preprocessed_assert_property_count"] != 6
        or len(re.findall(r"assert\s+property\b", preprocessed.read_text())) != 6
        or "--assert" not in campaign["build_argv"]
        or any("DISABLE_SV_ASSERTION" in arg for arg in campaign["build_argv"])
    ):
        raise ValueError("B41 strict source, simulator or assertion proof differs")
    if set(campaign["variants"]) != set(prepared["software"]):
        raise ValueError("B41 strict firmware coverage differs")
    for name, meta in prepared["software"].items():
        row = campaign["variants"][name]
        measured = row["measurements"]
        if (
            row["firmware_image_sha256"] != meta["image_sha256"]
            or measured["outputs"] != 304128 or measured["warmup"]["outputs"] != 25344
            or len(measured["physical_clear"]) != 13
        ):
            raise ValueError("B41 strict full12 scope differs: " + name)
    return dict(native_sha256=sha(native_path), campaign_sha256=sha(campaign_path),
                input_manifest_sha256=MANIFEST_SHA, simulator_sha256=sha(binary)), binary


def check_stall(checker, runner, raw):
    measured = checker.check_log(raw, 1, 8, True)
    timeline = runner.measurements(checker, raw, measured)
    source_wait = [row["source_accepted"] - row["source_begin"] for row in timeline]
    if min(source_wait) < STALL_CYCLES:
        raise ValueError("First-source backpressure absent from raw timing")
    return dict(measurements=measured, timeline=timeline, first_source_wait_cycles=source_wait)


def check_fault(checker, raw, mode):
    if re.search(r"FATAL|%Error|TEST_FAIL|timeout|^Error(?:\s|:)|D4K_SOC_PASS", raw, re.I | re.M):
        raise ValueError("Unexpected simulation failure or success-task marker")
    injected = checker.records(raw, "XU_CPU64_FAULT_INJECT", ["mode", "cycle"])
    fields = ["mode", "error_publications", "requests", "responses",
              "return_code", "busy", "pending", "locked", "ack", "done"]
    terminal = checker.records(raw, "XU_CPU64_FAULT_PASS", fields)
    if len(injected) != 1 or len(terminal) != 1 or injected[0]["mode"] != mode:
        raise ValueError("Missing or duplicate fault injection/terminal")
    row = terminal[0]
    if (
        row["mode"] != mode or row["error_publications"] != 1 or row["return_code"] != 5
        or row["requests"] == 0 or row["requests"] != row["responses"]
        or any(row[key] for key in ("busy", "pending", "locked", "ack", "done"))
    ):
        raise ValueError("CPU error publication or transaction retirement differs")
    return dict(injection=injected[0], terminal=row, physical_clear=checker.check_physical_clear(raw, 1, False))


def run_case(runner, out, label, cpu, binary, image, vectors, workload):
    argv = ["taskset", "-c", str(cpu), str(binary), f"+TESTCASE={image}", f"+VECTORS={vectors}",
            "+TASKS=1", "+ROWS=8", "+MAX_CYCLES=20000000", *workload]
    log = out / (label + ".log")
    print("B41_FOLLOWUP_START", label, flush=True)
    raw = runner.run(argv, out, log, 900)
    return raw, dict(argv=argv, log_sha256=sha(log), firmware_image_sha256=sha(image.with_suffix(".verilog")))


def run(cpu):
    if ROOT.parent != FPT_PROJECT or cpu not in os.sched_getaffinity(0) or len(os.sched_getaffinity(0)) != 3:
        raise ValueError("B41 follow-up requires the guarded FPT candidate slot")
    normal = ROOT.parent / NORMAL
    prepared = strict_inputs(normal)
    full12, binary = accepted_full12(normal, prepared)
    source = normal / "source"
    runner = load("b41_strict_runner", normal / "run_strict.py")
    checker = load("b41_strict_checker", source / "check_results.py")
    fixture = ROOT / "tb_dma64_fault_soc.sv"
    if sha(fixture) != FAULT_TB_SHA:
        raise ValueError("B41 fault fixture identity differs")
    out = ROOT / "native-r1/campaign"
    out.mkdir()
    record = dict(status="RUNNING", accepted_full12=full12, fault_fixture_sha256=FAULT_TB_SHA,
                  stall_cases={}, fault_cases={})
    result = out / "result.json"
    runner.save(result, record)
    images = {name: normal / "firmware" / name / "dma64_soc" for name in prepared["software"]}
    try:
        for name, image in images.items():
            raw, row = run_case(runner, out, name + "-stall31", cpu, binary, image, normal / "vectors",
                                ["+WARMUP=1", f"+FIRST_SOURCE_STALL={STALL_CYCLES}", "+DUMPWAVE=0"])
            record["stall_cases"][name] = dict(**row, **check_stall(checker, runner, raw))
            runner.save(result, record)

        rtl = source / "rtl"
        files = sorted(p for p in rtl.rglob("*") if p.suffix in (".v", ".sv")) + [fixture]
        filelist = out / "fault-rtl.f"
        filelist.write_text("".join(f'"{path}"\n' for path in files))
        fault = out / "fault-obj/cpu64_fault"
        includes = [rtl / "core", rtl / "perips", rtl / "perips/apb_i2c", source / "tests"]
        common = ["--timing", "--assert", "--top-module", "tb_dma64_fault_soc",
                  "-DXU_MATRIX_DMA", "-DXU_MATRIX_DMA64", "-DD4K_THROTTLE=7",
                  *["-I" + str(p) for p in includes], "-f", str(filelist)]
        build = ["verilator", "--binary", "-CFLAGS", "-std=gnu++20", "-j", "2", "-Wno-fatal",
                 "-Mdir", str(fault.parent), "-o", fault.name, *common]
        preprocessed = out / "fault-preprocessed.sv"
        raw = runner.run(["verilator", "-E", *common], out, preprocessed, 120)
        count = len(re.findall(r"assert\s+property\b", raw))
        if count != 6:
            raise ValueError("B41 fault fixture did not preserve six CPU assertion properties")
        record.update(fault_build_argv=build, fault_preprocessed_sha256=sha(preprocessed),
                      fault_cpu_assert_properties=count)
        runner.run(build, out, out / "fault-build.log", 1200)
        record["fault_simulator_sha256"] = sha(fault)
        for name, image in images.items():
            for mode, operation in ((1, "read"), (2, "write")):
                label = name + "-" + operation
                raw, row = run_case(runner, out, label, cpu, fault, image, normal / "vectors",
                                    ["+WARMUP=0", "+FIRST_SOURCE_STALL=0", f"+FAULT={mode}"])
                record["fault_cases"][label] = dict(**row, **check_fault(checker, raw, mode))
                runner.save(result, record)
        if (
            strict_inputs(normal) != prepared or accepted_full12(normal, prepared)[0] != full12
            or sha(fault) != record["fault_simulator_sha256"]
        ):
            raise ValueError("B41 follow-up input drift")
        record["status"] = PASS
        print(PASS, len(record["stall_cases"]), len(record["fault_cases"]), flush=True)
    except Exception as error:
        record.update(status="FAIL", error=str(error))
        raise
    finally:
        runner.save(result, record)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--prepare-out", type=Path)
    operation.add_argument("--sim-cpu", type=int)
    args = parser.parse_args()
    if args.prepare_out is not None:
        prepare(args.prepare_out.resolve())
    else:
        run(args.sim_cpu)
