module serv_mem_if_profile (
  input wire i_clk,
  input wire [1:0] i_bytecnt, i_lsb,
  input wire i_signed, i_word, i_half, i_mdu_op, i_bufreg2_q,
  output wire o_misalign, o_rd,
  output wire [3:0] o_wb_sel
);
  serv_mem_core dut (
    .i_clk(i_clk), .reset_unused(1'b0), .i_bytecnt(i_bytecnt),
    .i_lsb(i_lsb), .i_signed(i_signed), .i_word(i_word),
    .i_half(i_half), .i_mdu_op(i_mdu_op), .i_bufreg2_q(i_bufreg2_q),
    .o_misalign(o_misalign), .o_rd(o_rd), .o_wb_sel(o_wb_sel)
  );
endmodule
