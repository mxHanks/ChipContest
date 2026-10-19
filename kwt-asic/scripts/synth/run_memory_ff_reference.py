#!/usr/bin/env python3
"""Explicit bounded FF+MUX synthesis; default is only a 16x128 test primitive.

Full engine expansion requires --full-engine --allow-full-ff and is guarded by
a process address-space cap and timeout. FF area is never SRAM macro area.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import sys
import time
import uuid

from run_structural import ROOT, integer, record
from run_nangate_reference import LIB_SHA256, library_areas, measured_logic
sys.path.insert(0,str(ROOT/'scripts/verify'))
import sram_sources as SOURCES

MARKER = "KWT_SRAM_FF_REFERENCE_COMPLETE"


def bounded(command, cwd, logfile, timeout, memory_mib):
    def limit():
        bound = memory_mib * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (bound, bound))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    start = time.monotonic()
    with logfile.open("w") as log:
        process = subprocess.Popen(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True, preexec_fn=limit)
        timed_out = False
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try: code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
    return {"argv": command, "cwd": str(cwd), "exit_code": code, "timed_out": timed_out,
            "memory_limit_MiB": memory_mib, "elapsed_seconds": round(time.monotonic()-start,6),
            "log": record(logfile)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--full-engine", action="store_true")
    p.add_argument("--allow-full-ff", action="store_true")
    p.add_argument("--map-logic", action="store_true")
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--memory-limit-mib", type=int, default=4096)
    p.add_argument("--output-dir", type=Path)
    args = p.parse_args()
    if args.full_engine and not args.allow_full_ff:
        p.error("full-capacity FF expansion is deliberately disabled; require --allow-full-ff")
    if args.allow_full_ff and not args.full_engine:
        p.error("--allow-full-ff requires --full-engine")
    if args.timeout <= 0 or not 512 <= args.memory_limit_mib <= 4096:
        p.error("timeout must be positive; memory limit must be 512..4096 MiB")
    top = "kwt_linear_engine_rowpair_sram" if args.full_engine else "kwt_sram_ff_reference"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out = (args.output_dir or ROOT/"artifacts/runs"/(stamp+"-sram-ff-reference-"+uuid.uuid4().hex[:8])).resolve()
    out.mkdir(parents=True, exist_ok=False)
    sources = [ROOT/"src/rtl/memory/kwt_sram_1rw.sv", ROOT/"src/rtl/memory/kwt_sram_1rw_blackbox.sv"]
    if args.full_engine:
        sources += [ROOT/"src/rtl/memory/kwt_sram_bank.sv", ROOT/"src/rtl"/(top+".sv")]
    tool = ROOT/".tools/bin/yosys"
    lib = ROOT/"ChipContest/assets/libs/nangate45/NangateOpenCellLibrary_typical.lib"
    result = {"schema":"kwt-sram-ff-reference-v1", "status":"FAIL", "run_directory":str(out),
              "configuration":{"top":top,"backend":"FF_FALLBACK","full_engine":args.full_engine,
                               "map_logic":args.map_logic,"memory_limit_MiB":args.memory_limit_mib,"timeout_seconds":args.timeout},
              "scope":"full engine FF+MUX expansion" if args.full_engine else "single 128x16 FF_FALLBACK primitive; not full engine",
              "official_sram_ppa":"NOT_APPLICABLE", "static_timing":"NOT_RUN", "power":"NOT_RUN",
              "inputs":[],"commands":[]}
    try:
        backend=SOURCES.select_backend('ff','synthesis',allow_full_ff=True)
        sources=backend['sources'] if args.full_engine else [backend['sources'][0]]
        dependencies = sources+backend['dependencies']+[Path(__file__),ROOT/"scripts/synth/run_structural.py",ROOT/"scripts/synth/run_nangate_reference.py",tool,
                                ROOT/".tools/synth/usr/bin/yosys",ROOT/".tools/synth/usr/bin/yosys-abc"]
        if args.map_logic: dependencies.append(lib)
        result["inputs"]=[record(x) for x in dependencies]
        names=[]
        for i, source in enumerate(sources):
            name=f"input-{i}.sv";names.append(name);(out/name).write_bytes(source.read_bytes())
        if not args.full_engine:
            (out/"unit.sv").write_text("""module kwt_sram_ff_reference(input clk,rst_n,wr_en,rd_en,
input [6:0] wr_addr,rd_addr,input [15:0] wr_data,output [15:0] rd_data,output rd_valid);
kwt_sram_1rw #(.WIDTH(16),.DEPTH(128),.BACKEND(2),.CHECKS(0)) memory
(.clk(clk),.rst_n(rst_n),.wr_en(wr_en),.wr_addr(wr_addr),.wr_data(wr_data),
.rd_en(rd_en),.rd_addr(rd_addr),.rd_data(rd_data),.rd_valid(rd_valid));
endmodule
""")
            names.append("unit.sv")
        lines=["read_verilog -sv -defer -D SYNTHESIS "+" ".join(names)]
        if args.full_engine:
            lines.append(f"chparam -set SRAM_BACKEND 2 -set SRAM_CHECKS 0 -set PIPE_MUL 1 -set RESULT_BUFFERS 2 {top}")
        lines += ["hierarchy -check -top "+top,"proc","opt","memory_dff","memory_collect","flatten","opt_clean",
                  "check -assert","write_json retained.json","memory_map","opt","check -assert","stat -width",
                  "write_json ff-structure.json"]
        if args.map_logic:
            if record(lib)["sha256"] != LIB_SHA256:raise ValueError("reference Liberty SHA mismatch")
            quoted='"'+str(lib)+'"'
            lines += ["read_liberty -lib "+quoted,"synth -top "+top+" -noabc","dfflibmap -liberty "+quoted,
                      "abc -fast -D 6667 -liberty "+quoted,"clean","check -assert","stat -liberty "+quoted,
                      "write_json mapped.json","write_verilog -noattr -noexpr mapped.v"]
        lines += ["log "+MARKER, ""]
        (out/"run.ys").write_text("\n".join(lines))
        with (ROOT/".tools/synth/structural.lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            version=bounded([str(tool),"-V"],out,out/"version.log",15,args.memory_limit_mib)
            result["commands"].append(version);result["tool_version"]=(out/"version.log").read_text().strip()
            run=bounded([str(tool),"-Q","-s","run.ys"],out,out/"synthesis.log",args.timeout,args.memory_limit_mib)
            result["commands"].append(run)
        log=(out/"synthesis.log").read_text()
        if run["exit_code"] or run["timed_out"] or len(re.findall("^"+MARKER+"$",log,re.M)) != 1 or "End of script." not in log:
            raise RuntimeError("FF synthesis failed or bounded out; original exit/log preserved")
        design=json.loads((out/"ff-structure.json").read_text())["modules"][top]
        cells=design["cells"]
        if design.get("memories") or any(c["type"].startswith("$mem") for c in cells.values()):
            raise ValueError("FF mode retained unexpected memory")
        result["ff_structure"]={"register_bits":sum(integer(c["parameters"]["WIDTH"]) for c in cells.values() if c["type"].startswith(("$dff","$adff","$sdff"))),
                                "cell_types":dict(Counter(c["type"] for c in cells.values())),"remaining_memory_cells":0}
        if result["ff_structure"]["register_bits"] < (415744 if args.full_engine else 2048):
            raise ValueError("too few storage FF bits; payload may have been optimized away")
        if args.map_logic:
            result["mapped_ff_logic"]=measured_logic(json.loads((out/"mapped.json").read_text()),top,library_areas(lib.read_text()))
            result["mapped_ff_logic"]["scope"]="FF standard-cell implementation only; never an SRAM-macro PPA result"
        for item in result["inputs"]:
            if record(item["path"])["sha256"] != item["sha256"]:raise ValueError("input changed during FF synthesis")
        result["status"]="PASS"
    except Exception as exc:result["error"]=type(exc).__name__+": "+str(exc)
    result["outputs"]=[record(x) for x in sorted(out.iterdir()) if x.is_file() and x.name!="result.json"]
    (out/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"report":str(out/"result.json"),"scope":result["scope"],"error":result.get("error")}))
    return 0 if result["status"]=="PASS" else 1


if __name__=="__main__":raise SystemExit(main())
