module \rr_arbiter (
  input logic \clk ,
  input logic \rst ,
  input logic [3:0] \req ,
  input logic \ready ,
  output logic \valid ,
  output logic [3:0] \grant 
);
  logic \c0_u1 ;
  logic [3:0] \c0_u4 ;
  logic [3:0] \c1_u4 ;
  logic [3:0] \c2_u4 ;
  logic [3:0] \c4_u4 ;
  logic [3:0] \c8_u4 ;
  logic [1:0] \c0_u2 ;
  logic [1:0] \c1_u2 ;
  logic [1:0] \c2_u2 ;
  logic [1:0] \c3_u2 ;
  logic \r0 ;
  logic \r1 ;
  logic \r2 ;
  logic \r3 ;
  logic [3:0] \g_p0_3 ;
  logic [3:0] \g_p0_2 ;
  logic [3:0] \g_p0_1 ;
  logic [3:0] \g_p0 ;
  logic [3:0] \g_p1_0 ;
  logic [3:0] \g_p1_3 ;
  logic [3:0] \g_p1_2 ;
  logic [3:0] \g_p1 ;
  logic [3:0] \g_p2_1 ;
  logic [3:0] \g_p2_0 ;
  logic [3:0] \g_p2_3 ;
  logic [3:0] \g_p2 ;
  logic [3:0] \g_p3_2 ;
  logic [3:0] \g_p3_1 ;
  logic [3:0] \g_p3_0 ;
  logic [3:0] \g_p3 ;
  logic [1:0] \prio ;
  logic \locked ;
  logic [3:0] \locked_grant ;
  logic \p_bit0 ;
  logic \p_bit1 ;
  logic [3:0] \g_p01 ;
  logic [3:0] \g_p23 ;
  logic [3:0] \new_grant ;
  logic [3:0] \raw_grant ;
  logic \raw_valid ;
  logic \transfer ;
  logic \g0 ;
  logic \g1 ;
  logic \g2 ;
  logic [1:0] \np_2 ;
  logic [1:0] \np_1 ;
  logic [1:0] \granted_next_prio ;
  logic [1:0] \next_prio ;
  logic \not_ready ;
  logic \c1_u1 ;
  logic \next_locked ;
  logic [3:0] \next_locked_grant ;
  // Vexim line 109
  assign \valid = \rst ? \c0_u1 : \raw_valid ;
  // Vexim line 108
  assign \grant = \rst ? \c0_u4 : \raw_grant ;
  // Vexim line 21
  assign \c0_u1 = 1'd0;
  // Vexim line 22
  assign \c0_u4 = 4'd0;
  // Vexim line 23
  assign \c1_u4 = 4'd1;
  // Vexim line 24
  assign \c2_u4 = 4'd2;
  // Vexim line 25
  assign \c4_u4 = 4'd4;
  // Vexim line 26
  assign \c8_u4 = 4'd8;
  // Vexim line 28
  assign \c0_u2 = 2'd0;
  // Vexim line 29
  assign \c1_u2 = 2'd1;
  // Vexim line 30
  assign \c2_u2 = 2'd2;
  // Vexim line 31
  assign \c3_u2 = 2'd3;
  // Vexim line 37
  assign \r0 = \req [0];
  // Vexim line 38
  assign \r1 = \req [1];
  // Vexim line 39
  assign \r2 = \req [2];
  // Vexim line 40
  assign \r3 = \req [3];
  // Vexim line 47
  assign \g_p0_3 = \r3 ? \c8_u4 : \c0_u4 ;
  // Vexim line 48
  assign \g_p0_2 = \r2 ? \c4_u4 : \g_p0_3 ;
  // Vexim line 49
  assign \g_p0_1 = \r1 ? \c2_u4 : \g_p0_2 ;
  // Vexim line 50
  assign \g_p0 = \r0 ? \c1_u4 : \g_p0_1 ;
  // Vexim line 57
  assign \g_p1_0 = \r0 ? \c1_u4 : \c0_u4 ;
  // Vexim line 58
  assign \g_p1_3 = \r3 ? \c8_u4 : \g_p1_0 ;
  // Vexim line 59
  assign \g_p1_2 = \r2 ? \c4_u4 : \g_p1_3 ;
  // Vexim line 60
  assign \g_p1 = \r1 ? \c2_u4 : \g_p1_2 ;
  // Vexim line 67
  assign \g_p2_1 = \r1 ? \c2_u4 : \c0_u4 ;
  // Vexim line 68
  assign \g_p2_0 = \r0 ? \c1_u4 : \g_p2_1 ;
  // Vexim line 69
  assign \g_p2_3 = \r3 ? \c8_u4 : \g_p2_0 ;
  // Vexim line 70
  assign \g_p2 = \r2 ? \c4_u4 : \g_p2_3 ;
  // Vexim line 77
  assign \g_p3_2 = \r2 ? \c4_u4 : \c0_u4 ;
  // Vexim line 78
  assign \g_p3_1 = \r1 ? \c2_u4 : \g_p3_2 ;
  // Vexim line 79
  assign \g_p3_0 = \r0 ? \c1_u4 : \g_p3_1 ;
  // Vexim line 80
  assign \g_p3 = \r3 ? \c8_u4 : \g_p3_0 ;
  // Vexim line 136
  always_ff @(posedge \clk ) begin
    if (\rst ) \prio <= 2'd0;
    else \prio <= \next_prio ;
  end
  // Vexim line 146
  always_ff @(posedge \clk ) begin
    if (\rst ) \locked <= 1'd0;
    else \locked <= \next_locked ;
  end
  // Vexim line 151
  always_ff @(posedge \clk ) begin
    if (\rst ) \locked_grant <= 4'd0;
    else \locked_grant <= \next_locked_grant ;
  end
  // Vexim line 90
  assign \p_bit0 = \prio [0];
  // Vexim line 91
  assign \p_bit1 = \prio [1];
  // Vexim line 96
  assign \g_p01 = \p_bit0 ? \g_p1 : \g_p0 ;
  // Vexim line 97
  assign \g_p23 = \p_bit0 ? \g_p3 : \g_p2 ;
  // Vexim line 98
  assign \new_grant = \p_bit1 ? \g_p23 : \g_p01 ;
  // Vexim line 102
  assign \raw_grant = \locked ? \locked_grant : \new_grant ;
  // Vexim line 105
  assign \raw_valid = \raw_grant != \c0_u4 ;
  // Vexim line 113
  assign \transfer = \valid & \ready ;
  // Vexim line 123
  assign \g0 = \raw_grant [0];
  // Vexim line 124
  assign \g1 = \raw_grant [1];
  // Vexim line 125
  assign \g2 = \raw_grant [2];
  // Vexim line 130
  assign \np_2 = \g2 ? \c3_u2 : \c0_u2 ;
  // Vexim line 131
  assign \np_1 = \g1 ? \c2_u2 : \np_2 ;
  // Vexim line 132
  assign \granted_next_prio = \g0 ? \c1_u2 : \np_1 ;
  // Vexim line 135
  assign \next_prio = \transfer ? \granted_next_prio : \prio ;
  // Vexim line 142
  assign \not_ready = \ready ^ \c1_u1 ;
  // Vexim line 141
  assign \c1_u1 = 1'd1;
  // Vexim line 145
  assign \next_locked = \raw_valid & \not_ready ;
  // Vexim line 150
  assign \next_locked_grant = \raw_grant ;
endmodule
