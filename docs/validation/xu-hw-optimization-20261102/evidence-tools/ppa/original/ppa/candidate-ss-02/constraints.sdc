create_clock -name xu_clk -period 6.666666667 [get_ports clk]
set_clock_uncertainty 0.1 [get_clocks xu_clk]
set_clock_transition 0.1 [get_clocks xu_clk]
set xu_data_inputs [remove_from_collection [all_inputs] [get_ports clk]]
set_input_delay 0.5 -clock xu_clk $xu_data_inputs
set_input_transition 0.1 $xu_data_inputs
set_output_delay 0.5 -clock xu_clk [all_outputs]
set_load 0.01 [all_outputs]
set_false_path -from [get_ports rst_n]
