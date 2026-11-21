module timing_harness (
  input clk,
  input [8:0] stimuli,
  output reg [5:0] response
);
  reg [8:0] launch;
  wire [5:0] capture;
  always @(posedge clk) begin
    launch <= stimuli;
    response <= capture;
  end
  `DUT dut (
    .i_clk(clk), .i_bytecnt(launch[8:7]), .i_lsb(launch[6:5]),
    .i_signed(launch[4]), .i_word(launch[3]), .i_half(launch[2]),
    .i_mdu_op(launch[1]), .i_bufreg2_q(launch[0]),
    .o_misalign(capture[5]), .o_rd(capture[4]), .o_wb_sel(capture[3:0])
  );
endmodule
