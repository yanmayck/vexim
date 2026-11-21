module \mem_controller (
  input logic \clk ,
  input logic \rst ,
  input logic \cmd_valid ,
  input logic \cmd_write ,
  input logic [39:0] \cmd_addr ,
  input logic [7:0] \cmd_beats ,
  input logic \w_valid ,
  input logic [63:0] \w_data ,
  input logic [7:0] \w_strb ,
  input logic \r_ready ,
  input logic \mem_ready ,
  input logic \mem_w_ready ,
  input logic \mem_r_valid ,
  input logic [63:0] \mem_r_data ,
  output logic \cmd_ready ,
  output logic \w_ready ,
  output logic \r_valid ,
  output logic [63:0] \r_data ,
  output logic \r_last ,
  output logic \mem_valid ,
  output logic \mem_write ,
  output logic [39:0] \mem_addr ,
  output logic [7:0] \mem_beats ,
  output logic \mem_w_valid ,
  output logic [63:0] \mem_w_data ,
  output logic [7:0] \mem_w_strb ,
  output logic \mem_r_ready ,
  output logic \done 
);
  logic \c0_1 ;
  logic [1:0] \c0_2 ;
  logic [1:0] \c1_2 ;
  logic [1:0] \c2_2 ;
  logic [7:0] \c1_8 ;
  logic [7:0] \c16_8 ;
  logic [1:0] \state ;
  logic [1:0] \next_state ;
  logic \is_write_reg ;
  logic \next_is_write ;
  logic [39:0] \addr_reg ;
  logic [39:0] \next_addr ;
  logic [7:0] \rem_beats_reg ;
  logic [7:0] \next_rem_beats ;
  logic [7:0] \cur_beats_reg ;
  logic [7:0] \next_cur_beats ;
  logic [7:0] \desc_beats_reg ;
  logic [7:0] \next_desc_beats ;
  logic \is_idle ;
  logic \is_desc ;
  logic \is_data ;
  logic \not_rst ;
  logic [4:0] \addr_hi5 ;
  logic [4:0] \c31_5 ;
  logic \near_4k ;
  logic [3:0] \addr_mid4 ;
  logic [7:0] \addr_mid4_z8 ;
  logic [7:0] \diff_4k ;
  logic [7:0] \max_16_or_4k ;
  logic [8:0] \rem_z9 ;
  logic [8:0] \max_z9 ;
  logic [8:0] \unused_sub_rem_max ;
  logic \rem_lt_max ;
  logic [7:0] \calc_beats ;
  logic \cmd_ready_raw ;
  logic \cmd_fire ;
  logic \desc_fire ;
  logic \mem_valid_raw ;
  logic \is_data_active ;
  logic \is_write_data ;
  logic \is_read_data ;
  logic \not_is_write ;
  logic \w_fire ;
  logic \r_fire ;
  logic \beat_fire ;
  logic \last_desc_beat ;
  logic \last_cmd_beat ;
  logic \r_last_cond ;
  logic [1:0] \state_from_idle ;
  logic [1:0] \state_from_desc ;
  logic \desc_done ;
  logic [1:0] \state_after_desc_done ;
  logic [1:0] \state_from_data ;
  logic [1:0] \next_state_1 ;
  logic [1:0] \next_state_2 ;
  logic [7:0] \cur_beats_dec ;
  logic [7:0] \cur_beats_after_data ;
  logic [7:0] \rem_beats_dec ;
  logic [7:0] \rem_beats_after_data ;
  logic [2:0] \c0_3 ;
  logic [10:0] \desc_beats_bytes ;
  logic [39:0] \desc_beats_bytes_z40 ;
  logic [39:0] \addr_inc ;
  logic [39:0] \addr_after_data ;
  // Vexim line 108
  assign \cmd_ready = \is_idle & \not_rst ;
  // Vexim line 136
  assign \w_ready = \is_write_data & \mem_w_ready ;
  // Vexim line 144
  assign \r_valid = \is_read_data & \mem_r_valid ;
  // Vexim line 146
  assign \r_data = \mem_r_data ;
  // Vexim line 163
  assign \r_last = \r_last_cond ;
  // Vexim line 113
  assign \mem_valid = \is_desc & \not_rst ;
  // Vexim line 114
  assign \mem_write = \is_write_reg ;
  // Vexim line 115
  assign \mem_addr = \addr_reg ;
  // Vexim line 116
  assign \mem_beats = \calc_beats ;
  // Vexim line 135
  assign \mem_w_valid = \is_write_data & \w_valid ;
  // Vexim line 137
  assign \mem_w_data = \w_data ;
  // Vexim line 138
  assign \mem_w_strb = \w_strb ;
  // Vexim line 145
  assign \mem_r_ready = \is_read_data & \r_ready ;
  // Vexim line 165
  assign \done = \beat_fire & \last_cmd_beat ;
  // Vexim line 39
  assign \c0_1 = 1'd0;
  // Vexim line 40
  assign \c0_2 = 2'd0;
  // Vexim line 41
  assign \c1_2 = 2'd1;
  // Vexim line 42
  assign \c2_2 = 2'd2;
  // Vexim line 43
  assign \c1_8 = 8'd1;
  // Vexim line 44
  assign \c16_8 = 8'd16;
  // Vexim line 216
  always_ff @(posedge \clk ) begin
    if (\rst ) \state <= 2'd0;
    else \state <= \next_state ;
  end
  // Vexim line 185
  assign \next_state = \is_data ? \state_from_data : \next_state_2 ;
  // Vexim line 217
  always_ff @(posedge \clk ) begin
    if (\rst ) \is_write_reg <= 1'd0;
    else \is_write_reg <= \next_is_write ;
  end
  // Vexim line 188
  assign \next_is_write = \cmd_fire ? \cmd_write : \is_write_reg ;
  // Vexim line 218
  always_ff @(posedge \clk ) begin
    if (\rst ) \addr_reg <= 40'd0;
    else \addr_reg <= \next_addr ;
  end
  // Vexim line 213
  assign \next_addr = \cmd_fire ? \cmd_addr : \addr_after_data ;
  // Vexim line 219
  always_ff @(posedge \clk ) begin
    if (\rst ) \rem_beats_reg <= 8'd0;
    else \rem_beats_reg <= \next_rem_beats ;
  end
  // Vexim line 201
  assign \next_rem_beats = \cmd_fire ? \cmd_beats : \rem_beats_after_data ;
  // Vexim line 220
  always_ff @(posedge \clk ) begin
    if (\rst ) \cur_beats_reg <= 8'd0;
    else \cur_beats_reg <= \next_cur_beats ;
  end
  // Vexim line 195
  assign \next_cur_beats = \desc_fire ? \calc_beats : \cur_beats_after_data ;
  // Vexim line 221
  always_ff @(posedge \clk ) begin
    if (\rst ) \desc_beats_reg <= 8'd0;
    else \desc_beats_reg <= \next_desc_beats ;
  end
  // Vexim line 189
  assign \next_desc_beats = \desc_fire ? \calc_beats : \desc_beats_reg ;
  // Vexim line 72
  assign \is_idle = \state == \c0_2 ;
  // Vexim line 73
  assign \is_desc = \state == \c1_2 ;
  // Vexim line 74
  assign \is_data = \state == \c2_2 ;
  // Vexim line 75
  assign \not_rst = \rst == \c0_1 ;
  // Vexim line 86
  assign \addr_hi5 = \addr_reg [11:7];
  // Vexim line 87
  assign \c31_5 = 5'd31;
  // Vexim line 88
  assign \near_4k = \addr_hi5 == \c31_5 ;
  // Vexim line 89
  assign \addr_mid4 = \addr_reg [6:3];
  // Vexim line 90
  assign \addr_mid4_z8 = {4'd0, \addr_mid4 };
  // Vexim line 91
  assign \diff_4k = \c16_8 - \addr_mid4_z8 ;
  // Vexim line 92
  assign \max_16_or_4k = \near_4k ? \diff_4k : \c16_8 ;
  // Vexim line 100
  assign \rem_z9 = {1'd0, \rem_beats_reg };
  // Vexim line 101
  assign \max_z9 = {1'd0, \max_16_or_4k };
  // Vexim line 102
  assign \unused_sub_rem_max = \rem_z9 - \max_z9 ;
  // Vexim line 103
  assign \rem_lt_max = \unused_sub_rem_max [8];
  // Vexim line 104
  assign \calc_beats = \rem_lt_max ? \rem_beats_reg : \max_16_or_4k ;
  // Vexim line 109
  assign \cmd_ready_raw = \cmd_ready ;
  // Vexim line 111
  assign \cmd_fire = \cmd_valid & \cmd_ready_raw ;
  // Vexim line 121
  assign \desc_fire = \mem_valid_raw & \mem_ready ;
  // Vexim line 120
  assign \mem_valid_raw = \is_desc & \not_rst ;
  // Vexim line 125
  assign \is_data_active = \is_data & \not_rst ;
  // Vexim line 131
  assign \is_write_data = \is_data_active & \is_write_reg ;
  // Vexim line 132
  assign \is_read_data = \is_data_active & \not_is_write ;
  // Vexim line 130
  assign \not_is_write = \is_write_reg == \c0_1 ;
  // Vexim line 141
  assign \w_fire = \mem_w_valid & \mem_w_ready ;
  // Vexim line 149
  assign \r_fire = \r_valid & \r_ready ;
  // Vexim line 152
  assign \beat_fire = \w_fire | \r_fire ;
  // Vexim line 156
  assign \last_desc_beat = \cur_beats_reg == \c1_8 ;
  // Vexim line 159
  assign \last_cmd_beat = \rem_beats_reg == \c1_8 ;
  // Vexim line 162
  assign \r_last_cond = \r_valid & \last_cmd_beat ;
  // Vexim line 169
  assign \state_from_idle = \cmd_fire ? \c1_2 : \c0_2 ;
  // Vexim line 172
  assign \state_from_desc = \desc_fire ? \c2_2 : \c1_2 ;
  // Vexim line 175
  assign \desc_done = \beat_fire & \last_desc_beat ;
  // Vexim line 177
  assign \state_after_desc_done = \last_cmd_beat ? \c0_2 : \c1_2 ;
  // Vexim line 179
  assign \state_from_data = \desc_done ? \state_after_desc_done : \c2_2 ;
  // Vexim line 182
  assign \next_state_1 = \is_idle ? \state_from_idle : \state ;
  // Vexim line 184
  assign \next_state_2 = \is_desc ? \state_from_desc : \next_state_1 ;
  // Vexim line 192
  assign \cur_beats_dec = \cur_beats_reg - \c1_8 ;
  // Vexim line 194
  assign \cur_beats_after_data = \beat_fire ? \cur_beats_dec : \cur_beats_reg ;
  // Vexim line 198
  assign \rem_beats_dec = \rem_beats_reg - \c1_8 ;
  // Vexim line 200
  assign \rem_beats_after_data = \beat_fire ? \rem_beats_dec : \rem_beats_reg ;
  // Vexim line 204
  assign \c0_3 = 3'd0;
  // Vexim line 206
  assign \desc_beats_bytes = {\desc_beats_reg , \c0_3 };
  // Vexim line 208
  assign \desc_beats_bytes_z40 = {29'd0, \desc_beats_bytes };
  // Vexim line 210
  assign \addr_inc = \addr_reg + \desc_beats_bytes_z40 ;
  // Vexim line 212
  assign \addr_after_data = \desc_done ? \addr_inc : \addr_reg ;
endmodule
