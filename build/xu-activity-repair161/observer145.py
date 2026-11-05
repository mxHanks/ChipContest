"""Passive instrumentation and CPU clearing protocols; no DUT assignments."""
from pathlib import Path
from context145 import require, sha


def recipe(profile):
    writes = []
    cache = profile!='s1_h2_only'
    if cache: writes.append((0x40,0))
    for bank in range(8):
        writes.append((0x1c,bank))
        for address in range(2048): writes.extend(((0x20,address),(0x24,0)))
    if cache:
        for column in range(256): writes.extend(((0x44,column),(0x48,0),(0x4c,0)))
    for lane in range(8): writes.extend(((0x28,lane),(0x2c,0),(0x30,0)))
    if profile=='s2d':
        writes.extend(((0x40,1),(0xd0,1)))
        for bank in range(2):
            writes.append((0xd8,bank<<8))
            writes.extend([(0xdc,0)]*32)
        writes.extend(((0xd0,0),(0x40,0)))
    else:
        for address in range(64): writes.extend(((0x14,address),(0x18,0)))
    expected = 32928 if not cache else 33639 if profile=='s2d' else 33697
    require(len(writes)==expected, 'clear recipe geometry differs')
    return writes


def firmware_wrapper(main, profile):
    main = Path(main).resolve()
    require(not any(c in str(main) for c in ('"','\\','\n','\r')), 'unrepresentable main path')
    cache = profile!='s1_h2_only'
    body = ['/* xu145 original main SHA256 '+sha(main)+' */', '#define main xu_frozen_task_main',
            '#include "'+str(main)+'"', '#undef main',
            'static int xu_clear145(void) {',
            'volatile uint32_t *const reg=(volatile uint32_t *)0x10042000u;',
            'if(reg[0]!=0xacce2030u || (reg[3]&1u) || reg[0x50/4]!='+
            ('0x58550003u' if cache else '0x58550002u')+') return -1;']
    if cache: body.append('reg[0x40/4]=0;')
    body += ['for(unsigned bank=0;bank<8;++bank){reg[0x1c/4]=bank;',
             'for(unsigned a=0;a<2048;++a){reg[0x20/4]=a;reg[0x24/4]=0;}}']
    if cache: body.append('for(unsigned c=0;c<256;++c){reg[0x44/4]=c;reg[0x48/4]=0;reg[0x4c/4]=0;}')
    body.append('for(unsigned lane=0;lane<8;++lane){reg[0x28/4]=lane;reg[0x2c/4]=0;reg[0x30/4]=0;}')
    if profile=='s2d':
        body += ['reg[0x40/4]=1;reg[0xd0/4]=1;',
                 'for(unsigned bank=0;bank<2;++bank){reg[0xd8/4]=bank<<8;',
                 'for(unsigned a=0;a<32;++a)reg[0xdc/4]=0;}',
                 'reg[0xd0/4]=0;reg[0x40/4]=0;']
    else: body.append('for(unsigned a=0;a<64;++a){reg[0x14/4]=a;reg[0x18/4]=0;}')
    body += ['__asm__ volatile("fence iorw, iorw" ::: "memory");return 0;}',
             'int main(void){if(xu_clear145())return 17;return xu_frozen_task_main();}','']
    return '\n'.join(body)


def declarations(ctx, recipe_path):
    profile = ctx.id
    cache = profile!='s1_h2_only'
    count = len(recipe(profile))
    manual = profile in ('baseline_h1_h2','s1_h2_only','s1_sram_bias')
    rows = profile in ('s2d','pe32','pe64','compact32_128')
    xwen = '`ACCEL.u_linear_compute_core.io_xLoadWen'
    xaddr = '`ACCEL.u_linear_compute_core.io_xLoadAddr'
    xdata = '`ACCEL.u_linear_compute_core.io_xLoadData'
    if profile=='s2d':
        xwen = '(`ACCEL.db_mode ? `ACCEL.u_linear_compute_core.io_dbXLoadWen : `ACCEL.u_linear_compute_core.io_xLoadWen)'
        xaddr = '(`ACCEL.db_mode ? `ACCEL.u_linear_compute_core.io_dbXLoadAddr : `ACCEL.u_linear_compute_core.io_xLoadAddr)'
        xdata = '(`ACCEL.db_mode ? `ACCEL.u_linear_compute_core.io_dbXLoadData : `ACCEL.u_linear_compute_core.io_xLoadData)'
    ownership = ''
    reset_ownership = ''
    if rows:
        reset_ownership = '''if ({`ACCEL.row_active,`ACCEL.row_running,`ACCEL.row_count,
              `ACCEL.row_produced,`ACCEL.row_retired}!==0)
            $fatal(1,"XU145_REJECT row ownership not reset");'''
        ownership = '''if (`ACCEL.row_active || `ACCEL.row_running || `ACCEL.row_count!=0)
          $fatal(1,"XU145_REJECT nonempty row ownership at boundary");'''
    if profile=='s2d':
        ownership += '''if ({`ACCEL.db_mode,`ACCEL.db_outstanding,`ACCEL.db_queued,
          `ACCEL.db_count,`ACCEL.db_running}!==0 || `ACCEL.db_bank_free!==2'b11)
          $fatal(1,"XU145_REJECT DB ownership not empty/free");'''
        reset_ownership += '''if ({`ACCEL.db_outstanding,`ACCEL.db_queued,`ACCEL.db_count,`ACCEL.db_running}!==0 ||
          `ACCEL.db_bank_free!==2'b11) $fatal(1,"XU145_REJECT DB reset ownership");'''
    text = r'''
  integer xu_global_task=-1, xu_clear_stage=0, xu_clear_writes=0, xu_setup_writes=0;
  integer xu_saif_started=0, xu_saif_stopped=0, xu_request_cycle=-1, xu_accept_cycle=-1;
  integer xu_formal_cycles=0, xu_initial_wait=0, xu_ready=0, xu_reset_edges145=0;
  integer xu_w_count=0, xu_x_count=0, xu_bias_count=0;
  integer xu_clear_w_commits=0, xu_clear_x_commits=0, xu_clear_bias_commits=0;
  integer xu_clear_first_cycle=-1, xu_clear_last_cycle=-1, xu_i145;
  real xu_reset_first_tick145=-1, xu_reset_last_tick145=-1;
  reg [31:0] xu_request_addr;
  reg [43:0] xu_clear_expected [0:@COUNT@-1];
  reg [16383:0] xu_clear_w_seen=0, xu_w_seen=0;
  reg [4:0] xu_bias_seen [0:255], xu_clear_bias_seen [0:255];
  initial begin
    $readmemh("@RECIPE@",xu_clear_expected);
    for(xu_i145=0;xu_i145<256;xu_i145=xu_i145+1)begin
      xu_bias_seen[xu_i145]=0;xu_clear_bias_seen[xu_i145]=0;
    end
  end
  always @(posedge `ACCEL.clk) begin
    if (`ACCEL.rst_n===1'b0) begin
      if(xu_ready || xu_saif_started)$fatal(1,"XU145_REJECT late actual accelerator reset");
      if(xu_reset_edges145==0)xu_reset_first_tick145=$realtime*1000000.0;
      xu_reset_edges145=xu_reset_edges145+1;
      xu_reset_last_tick145=$realtime*1000000.0;
    end else if (`ACCEL.rst_n!==1'b1 && xu_reset_edges145>0)
      $fatal(1,"XU145_REJECT actual reset X after known reset");
  end
  task xu_boundary_idle145;
    integer a;
    begin
      if (`ACCEL.busy!==0 || `ACCEL.core_start!==0 ||
          `ACCEL.u_linear_compute_core.io_wLoadWen!==0 || @XWEN@!==0 ||
          `ACCEL.u_linear_compute_core.io_cacheWriteEnable!==0)
        $fatal(1,"XU145_REJECT boundary compute/load not idle");
      @CACHE_IDLE@
      @OWNERSHIP@
      for(a=0;a<8;a=a+1)if(!xu_saif_started && `ACCEL.bias_regs[a]!==40'b0)
        $fatal(1,"XU145_REJECT actual legacy bias not zero");
    end
  endtask
  task xu_observe145;
    integer a,b,logical_index;
    reg source_request,source_accept,w_commit,x_commit,b_commit;
    reg [4:0] old_mask,new_mask;
    begin
      source_request=cmd_valid && cmd_read && cmd_addr>=BASE && cmd_addr<BASE+'h18800;
      source_accept=source_request && cmd_ready;
      if (`ACCEL.rst_n!==1'b1) begin
        if(xu_ready || xu_saif_started || `ACCEL.cmd_valid===1'b1 || source_request===1'b1)
          $fatal(1,"XU145_REJECT request/reset before actual ready or late reset");
      end else begin
        if(xu_reset_edges145<=0)$fatal(1,"XU145_REJECT no clock sampled actual reset");
        if(!xu_ready)begin
          xu_ready=1;
          @RESET_OWNERSHIP@
          $display("XU_RESET145 task=%0d edges=%0d first_tick=%0.0f last_tick=%0.0f ready_cycle=%0d ready_tick=%0.0f",xu_global_task,xu_reset_edges145,xu_reset_first_tick145,xu_reset_last_tick145,cycles,$realtime*1000000.0);
        end
        w_commit=`ACCEL.u_linear_compute_core.io_wLoadWen;
        x_commit=@XWEN@;
        b_commit=`ACCEL.u_linear_compute_core.io_cacheWriteEnable;
        if((^{w_commit,x_commit,b_commit})===1'bx)$fatal(1,"XU145_REJECT unknown actual commit control");
        if(w_commit)begin
          if((^{`ACCEL.u_linear_compute_core.io_wLoadBank,`ACCEL.u_linear_compute_core.io_wLoadAddr,
               `ACCEL.u_linear_compute_core.io_wLoadData})===1'bx)$fatal(1,"XU145_REJECT W X");
          a=`ACCEL.u_linear_compute_core.io_wLoadBank*2048+`ACCEL.u_linear_compute_core.io_wLoadAddr;
          logical_index=(`ACCEL.u_linear_compute_core.io_wLoadAddr%64)*256+
             (`ACCEL.u_linear_compute_core.io_wLoadAddr/64)*8+`ACCEL.u_linear_compute_core.io_wLoadBank;
          if(!xu_saif_started)begin
            if(xu_clear_w_seen[a] || `ACCEL.u_linear_compute_core.io_wLoadData!==16'b0)$fatal(1,"XU145_REJECT W clear commit");
            xu_clear_w_seen[a]=1;xu_clear_w_commits=xu_clear_w_commits+1;
          end else begin
            if(xu_saif_stopped || xu_w_seen[a] || `ACCEL.u_linear_compute_core.io_wLoadData!==w[logical_index])$fatal(1,"XU145_REJECT W fixture commit");
            xu_w_seen[a]=1;xu_w_count=xu_w_count+1;
          end
        end
        if(x_commit)begin
          if((^{@XADDR@,@XDATA@})===1'bx)$fatal(1,"XU145_REJECT X commit unknown");
          a=@XADDR@;
          if(!xu_saif_started)begin
            if(@XDATA@!==16'b0)$fatal(1,"XU145_REJECT nonzero X clear");
            xu_clear_x_commits=xu_clear_x_commits+1;
          end else begin
            if(xu_saif_stopped || xu_x_count>=6336 || a!=xu_x_count%64 || @XDATA@!==x[xu_x_count])$fatal(1,"XU145_REJECT X fixture/order commit");
            xu_x_count=xu_x_count+1;
          end
        end
        if(b_commit)begin
          a=`ACCEL.u_linear_compute_core.io_cacheWriteAddr;
          new_mask=`ACCEL.u_linear_compute_core.io_cacheWriteMask;
          old_mask=xu_saif_started ? xu_bias_seen[a] : xu_clear_bias_seen[a];
          if((^{a,new_mask,`ACCEL.u_linear_compute_core.io_cacheWriteData})===1'bx ||
             (new_mask!==5'b01111 && new_mask!==5'b10000) || (old_mask&new_mask)!=0 || xu_saif_stopped)
            $fatal(1,"XU145_REJECT bias commit/mask");
          for(b=0;b<5;b=b+1)if(new_mask[b] && `ACCEL.u_linear_compute_core.io_cacheWriteData[8*b+:8] !==
             (xu_saif_started ? bias[a][8*b+:8] : 8'b0))$fatal(1,"XU145_REJECT bias fixture/zero byte");
          if(xu_saif_started)xu_bias_seen[a]=old_mask|new_mask;else xu_clear_bias_seen[a]=old_mask|new_mask;
          if((old_mask|new_mask)==31)begin
            if(xu_saif_started)xu_bias_count=xu_bias_count+1;else xu_clear_bias_commits=xu_clear_bias_commits+1;
          end
        end
        if(!xu_saif_started)begin
          if(`ACCEL.core_start!==0)$fatal(1,"XU145_REJECT compute before task");
          if(`ACCEL.cmd_valid && `ACCEL.cmd_ready)begin
            if(`ACCEL.cmd_read)begin
              case(`ACCEL.cmd_addr[11:0])
                12'h000,12'h00c,12'h050,12'h070,12'h074,12'h078,12'h07c:begin end
                default:$fatal(1,"XU145_REJECT pretask MMIO read");
              endcase
            end else if(xu_clear_writes<@COUNT@)begin
              if(`ACCEL.cmd_wmask!==4'hf || {`ACCEL.cmd_addr[11:0],`ACCEL.cmd_wdata}!==xu_clear_expected[xu_clear_writes])
                $fatal(1,"XU145_REJECT clear accepted write index=%0d addr=%h data=%h",xu_clear_writes,`ACCEL.cmd_addr,`ACCEL.cmd_wdata);
              if(xu_clear_first_cycle<0)begin
                xu_clear_first_cycle=cycles;
                $display("XU_CLEAR_BEGIN145 task=%0d cycle=%0d tick=%0.0f",xu_global_task,cycles,$realtime*1000000.0);
              end
              xu_clear_last_cycle=cycles;xu_clear_writes=xu_clear_writes+1;
              if(xu_clear_writes==@COUNT@)$display("XU_CLEAR_LAST145 task=%0d cycle=%0d tick=%0.0f writes=@COUNT@",xu_global_task,cycles,$realtime*1000000.0);
            end else begin
              if(xu_setup_writes>=@SETUP@ || `ACCEL.cmd_wmask!==4'hf || `ACCEL.cmd_wdata!==0 ||
                 `ACCEL.cmd_addr[11:0]!=(xu_setup_writes==0 ? 12'h01c : 12'h020))$fatal(1,"XU145_REJECT pre-source task setup");
              xu_setup_writes=xu_setup_writes+1;
            end
          end
          if(source_request)begin
            xu_boundary_idle145();
            if(xu_clear_writes!=@COUNT@ || xu_setup_writes!=@SETUP@ || xu_clear_w_commits!=16384 ||
               xu_clear_w_seen!=={16384{1'b1}} || xu_clear_x_commits!=@XCLEAR@ || xu_clear_bias_commits!=@BIAS@)
              $fatal(1,"XU145_REJECT incomplete actual clear before REQUEST");
            xu_request_cycle=cycles;xu_request_addr=cmd_addr;xu_saif_started=1;xu_clear_stage=1;
`ifndef XU_TASK_ACTIVITY_HOST_CHECK
            $toggle_start();
`endif
            $display("XU_SOURCE_REQUEST145 task=%0d cycle=%0d tick=%0.0f clear_writes=@COUNT@ setup_writes=@SETUP@",xu_global_task,cycles,$realtime*1000000.0);
            $display("XU_ACTIVITY_BEGIN task=%0d tick=%0.0f",xu_global_task,$realtime*1000000.0);
          end
        end
        if(xu_request_cycle>=0 && xu_accept_cycle<0)begin
          if(!source_request || cmd_addr!==xu_request_addr)$fatal(1,"XU145_REJECT initial REQUEST unstable");
          if(source_accept)begin
            xu_accept_cycle=cycles;
            if(xu_initial_wait!=xu_accept_cycle-xu_request_cycle)$fatal(1,"XU145_REJECT initial wait accounting");
            $display("XU_SOURCE_ACCEPT145 task=%0d cycle=%0d tick=%0.0f",xu_global_task,cycles,$realtime*1000000.0);
          end else xu_initial_wait=xu_initial_wait+1;
        end
        if(xu_saif_started && !xu_saif_stopped)xu_formal_cycles=xu_formal_cycles+1;
      end
    end
  endtask
'''
    replacements = dict(COUNT=count, RECIPE=str(Path(recipe_path).resolve()), XWEN=xwen,XADDR=xaddr,XDATA=xdata,
                        CACHE_IDLE=('if(!xu_saif_started && `ACCEL.cache_enable!==0)$fatal(1,"XU145_REJECT cache enabled before task");' if cache else ''),
                        OWNERSHIP=ownership,RESET_OWNERSHIP=reset_ownership,SETUP=2 if manual else 0,
                        XCLEAR=128 if profile=='s2d' else 64,BIAS=256 if cache else 0)
    for key,value in replacements.items(): text=text.replace('@'+key+'@',str(value))
    require('@' not in text.replace('always @',''), 'observer substitution incomplete')
    return text


def lf_clock():
    return '''  integer xu_lf_index145=0, xu_lf_checks145=0;
  real xu_lf_target145;
  initial forever begin
    xu_lf_index145=xu_lf_index145+1;xu_lf_target145=xu_lf_index145*15258.7890625;
    #(xu_lf_target145-$realtime);
    if(($realtime-xu_lf_target145)>0.00000101 || ($realtime-xu_lf_target145)< -0.00000101)
      $fatal(1,"XU145_REJECT LF phase drift");
    xu_lf_checks145=xu_lf_checks145+1;lfclk=~lfclk;
  end'''


def generate_tb(ctx, recipe_path):
    text=ctx.base.generate_tb(True,'nominal150')
    once=ctx.base.once
    text=once(text,'  always #15258.7890625 lfclk = ~lfclk;',lf_clock())
    text=once(text,'  // Observation only: these counters never drive',declarations(ctx,recipe_path)+'\n  // Observation only: these counters never drive')
    text=once(text,'    #1; // Finish vendor initialization before the first HF edge.','''    if(!$value$plusargs("XU_GLOBAL_TASK=%d",xu_global_task) || xu_global_task<0 || xu_global_task>11 || tasks!=1)
      $fatal(1,"XU145_REJECT TASKS=1/global task required");
`ifndef XU_TASK_ACTIVITY_HOST_CHECK
    $set_gate_level_monitoring("rtl_on");$set_toggle_region(tb_xu_soc_ppa.dut);
`endif
    #1; // Finish vendor initialization before the first HF edge.''')
    text=once(text,'      // Match the existing inclusive first-input/final-Y-response interval.',
              '      xu_observe145();\n      // Match the existing inclusive first-input/final-Y-response interval.')
    text=once(text,'          $display("XU_ACTIVITY_BEGIN task=%0d tick=%0.0f",layer,$realtime*1000000.0);','')
    finish='''          xu_boundary_idle145();
          if(xu_request_cycle<0 || xu_accept_cycle<xu_request_cycle || xu_formal_cycles!=cycles-xu_request_cycle+1 ||
             xu_formal_cycles!=perf_cycles+xu_initial_wait || xu_w_count!=16384 || xu_x_count!=6336 || xu_bias_count!=@BIAS@ ||
             !xu_saif_started || xu_saif_stopped)$fatal(1,"XU145_REJECT final actual uploads/window");
`ifndef XU_TASK_ACTIVITY_HOST_CHECK
          $toggle_stop();
`endif
          xu_saif_stopped=1;xu_clear_stage=2;
          $display("XU_ACTIVITY_END task=%0d tick=%0.0f",xu_global_task,$realtime*1000000.0);
          $display("XU_WINDOW145 task=%0d request_cycle=%0d accept_cycle=%0d end_cycle=%0d initial_wait=%0d legacy_cycles=%0d formal_inclusive=%0d formal_elapsed=%0d",xu_global_task,xu_request_cycle,xu_accept_cycle,cycles,xu_initial_wait,perf_cycles,xu_formal_cycles,xu_formal_cycles-1);
          $display("XU_UPLOAD145 task=%0d w=16384 x=6336 bias=@BIAS@ actual_clear_w=16384 actual_clear_x=@XCLEAR@ actual_clear_bias=@BIAS@ checked_data=1",xu_global_task);
`ifndef XU_TASK_ACTIVITY_HOST_CHECK
          $toggle_report("task.saif",1.0e-15,"tb_xu_soc_ppa.dut");
`endif'''.replace('@BIAS@','0' if ctx.id=='s1_h2_only' else '256').replace('@XCLEAR@','128' if ctx.id=='s2d' else '64')
    text=once(text,'          $display("XU_ACTIVITY_END task=%0d tick=%0.0f",layer,$realtime*1000000.0);',finish)
    text=once(text,'        $display("XU_CLOCK_STATIC_PASS','''        if(!xu_saif_stopped || xu_lf_checks145<=0)$fatal(1,"XU145_REJECT missing end/LF");
        $display("XU_LF145 nominal_hz=32768 checked_edges=%0d max_phase_error_fs=1",xu_lf_checks145);
        $display("XU_CLOCK_STATIC_PASS''')
    return text
