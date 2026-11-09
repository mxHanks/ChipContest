#!/usr/bin/env python3
"""Source-level clocked storage inventory; no synthesis or area inference.

Counts declared widths only when the named register receives a nonblocking
assignment. Combinational temporaries, simulator random variables and macro
behavioral models are excluded. Optimization may change mapped flop counts.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def plain(text):
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.S)


def registers(path):
    text = plain(path.read_text())
    found = {}
    # Internal declarations, including comma-separated names and fixed arrays.
    for match in re.finditer(r"(?m)^\s*reg\s+(?:signed\s+)?(?:\[(\d+):(\d+)\]\s*)?([^;]+);", text):
        width = abs(int(match[1])-int(match[2]))+1 if match[1] else 1
        for part in match[3].split(","):
            entry = re.fullmatch(r"\s*(\w+)\s*(?:\[(\d+):(\d+)\])?\s*(?:=.*)?", part, re.S)
            if not entry:
                raise ValueError(f"Unrecognized register declaration in {path}: {part!r}")
            name = entry[1]
            if re.search(r"\b"+re.escape(name)+r"(?:\[[^;\n]*?\])?\s*<=", text):
                elements = abs(int(entry[2])-int(entry[3]))+1 if entry[2] else 1
                found[name] = dict(width=width,elements=elements,bits=width*elements)
    # ANSI output registers are outside the internal declaration grammar.
    for match in re.finditer(r"\boutput\s+reg\s+(?:\[(\d+):(\d+)\]\s*)?(\w+)", text):
        name = match[3]
        width = abs(int(match[1])-int(match[2]))+1 if match[1] else 1
        if re.search(r"\b"+re.escape(name)+r"(?:\[[^;\n]*?\])?\s*<=", text):
            found[name] = dict(width=width,elements=1,bits=width)
    return found


def inventory(directory, top, extra=()):
    paths = sorted(directory.glob("*.sv"))+sorted(directory.glob("*.v"))+list(extra)
    sources = {}
    for path in paths:
        text = plain(path.read_text())
        modules = re.findall(r"\bmodule\s+(\w+)",text)
        if len(modules)==1:
            if modules[0] in sources: raise ValueError("Duplicate module "+modules[0])
            sources[modules[0]] = path
    instances=[]; per_module=Counter(); active=set()
    known = "|".join(map(re.escape,sources))
    def walk(kind, inst):
        if kind in active: raise ValueError("Recursive module "+kind)
        per_module[kind]+=1
        instances.append(dict(path=inst,module=kind))
        if kind=="mem_1024x16": return
        active.add(kind)
        text=plain(sources[kind].read_text())
        for match in re.finditer(r"(?m)^\s*("+known+r")\s+(?:#\s*\([^;]*?\)\s*)?(\w+)\s*\(",text):
            walk(match[1],inst+"."+match[2])
        active.remove(kind)
    walk(top,top)
    descriptions={}
    for kind,count in sorted(per_module.items()):
        if kind=="mem_1024x16": continue
        regs=registers(sources[kind])
        bits=sum(r["bits"] for r in regs.values())
        descriptions[kind]=dict(instances=count,bits_per_instance=bits,total_bits=bits*count,registers=regs,
                                source=str(sources[kind].resolve()),sha256=sha(sources[kind]))
    macros=per_module["mem_1024x16"]
    return dict(top=top,module_counts=dict(per_module),clocked_register_bits=sum(v["total_bits"] for v in descriptions.values()),
                modules=descriptions,instances=instances,macro_count=macros,macro_capacity_bits=macros*1024*16)


def report(baseline,candidate,dma):
    old=inventory(baseline,"accel_icb_slave")
    new=inventory(candidate,"LinearRowPairDmaCore")
    dma_regs=registers(dma); arb_regs=registers(dma.with_name("xu_dma_shared_arb.v"))
    dma_bits=sum(v["bits"] for v in dma_regs.values());arb_bits=sum(v["bits"] for v in arb_regs.values())
    assert old["macro_count"]==new["macro_count"]==17,(old["macro_count"],new["macro_count"])
    assert old["module_counts"]["MacPE"]==8 and new["module_counts"]["MacPE"]==16
    assert old["module_counts"]["XRowBuffer"]==1 and new["module_counts"]["XRowBuffer"]==4
    assert new["modules"]["XRowBuffer"]["bits_per_instance"]==1024
    assert arb_bits==5,arb_regs
    core_regs=new["modules"]["LinearRowPairDmaCore"]["registers"]
    pair_results=sum(v["bits"] for k,v in core_regs.items() if k.startswith("results_"))
    bias_regs=new["modules"]["BiasSramPrefetch"]["registers"]
    bias_slots=sum(v["bits"] for k,v in bias_regs.items() if k.startswith("slotData_"))
    assert pair_results==1536 and bias_slots==640
    assert dma_regs["y_payload"]["bits"]==256
    total=new["clocked_register_bits"]+dma_bits+arb_bits
    return dict(schema="dma_day_source_storage_v1",baseline=old,candidate_core=new,
      dma=dict(path=str(dma.resolve()),sha256=sha(dma),clocked_register_bits=dma_bits,registers=dma_regs),
      arbiter=dict(path=str(dma.with_name("xu_dma_shared_arb.v").resolve()),sha256=sha(dma.with_name("xu_dma_shared_arb.v")),clocked_register_bits=arb_bits,registers=arb_regs),
      baseline_boundary_clocked_register_bits=old["clocked_register_bits"],candidate_boundary_clocked_register_bits=total,
      boundary_register_delta_bits=total-old["clocked_register_bits"],
      capacities=dict(weight=dict(macros=16,physical_bits=16*1024*16,logical_bits=16384*16,delta_bits=0),
        bias=dict(macros=1,physical_bits=16384,used_physical_bits=768*16,logical_bits=256*40,delta_bits=0),
        x_pingpong=dict(bits=4096,bytes=512,baseline_bits=1024,delta_bits=3072),
        core_result_slots=dict(bits=pair_results,bytes=192,baseline_bits=768,delta_bits=768),
        dma_snapshot=dict(bits=256,bytes=32,included_in_dma_register_total=True),
        bias_cache_slots=dict(bits=bias_slots,bytes=80,included_in_bias_module_total=True,delta_bits=0)),
      interfaces=dict(core_added_input_bits=20,core_added_input_signals=["abort","xLoadSet","xRunSet","wLoadPacked","wLoadDataHi[15:0]"],
        external_dma_master="one ordered outstanding ICB request; cmd71 bits including ready, rsp35 bits including ready",
        arbitration="peripheral CPU/DMA round-robin;5 state bits; originalCPU/LSU/BIUunchanged",
        configuration="existing accelerator peripheral aperture, candidate descriptor/control/status offsets0x300..0x37f"),
      scope="Declared source clocked payload/control widths before synthesis optimization; excluded macro behavioral pipeline regs, simulator random vars, and combinational temporaries. No gate-area, total-SoC-area, STA or formal-qualification claim.")


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline",type=Path,default=ROOT/"build/bias-demand-20261109/full12/source/rtl/perips")
    ap.add_argument("--candidate",type=Path,default=ROOT/"generated/LinearRowPairDmaCore")
    ap.add_argument("--dma",type=Path,default=ROOT/"third-party/e203_hbirdv2/rtl/e203/perips/xu_matrix_dma.sv")
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args();args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report(args.baseline,args.candidate,args.dma),indent=2)+"\n")


if __name__=="__main__": main()
