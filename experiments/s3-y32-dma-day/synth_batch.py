#!/usr/bin/env python3
"""Freeze and optionally execute the explicitly gated final cell-area batch.

Preparation alone invokes no synthesis. --run requires a successful complete
real-CPU dual-row12 result and an explicit authorization marker. SRAM behavioral
models are blackboxed before processing; this flow cannot establish STA/PPA.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LIB_SHA="8d540a4d4cf6d09d27c87ad067857a9c0c2eeb023ab7a56e058cd3113db4e9b1"
DEADLINE=datetime.fromisoformat("2026-11-09T23:59:00+08:00")


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,value): p.write_text(json.dumps(value,indent=2)+"\n")
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


CANDIDATE_WRAPPER=r'''// Exact candidate boundary: independent DMA + its peripheral arbiter.
// CPU core, original memory fabric and shared SRAM endpoint are external.
module DmaAreaBoundary(
 input clk,rst_n,
 input cfg_cmd_valid,output cfg_cmd_ready,
 input [31:0] cfg_cmd_addr,input cfg_cmd_read,
 input [31:0] cfg_cmd_wdata,input [3:0] cfg_cmd_wmask,
 output cfg_rsp_valid,input cfg_rsp_ready,output cfg_rsp_err,output [31:0] cfg_rsp_rdata,
 input cpu_cmd_valid,output cpu_cmd_ready,input [31:0] cpu_cmd_addr,input cpu_cmd_read,
 input [31:0] cpu_cmd_wdata,input [3:0] cpu_cmd_wmask,
 output cpu_rsp_valid,input cpu_rsp_ready,output cpu_rsp_err,output [31:0] cpu_rsp_rdata,
 output mem_cmd_valid,input mem_cmd_ready,output [31:0] mem_cmd_addr,output mem_cmd_read,
 output [31:0] mem_cmd_wdata,output [3:0] mem_cmd_wmask,
 input mem_rsp_valid,output mem_rsp_ready,input mem_rsp_err,input [31:0] mem_rsp_rdata
);
 wire dma_cmd_valid,dma_cmd_ready,dma_cmd_read,dma_rsp_valid,dma_rsp_ready,dma_rsp_err;
 wire [31:0] dma_cmd_addr,dma_cmd_wdata,dma_rsp_rdata;
 wire [3:0] dma_cmd_wmask;
 xu_matrix_dma dma (
  .clk(clk),.rst_n(rst_n),
  .cfg_cmd_valid(cfg_cmd_valid),.cfg_cmd_ready(cfg_cmd_ready),.cfg_cmd_addr(cfg_cmd_addr),
  .cfg_cmd_read(cfg_cmd_read),.cfg_cmd_wdata(cfg_cmd_wdata),.cfg_cmd_wmask(cfg_cmd_wmask),
  .cfg_rsp_valid(cfg_rsp_valid),.cfg_rsp_ready(cfg_rsp_ready),.cfg_rsp_err(cfg_rsp_err),.cfg_rsp_rdata(cfg_rsp_rdata),
  .mem_cmd_valid(dma_cmd_valid),.mem_cmd_ready(dma_cmd_ready),.mem_cmd_addr(dma_cmd_addr),
  .mem_cmd_read(dma_cmd_read),.mem_cmd_wdata(dma_cmd_wdata),.mem_cmd_wmask(dma_cmd_wmask),
  .mem_rsp_valid(dma_rsp_valid),.mem_rsp_ready(dma_rsp_ready),.mem_rsp_err(dma_rsp_err),.mem_rsp_rdata(dma_rsp_rdata)
 );
 xu_dma_shared_arb arb (.*);
endmodule
'''


def prepare(args):
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    gate=json.loads(args.gate.read_text())
    assert gate["status"]=="PASS" and gate["arguments"]["tasks"]==12 and gate["arguments"]["dual"]==1
    assert gate["outputs"]==304128 and gate["source_drift"]==[]
    assert gate["principal_cycles"]<5874840,"Candidate must demonstrate improvement before area selection"
    candidate=args.gate.resolve().parent/"source/rtl/perips"
    baseline=args.baseline.resolve()
    inventory=module("storage_inventory",HERE/"storage_inventory.py")
    inventories={"baseline":inventory.inventory(baseline,"accel_icb_slave"),
                 "candidate":inventory.inventory(candidate,"xu_matrix_dma")}
    source=out/"source";source.mkdir()
    origins={}
    for name,inv in inventories.items():
        directory=source/name;directory.mkdir()
        chosen={Path(v["source"]) for v in inv["modules"].values()}
        chosen.add((baseline if name=="baseline" else candidate)/"mem_1024x16.sv")
        if name=="candidate": chosen.add(candidate/"xu_dma_shared_arb.v")
        for path in sorted(chosen):
            dest=directory/path.name;shutil.copy2(path,dest)
            origins[str(dest.relative_to(out))]=dict(origin=str(path),sha256=sha(path))
    (source/"candidate/DmaAreaBoundary.sv").write_text(CANDIDATE_WRAPPER)
    liberty=ROOT/"assets/libs/nangate45/NangateOpenCellLibrary_typical.lib"
    assert sha(liberty)==LIB_SHA
    (source/"lib").mkdir();shutil.copy2(liberty,source/"lib/NangateOpenCellLibrary_typical.lib")
    for filename in ("synth_batch.py","storage_inventory.py","check_mapped_area.py"):
        shutil.copy2(HERE/filename,source/filename)
    shutil.copy2(args.gate,source/"functional-gate.json")
    tops={"baseline":"accel_icb_slave","candidate":"DmaAreaBoundary"}
    for name,top in tops.items():
        directory=out/name;directory.mkdir()
        files=sorted((source/name).glob("*.v"))+sorted((source/name).glob("*.sv"))
        script=["read_liberty -lib source/lib/NangateOpenCellLibrary_typical.lib"]
        script += ["read_verilog -sv -DSYNTHESIS "+str(p.relative_to(out)) for p in files]
        script += ["blackbox mem_1024x16"]
        if name=="baseline": script += ["chparam -set DIRECT_ENABLE 1 accel_icb_slave"]
        script += [f"hierarchy -check -top {top}","proc","flatten",
                   "opt -full" if args.bounded_opt_full else "opt_clean","check -assert",
                   f"write_json {name}/elaborated.json",f"synth -top {top} -flatten -noabc",
                   "dfflibmap -liberty source/lib/NangateOpenCellLibrary_typical.lib",
                   "abc -liberty source/lib/NangateOpenCellLibrary_typical.lib","clean -purge","check -assert",
                   f"write_json {name}/mapped.json",f"write_verilog -noattr {name}/mapped.v",
                   f"tee -o {name}/stat.json stat -json -liberty source/lib/NangateOpenCellLibrary_typical.lib"]
        (directory/"map.ys").write_text("\n".join(script)+"\n")
    tools={}
    for name in ("yosys","yosys-abc"):
        path=Path(shutil.which(name) or "/missing");assert path.exists(),name
        tools[name]=dict(path=str(path),sha256=sha(path))
    manifest={str(p.relative_to(out)):sha(p) for p in sorted(source.rglob("*")) if p.is_file()}
    manifest.update({f"{name}/map.ys":sha(out/name/"map.ys") for name in tops})
    report=dict(schema="dma_day_final_cell_area_batch_v1",status="PREPARED_NOT_RUN",created_at=datetime.now(timezone.utc).isoformat(),
       authorization=args.authorized_final_batch,bounded_opt_full=args.bounded_opt_full,
       gate=str(args.gate.resolve()),gate_sha256=sha(args.gate),gate_principal_cycles=gate["principal_cycles"],
       inputs=manifest,origins=origins,tools=tools,tops=tops,
       synthesis_conditions=dict(liberty_sha256=LIB_SHA,nominal_process=1.0,temperature_C=25,voltage_V=1.10,
         clock_target="none; identical unconstrained area mapping",defines=["SYNTHESIS"],flatten=True,
         baseline_parameters=dict(DIRECT_ENABLE=1),candidate_dual="variable through public cfg input; not specialized away",
         macro_blackbox="mem_1024x16;17 required in each design;Sram1024x16 wrapper remains logic"),
       scope="Mapped standard-cell area for accelerator peripheral boundary; baseline accel_icb_slave DIRECT_ENABLE1 +8PE, candidate DMA+16PE+peripheral arbiter. CPU, originalLSU/BIU/fabric, shared endpoint, SRAM macro area/timing, wiring/place/parasitics omitted. Not whole-SoC area or150MHz STA/formal qualification.")
    dump(out/"result.json",report)
    return out,report


def execute(out,report):
    if datetime.now(timezone.utc)>=DEADLINE: raise RuntimeError("Deadline reached; no new experiment")
    if not report["authorization"]: raise RuntimeError("Explicit root final-batch authorization marker required")
    auditor=module("check_mapped_area",out/"source/check_mapped_area.py")
    results={};commands=[]
    for name,top in report["tops"].items():
        if datetime.now(timezone.utc)>=DEADLINE: raise RuntimeError("Deadline reached; no further new mapping")
        cmd=[report["tools"]["yosys"]["path"],"-l",f"{name}/yosys.log",f"{name}/map.ys"]
        begin=time.monotonic()
        proc=subprocess.run(cmd,cwd=out,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                            timeout=min(3600,max(1,(DEADLINE-datetime.now(timezone.utc)).total_seconds())))
        (out/name/"console.log").write_text(proc.stdout)
        commands.append(dict(command=cmd,cwd=str(out),returncode=proc.returncode,seconds=time.monotonic()-begin))
        report["commands"]=commands;dump(out/"result.json",report)
        if proc.returncode:
            if report["bounded_opt_full"]:
                results[name]=dict(status="FLOW_FAILED",returncode=proc.returncode,log=f"{name}/console.log",
                                  scope="No area from this design; structural/check failure preserved")
                continue
            raise RuntimeError(f"{name} Yosys failed; see {name}/console.log")
        net=json.loads((out/name/"mapped.json").read_text())
        elaborated=json.loads((out/name/"elaborated.json").read_text())
        for design,label in ((elaborated,"elaborated"),(net,"mapped")):
            mod=design["modules"][top]
            macros=[(key,cell) for key,cell in mod["cells"].items() if cell["type"]=="mem_1024x16"]
            assert len(macros)==17,(name,label,len(macros))
            for key,cell in macros:
                assert {p:len(v) for p,v in cell["connections"].items()}==dict(RW0_addr=10,RW0_en=1,RW0_clk=1,RW0_wmode=1,RW0_wdata=16,RW0_rdata=16),(key,cell)
        audit=auditor.audit(out/name/"mapped.json",out/name/"stat.json",out/"source/lib/NangateOpenCellLibrary_typical.lib",top,
                            macros=("mem_1024x16",),metadata=("$scopeinfo",))
        # Mapped sequential logic must survive in addition to the17 macros.
        assert sum(v["count"] for k,v in audit["per_cell"].items() if k.startswith(("DFF","SDFF","DFFE","DFFR","DFFS")))>100
        audit["mapped_macro_instances"]=[key for key,cell in net["modules"][top]["cells"].items() if cell["type"]=="mem_1024x16"]
        dump(out/name/"area-audit.json",audit);results[name]=audit
    drift=[name for name,digest in report["inputs"].items() if sha(out/name)!=digest]
    assert not drift,drift
    if any(result.get("status")=="FLOW_FAILED" for result in results.values()):
        report.update(status="PARTIAL_MAPPING_WITH_FLOW_FAILURE",results=results,source_drift=drift,
          standard_cell_area_delta_percent=None,whole_soc_25_percent_budget="UNVERIFIED: no valid comparable baseline mapping",
          sta_150mhz="NOT_MEASURED",formal_qualification="NOT_VERIFIED",finished_at=datetime.now(timezone.utc).isoformat())
        dump(out/"result.json",report)
        return
    old=float(results["baseline"]["standard_cell_area_liberty_units"])
    new=float(results["candidate"]["standard_cell_area_liberty_units"])
    report.update(status="MAPPED_CELL_AREA_PASS",results=results,source_drift=drift,
                  baseline_standard_cell_area=old,candidate_standard_cell_area=new,standard_cell_area_delta_percent=100*(new-old)/old,
                  whole_soc_25_percent_budget="UNVERIFIED: omitted CPU/fabric/sharedRAM/macro areas; boundary cell-only delta is not whole-SoC delta",
                  sta_150mhz="NOT_MEASURED",formal_qualification="NOT_VERIFIED",finished_at=datetime.now(timezone.utc).isoformat())
    dump(out/"result.json",report)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gate",type=Path,required=True)
    ap.add_argument("--baseline",type=Path,default=ROOT/"build/bias-demand-20261109/full12/source/rtl/perips")
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--run",action="store_true")
    ap.add_argument("--authorized-final-batch",action="store_true")
    ap.add_argument("--bounded-opt-full",action="store_true",
                    help="Explicitly authorized single same-RTL opt-full retry; preserve failures and still map the candidate once")
    args=ap.parse_args();out,report=prepare(args)
    try:
        if args.run: execute(out,report)
    except Exception as exc:
        report.update(status="FAILED",error=str(exc),finished_at=datetime.now(timezone.utc).isoformat())
        dump(out/"result.json",report);raise


if __name__=="__main__": main()
