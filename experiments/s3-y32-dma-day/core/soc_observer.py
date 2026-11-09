#!/usr/bin/env python3
"""Generate an inline read-only CPU-SoC physical-clear observer.

Only hierarchical reads appear in the emitted include. Dirtiness is recorded
from accepted physical write pins, never created with force/deposit or writes.
The CPU harness provides `CORE and `DMA hierarchy macros and the clock `clk`.
"""
import argparse
from pathlib import Path


def generate(path: Path):
    macros = [f"`CORE.weights.banks_{b}.sram{h}.mem_ext" for b in range(8) for h in range(2)]
    macros += ["`CORE.bias.memory.mem_ext"]
    xs = [f"`CORE.xs_{s}_{r}" for s in range(2) for r in range(2)]
    payload = [f"{x}.data_{k}" for x in xs for k in range(64)]
    payload += [f"`CORE.engines_{r}.peArray.pes_{lane}.ACC" for r in range(2) for lane in range(8)]
    payload += [f"`CORE.engines_{r}.resultReg_{lane}" for r in range(2) for lane in range(8)]
    payload += [f"`CORE.results_{s}_{r}_{lane}" for s in range(2) for r in range(2) for lane in range(8)]
    payload += [f"`CORE.bias.slotData_{s}_{lane}" for s in range(2) for lane in range(8)]
    cat = lambda paths: "{" + ", ".join(reversed(paths)) + "}"
    wires = {
        "[16:0] dma_phys_en": cat([p + ".RW0_en" for p in macros]),
        "[16:0] dma_phys_write": cat([p + ".RW0_wmode" for p in macros]),
        "[169:0] dma_phys_addr": cat([p + ".RW0_addr" for p in macros]),
        "[271:0] dma_phys_data": cat([p + ".RW0_wdata" for p in macros]),
        "[3:0] dma_phys_x_en": cat([p + ".io_wen" for p in xs]),
        "[23:0] dma_phys_x_addr": cat([p + ".io_waddr" for p in xs]),
        "[63:0] dma_phys_x_data": cat([p + ".io_wdata" for p in xs]),
        "dma_phys_payload_zero": " &&\n    ".join(f"({p} === 0)" for p in payload),
    }
    text = "// Generated read-only physical-clear monitor. No hierarchical writes.\n"
    text += "\n".join(f"  wire {name} = {value};" for name, value in wires.items())
    text += r'''
  reg dma_phys_observing=0;
  integer dma_phys_clears=0,dma_phys_writes_w=0,dma_phys_writes_b=0,dma_phys_writes_x=0;
  integer dma_phys_cycles=0,dma_phys_w_dirty_before=0,dma_phys_b_dirty_before=0,dma_phys_x_dirty_before=0;
  reg [1023:0] dma_phys_seen_w[0:15],dma_phys_dirty_w[0:15];
  reg [767:0] dma_phys_seen_b=0,dma_phys_dirty_b=0;
  reg [63:0] dma_phys_seen_x[0:3],dma_phys_dirty_x[0:3];
  integer dma_phys_i,dma_phys_j,dma_phys_address;
  initial begin
    for(integer i=0;i<16;i=i+1)begin dma_phys_seen_w[i]=0;dma_phys_dirty_w[i]=0;end
    for(integer i=0;i<4;i=i+1)begin dma_phys_seen_x[i]=0;dma_phys_dirty_x[i]=0;end
  end
  always @(posedge clk) begin : dma_physical_clear_observation
    if(`CORE.reset !== 1'b0)begin
      dma_phys_observing=0;dma_phys_clears=0;
      dma_phys_seen_b=0;dma_phys_dirty_b=0;
      for(dma_phys_i=0;dma_phys_i<16;dma_phys_i=dma_phys_i+1)begin
        dma_phys_seen_w[dma_phys_i]=0;dma_phys_dirty_w[dma_phys_i]=0;
      end
      for(dma_phys_i=0;dma_phys_i<4;dma_phys_i=dma_phys_i+1)begin
        dma_phys_seen_x[dma_phys_i]=0;dma_phys_dirty_x[dma_phys_i]=0;
      end
    end else begin
      if(`CORE.io_abort)begin
        // An abort invalidates this observation; it never makes a completed
        // physical-clear claim. A subsequent clear starts fresh coverage.
        dma_phys_observing=0;
      end
      if(`CORE.io_clearValid && `CORE.io_clearReady)begin
        if(dma_phys_observing) $fatal(1,"physical clear overlaps a prior clear");
        if(`DMA.pending || `DMA.locked || `CORE.io_active || `CORE.io_outValid)
          $fatal(1,"physical clear started before owners drained");
        dma_phys_observing=1;dma_phys_cycles=0;
        dma_phys_writes_w=0;dma_phys_writes_b=0;dma_phys_writes_x=0;
        dma_phys_w_dirty_before=0;dma_phys_b_dirty_before=0;dma_phys_x_dirty_before=0;
        for(dma_phys_i=0;dma_phys_i<16;dma_phys_i=dma_phys_i+1)begin
          dma_phys_seen_w[dma_phys_i]=0;
          for(dma_phys_j=0;dma_phys_j<1024;dma_phys_j=dma_phys_j+1)
            dma_phys_w_dirty_before=dma_phys_w_dirty_before+dma_phys_dirty_w[dma_phys_i][dma_phys_j];
        end
        dma_phys_seen_b=0;
        for(dma_phys_j=0;dma_phys_j<768;dma_phys_j=dma_phys_j+1)
          dma_phys_b_dirty_before=dma_phys_b_dirty_before+dma_phys_dirty_b[dma_phys_j];
        for(dma_phys_i=0;dma_phys_i<4;dma_phys_i=dma_phys_i+1)begin
          dma_phys_seen_x[dma_phys_i]=0;
          for(dma_phys_j=0;dma_phys_j<64;dma_phys_j=dma_phys_j+1)
            dma_phys_x_dirty_before=dma_phys_x_dirty_before+dma_phys_dirty_x[dma_phys_i][dma_phys_j];
        end
        if(!warmup_active && dma_phys_clears>0 &&
          (dma_phys_w_dirty_before==0 || dma_phys_b_dirty_before==0 || dma_phys_x_dirty_before==0))
          $fatal(1,"counted task clear lacks prior public nonzero W/bias/X writes");
        $display("DMA_PHYSICAL_CLEAR_BEGIN call=%0d warmup=%0d nonzero_W=%0d nonzero_BIAS=%0d nonzero_X=%0d observed_last_public_writes=1",
          dma_phys_clears+1,warmup_active,dma_phys_w_dirty_before,dma_phys_b_dirty_before,dma_phys_x_dirty_before);
      end
      if(dma_phys_observing)dma_phys_cycles=dma_phys_cycles+1;
      for(dma_phys_i=0;dma_phys_i<17;dma_phys_i=dma_phys_i+1)begin
        if(dma_phys_en[dma_phys_i] && !dma_phys_write[dma_phys_i] && dma_phys_observing)
          $fatal(1,"physical SRAM read during exclusive clear");
        if(dma_phys_en[dma_phys_i] && dma_phys_write[dma_phys_i])begin
          dma_phys_address=dma_phys_addr[10*dma_phys_i+:10];
          if(dma_phys_i<16)
            dma_phys_dirty_w[dma_phys_i][dma_phys_address]=(dma_phys_data[16*dma_phys_i+:16]!==16'b0);
          else begin
            if(dma_phys_address>=768) $fatal(1,"physical bias address outside 768-word aperture");
            dma_phys_dirty_b[dma_phys_address]=(dma_phys_data[16*dma_phys_i+:16]!==16'b0);
          end
          if(dma_phys_observing)begin
            if(dma_phys_data[16*dma_phys_i+:16]!==16'b0) $fatal(1,"nonzero physical SRAM clear data");
            if(dma_phys_i<16)begin
              if(dma_phys_seen_w[dma_phys_i][dma_phys_address]) $fatal(1,"duplicate physical W clear address");
              dma_phys_seen_w[dma_phys_i][dma_phys_address]=1;
              dma_phys_writes_w=dma_phys_writes_w+1;
            end else begin
              if(dma_phys_seen_b[dma_phys_address]) $fatal(1,"duplicate physical bias clear address");
              dma_phys_seen_b[dma_phys_address]=1;dma_phys_writes_b=dma_phys_writes_b+1;
            end
          end
        end
      end
      for(dma_phys_i=0;dma_phys_i<4;dma_phys_i=dma_phys_i+1)if(dma_phys_x_en[dma_phys_i])begin
        dma_phys_address=dma_phys_x_addr[6*dma_phys_i+:6];
        dma_phys_dirty_x[dma_phys_i][dma_phys_address]=(dma_phys_x_data[16*dma_phys_i+:16]!==16'b0);
        if(dma_phys_observing)begin
          if(dma_phys_x_data[16*dma_phys_i+:16]!==16'b0 || dma_phys_seen_x[dma_phys_i][dma_phys_address])
            $fatal(1,"bad or duplicate physical X clear write");
          dma_phys_seen_x[dma_phys_i][dma_phys_address]=1;dma_phys_writes_x=dma_phys_writes_x+1;
        end
      end
      if(`CORE.io_clearDone)begin
        if(!dma_phys_observing || dma_phys_writes_w!=16384 || dma_phys_writes_b!=768 || dma_phys_writes_x!=256)
          $fatal(1,"incomplete physical clear totals W=%0d B=%0d X=%0d",dma_phys_writes_w,dma_phys_writes_b,dma_phys_writes_x);
        for(dma_phys_i=0;dma_phys_i<16;dma_phys_i=dma_phys_i+1)
          if((&dma_phys_seen_w[dma_phys_i])!==1'b1) $fatal(1,"physical W address coverage hole");
        if((&dma_phys_seen_b)!==1'b1) $fatal(1,"physical bias address coverage hole");
        for(dma_phys_i=0;dma_phys_i<4;dma_phys_i=dma_phys_i+1)
          if((&dma_phys_seen_x[dma_phys_i])!==1'b1) $fatal(1,"physical X address coverage hole");
        if(!dma_phys_payload_zero) $fatal(1,"physical X/ACC/result/FIFO/bias-cache payload not zero at clear_done");
        if(`DMA.y_payload!==256'b0 || `DMA.b_low!==32'b0 || `DMA.b_high!==8'b0)
          $fatal(1,"DMA snapshot/bias assembly payload not zero at clear_done");
        if(`DMA.pending || `DMA.locked || `CORE.io_active || `CORE.io_outValid)
          $fatal(1,"physical clear done with outstanding owners");
        dma_phys_clears=dma_phys_clears+1;dma_phys_observing=0;
        $display("DMA_PHYSICAL_CLEAR_PASS call=%0d warmup=%0d W=16384 BIAS=768 X=256 total16bit_writes=17408 physical_cycles=%0d X_REGS=256 ACC=16 ENGINE_RESULT=16 FIFO=32 BIAS_CACHE=16 DMA_SNAPSHOT=1 all_addresses=1 all_payload_zero=1",
          dma_phys_clears,warmup_active,dma_phys_cycles);
      end
    end
  end
'''
    path.write_text(text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    generate(args.output)
