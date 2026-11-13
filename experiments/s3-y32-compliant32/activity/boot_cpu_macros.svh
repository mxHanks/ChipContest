// Testbench-only initialization of boot firmware, never tensor/result data.
// This follows the generic RAMSP1024X16 model's actual interleaved array layout.
reg activity_firmware_loaded = 0;
wire [31:0] activity_boot_macro_done;
genvar activity_boot_bank, activity_boot_lane;
generate
  for (activity_boot_bank=0;activity_boot_bank<8;activity_boot_bank=activity_boot_bank+1) begin: activity_boot_banks
    for (activity_boot_lane=0;activity_boot_lane<4;activity_boot_lane=activity_boot_lane+1) begin: activity_boot_lanes
      reg done = 0;
      integer address, bit_index;
      assign activity_boot_macro_done[4*activity_boot_bank+activity_boot_lane] = done;
      initial begin
        wait(activity_firmware_loaded);
        for(address=0;address<1024;address=address+1)
          for(bit_index=0;bit_index<16;bit_index=bit_index+1)
            `ITCM.macro_storage.depth_bank[activity_boot_bank].width_lane[activity_boot_lane].macro.mem[address>>2][4*bit_index+(address&3)] =
              program_bytes[(activity_boot_bank*1024+address)*8+activity_boot_lane*2+bit_index/8][bit_index%8];
        done=1;
      end
    end
  end
endgenerate
