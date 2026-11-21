module \home_computer (
  input logic \clk ,
  input logic \rst ,
  input logic [15:0] \instruction ,
  input logic [7:0] \sensors ,
  input logic [7:0] \net_data ,
  input logic \net_valid ,
  output logic [7:0] \pc ,
  output logic [7:0] \accumulator ,
  output logic [7:0] \gpio ,
  output logic \halted ,
  output logic \fault ,
  output logic \net_ack ,
  output logic \reboot 
);
  logic [3:0] \opcode ;
  logic [3:0] \unused_mid ;
  logic [7:0] \imm ;
  logic [3:0] \addr ;
  logic [7:0] \wd ;
  logic [7:0] \c8_0 ;
  logic [7:0] \c8_1 ;
  logic [7:0] \c8_2 ;
  logic [7:0] \c8_255 ;
  logic [3:0] \c4_1 ;
  logic [3:0] \c4_2 ;
  logic [3:0] \c4_3 ;
  logic [3:0] \c4_4 ;
  logic [3:0] \c4_5 ;
  logic [3:0] \c4_6 ;
  logic [3:0] \c4_7 ;
  logic [3:0] \c4_8 ;
  logic [3:0] \c4_9 ;
  logic [3:0] \c4_10 ;
  logic [3:0] \c4_11 ;
  logic [3:0] \c4_12 ;
  logic [3:0] \c4_13 ;
  logic [3:0] \c4_14 ;
  logic [3:0] \c4_15 ;
  logic \c1_0 ;
  logic \wd_exp ;
  logic \not_rst ;
  logic \not_wd_exp ;
  logic \not_halted ;
  logic \not_fault ;
  logic \run_a ;
  logic \run_b ;
  logic \running ;
  logic \is_ldi ;
  logic \is_addi ;
  logic \is_xori ;
  logic \is_load ;
  logic \is_store ;
  logic \is_in ;
  logic \is_out ;
  logic \is_jmp ;
  logic \is_jz ;
  logic \is_kick ;
  logic \is_halt ;
  logic \is_op12 ;
  logic \is_op13 ;
  logic \is_op14 ;
  logic \is_op15 ;
  logic \is_12_13 ;
  logic \is_14_15 ;
  logic \is_fault_op ;
  logic \is_halt_or_fault ;
  logic \imm_is_0 ;
  logic \imm_is_1 ;
  logic \imm_is_2 ;
  logic [7:0] \net_data_gated ;
  logic [7:0] \net_valid_zext ;
  logic [7:0] \in_p2 ;
  logic [7:0] \in_p1 ;
  logic [7:0] \in_val ;
  logic \in_port1 ;
  logic \in_port1_valid ;
  logic [7:0] \ram_rdata ;
  logic \ram_we ;
  logic [7:0] \acc_add ;
  logic [7:0] \acc_xor ;
  logic [7:0] \acc_m1 ;
  logic [7:0] \acc_m2 ;
  logic [7:0] \acc_m3 ;
  logic [7:0] \acc_m4 ;
  logic [7:0] \acc_exec ;
  logic [7:0] \acc_hold ;
  logic [7:0] \next_acc ;
  logic [7:0] \pc_inc ;
  logic \acc_is_0 ;
  logic \jz_take ;
  logic \take_jump ;
  logic [7:0] \pc_jump_or_inc ;
  logic [7:0] \pc_exec ;
  logic [7:0] \pc_hold ;
  logic [7:0] \next_pc ;
  logic [7:0] \gpio_exec ;
  logic [7:0] \gpio_hold ;
  logic [7:0] \next_gpio ;
  logic \set_halt ;
  logic \halt_hold ;
  logic \next_halted ;
  logic \set_fault ;
  logic \fault_hold ;
  logic \next_fault ;
  logic [7:0] \wd_inc ;
  logic \run_kick ;
  logic [7:0] \wd_or_kick ;
  logic [7:0] \next_wd ;
  logic [7:0] \ram [0:15];
  // Vexim line 165
  always_ff @(posedge \clk ) begin
    if (\ram_we ) \ram [\addr ] <= \accumulator ;
  end
  // Vexim line 206
  always_ff @(posedge \clk ) begin
    if (\rst ) \pc <= 8'd0;
    else \pc <= \next_pc ;
  end
  // Vexim line 187
  always_ff @(posedge \clk ) begin
    if (\rst ) \accumulator <= 8'd0;
    else \accumulator <= \next_acc ;
  end
  // Vexim line 215
  always_ff @(posedge \clk ) begin
    if (\rst ) \gpio <= 8'd0;
    else \gpio <= \next_gpio ;
  end
  // Vexim line 224
  always_ff @(posedge \clk ) begin
    if (\rst ) \halted <= 1'd0;
    else \halted <= \next_halted ;
  end
  // Vexim line 232
  always_ff @(posedge \clk ) begin
    if (\rst ) \fault <= 1'd0;
    else \fault <= \next_fault ;
  end
  // Vexim line 158
  assign \net_ack = \running & \in_port1_valid ;
  // Vexim line 245
  always_ff @(posedge \clk ) begin
    if (\rst ) \reboot <= 1'd0;
    else \reboot <= \wd_exp ;
  end
  // Vexim line 23
  assign \opcode = \instruction [15:12];
  // Vexim line 24
  assign \unused_mid = \instruction [11:8];
  // Vexim line 25
  assign \imm = \instruction [7:0];
  // Vexim line 26
  assign \addr = \instruction [3:0];
  // Vexim line 243
  always_ff @(posedge \clk ) begin
    if (\rst ) \wd <= 8'd0;
    else \wd <= \next_wd ;
  end
  // Vexim line 33
  assign \c8_0 = 8'd0;
  // Vexim line 34
  assign \c8_1 = 8'd1;
  // Vexim line 35
  assign \c8_2 = 8'd2;
  // Vexim line 36
  assign \c8_255 = 8'd255;
  // Vexim line 53
  assign \c4_1 = 4'd1;
  // Vexim line 54
  assign \c4_2 = 4'd2;
  // Vexim line 55
  assign \c4_3 = 4'd3;
  // Vexim line 56
  assign \c4_4 = 4'd4;
  // Vexim line 57
  assign \c4_5 = 4'd5;
  // Vexim line 58
  assign \c4_6 = 4'd6;
  // Vexim line 59
  assign \c4_7 = 4'd7;
  // Vexim line 60
  assign \c4_8 = 4'd8;
  // Vexim line 61
  assign \c4_9 = 4'd9;
  // Vexim line 62
  assign \c4_10 = 4'd10;
  // Vexim line 63
  assign \c4_11 = 4'd11;
  // Vexim line 64
  assign \c4_12 = 4'd12;
  // Vexim line 65
  assign \c4_13 = 4'd13;
  // Vexim line 66
  assign \c4_14 = 4'd14;
  // Vexim line 67
  assign \c4_15 = 4'd15;
  // Vexim line 70
  assign \c1_0 = 1'd0;
  // Vexim line 73
  assign \wd_exp = \wd == \c8_255 ;
  // Vexim line 79
  assign \not_rst = \rst == \c1_0 ;
  // Vexim line 80
  assign \not_wd_exp = \wd_exp == \c1_0 ;
  // Vexim line 81
  assign \not_halted = \halted == \c1_0 ;
  // Vexim line 82
  assign \not_fault = \fault == \c1_0 ;
  // Vexim line 87
  assign \run_a = \not_rst & \not_wd_exp ;
  // Vexim line 88
  assign \run_b = \not_halted & \not_fault ;
  // Vexim line 89
  assign \running = \run_a & \run_b ;
  // Vexim line 107
  assign \is_ldi = \opcode == \c4_1 ;
  // Vexim line 108
  assign \is_addi = \opcode == \c4_2 ;
  // Vexim line 109
  assign \is_xori = \opcode == \c4_3 ;
  // Vexim line 110
  assign \is_load = \opcode == \c4_4 ;
  // Vexim line 111
  assign \is_store = \opcode == \c4_5 ;
  // Vexim line 112
  assign \is_in = \opcode == \c4_6 ;
  // Vexim line 113
  assign \is_out = \opcode == \c4_7 ;
  // Vexim line 114
  assign \is_jmp = \opcode == \c4_8 ;
  // Vexim line 115
  assign \is_jz = \opcode == \c4_9 ;
  // Vexim line 116
  assign \is_kick = \opcode == \c4_10 ;
  // Vexim line 117
  assign \is_halt = \opcode == \c4_11 ;
  // Vexim line 118
  assign \is_op12 = \opcode == \c4_12 ;
  // Vexim line 119
  assign \is_op13 = \opcode == \c4_13 ;
  // Vexim line 120
  assign \is_op14 = \opcode == \c4_14 ;
  // Vexim line 121
  assign \is_op15 = \opcode == \c4_15 ;
  // Vexim line 126
  assign \is_12_13 = \is_op12 | \is_op13 ;
  // Vexim line 127
  assign \is_14_15 = \is_op14 | \is_op15 ;
  // Vexim line 128
  assign \is_fault_op = \is_12_13 | \is_14_15 ;
  // Vexim line 131
  assign \is_halt_or_fault = \is_halt | \is_fault_op ;
  // Vexim line 137
  assign \imm_is_0 = \imm == \c8_0 ;
  // Vexim line 138
  assign \imm_is_1 = \imm == \c8_1 ;
  // Vexim line 139
  assign \imm_is_2 = \imm == \c8_2 ;
  // Vexim line 143
  assign \net_data_gated = \net_valid ? \net_data : \c8_0 ;
  // Vexim line 144
  assign \net_valid_zext = {7'd0, \net_valid };
  // Vexim line 149
  assign \in_p2 = \imm_is_2 ? \net_valid_zext : \c8_0 ;
  // Vexim line 150
  assign \in_p1 = \imm_is_1 ? \net_data_gated : \in_p2 ;
  // Vexim line 151
  assign \in_val = \imm_is_0 ? \sensors : \in_p1 ;
  // Vexim line 156
  assign \in_port1 = \is_in & \imm_is_1 ;
  // Vexim line 157
  assign \in_port1_valid = \in_port1 & \net_valid ;
  // Vexim line 163
  assign \ram_rdata = \ram [\addr ];
  // Vexim line 164
  assign \ram_we = \running & \is_store ;
  // Vexim line 170
  assign \acc_add = \accumulator + \imm ;
  // Vexim line 171
  assign \acc_xor = \accumulator ^ \imm ;
  // Vexim line 180
  assign \acc_m1 = \is_in ? \in_val : \accumulator ;
  // Vexim line 181
  assign \acc_m2 = \is_load ? \ram_rdata : \acc_m1 ;
  // Vexim line 182
  assign \acc_m3 = \is_xori ? \acc_xor : \acc_m2 ;
  // Vexim line 183
  assign \acc_m4 = \is_addi ? \acc_add : \acc_m3 ;
  // Vexim line 184
  assign \acc_exec = \is_ldi ? \imm : \acc_m4 ;
  // Vexim line 185
  assign \acc_hold = \running ? \acc_exec : \accumulator ;
  // Vexim line 186
  assign \next_acc = \wd_exp ? \c8_0 : \acc_hold ;
  // Vexim line 198
  assign \pc_inc = \pc + \c8_1 ;
  // Vexim line 199
  assign \acc_is_0 = \accumulator == \c8_0 ;
  // Vexim line 200
  assign \jz_take = \is_jz & \acc_is_0 ;
  // Vexim line 201
  assign \take_jump = \is_jmp | \jz_take ;
  // Vexim line 202
  assign \pc_jump_or_inc = \take_jump ? \imm : \pc_inc ;
  // Vexim line 203
  assign \pc_exec = \is_halt_or_fault ? \pc : \pc_jump_or_inc ;
  // Vexim line 204
  assign \pc_hold = \running ? \pc_exec : \pc ;
  // Vexim line 205
  assign \next_pc = \wd_exp ? \c8_0 : \pc_hold ;
  // Vexim line 212
  assign \gpio_exec = \is_out ? \accumulator : \gpio ;
  // Vexim line 213
  assign \gpio_hold = \running ? \gpio_exec : \gpio ;
  // Vexim line 214
  assign \next_gpio = \wd_exp ? \c8_0 : \gpio_hold ;
  // Vexim line 221
  assign \set_halt = \running & \is_halt_or_fault ;
  // Vexim line 222
  assign \halt_hold = \halted | \set_halt ;
  // Vexim line 223
  assign \next_halted = \wd_exp ? \c1_0 : \halt_hold ;
  // Vexim line 229
  assign \set_fault = \running & \is_fault_op ;
  // Vexim line 230
  assign \fault_hold = \fault | \set_fault ;
  // Vexim line 231
  assign \next_fault = \wd_exp ? \c1_0 : \fault_hold ;
  // Vexim line 239
  assign \wd_inc = \wd + \c8_1 ;
  // Vexim line 240
  assign \run_kick = \running & \is_kick ;
  // Vexim line 241
  assign \wd_or_kick = \run_kick ? \c8_0 : \wd_inc ;
  // Vexim line 242
  assign \next_wd = \wd_exp ? \c8_0 : \wd_or_kick ;
endmodule
