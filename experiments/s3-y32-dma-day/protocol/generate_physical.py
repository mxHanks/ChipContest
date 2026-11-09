"""Read-only physical pin connections; no writes/deposits/array access."""
from pathlib import Path

def generate(path):
    lines=['integer physical_w=0,physical_b=0,physical_x=0;',
           'reg physical_observing=0;',
           'reg [1023:0] clear_seen_w[0:15];',
           'reg [767:0] clear_seen_b;',
           'reg [63:0] clear_seen_x[0:3];',
           'integer physical_i;',
           'always @(posedge clk)if(rst_n)begin',
           'if(dut.clear_request)begin physical_w=0;physical_b=0;physical_x=0;physical_observing=1;',
           'for(physical_i=0;physical_i<16;physical_i=physical_i+1)clear_seen_w[physical_i]=0;',
           'for(physical_i=0;physical_i<4;physical_i=physical_i+1)clear_seen_x[physical_i]=0;',
           'clear_seen_b=0;end']
    for bank in range(8):
        for half in range(2):
            i=bank*2+half
            p=f'dut.u_core.weights.banks_{bank}.sram{half}.mem_ext'
            lines += [f'if(physical_observing&&{p}.RW0_en&&{p}.RW0_wmode)begin',
                      f'if({p}.RW0_wdata!==0||clear_seen_w[{i}][{p}.RW0_addr])$fatal(1,"physical W clear address/data");',
                      f'clear_seen_w[{i}][{p}.RW0_addr]=1;physical_w=physical_w+1;end']
    p='dut.u_core.bias.memory.mem_ext'
    lines += [f'if(physical_observing&&{p}.RW0_en&&{p}.RW0_wmode)begin',
              f'if({p}.RW0_addr>=768||{p}.RW0_wdata!==0||clear_seen_b[{p}.RW0_addr])$fatal(1,"physical bias clear address/data");',
              f'clear_seen_b[{p}.RW0_addr]=1;physical_b=physical_b+1;end']
    for set_ in range(2):
        for row in range(2):
            i=set_*2+row;p=f'dut.u_core.xs_{set_}_{row}'
            lines += [f'if(physical_observing&&{p}.io_wen)begin',
                      f'if({p}.io_wdata!==0||clear_seen_x[{i}][{p}.io_waddr])$fatal(1,"physical X clear address/data");',
                      f'clear_seen_x[{i}][{p}.io_waddr]=1;physical_x=physical_x+1;end']
    lines += ['if(dut.core_clear_done)begin',
              'if(!physical_observing||physical_w!=16384||physical_b!=768||physical_x!=256)$fatal(1,"physical clear coverage");',
              'for(physical_i=0;physical_i<16;physical_i=physical_i+1)if(!(&clear_seen_w[physical_i]))$fatal(1,"W clear missing address");',
              'for(physical_i=0;physical_i<4;physical_i=physical_i+1)if(!(&clear_seen_x[physical_i]))$fatal(1,"X clear missing address");',
              'if(!(&clear_seen_b))$fatal(1,"bias clear missing address");physical_observing=0;end',
              'end']
    Path(path).write_text('\n'.join(lines)+'\n')

if __name__=='__main__':
    import sys
    generate(sys.argv[1])
