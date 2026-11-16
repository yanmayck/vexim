module tb;
logic clk=0, we=0;
logic [3:0] wr_addr=0, rd_addr=0;
logic [7:0] din=0, dout;
ram dut(.*);

task write_word(input logic [3:0] address, input logic [7:0] value);
  we=1; wr_addr=address; din=value;
  #1; clk=1; #1; clk=0; we=0;
endtask

task expect_word(input logic [3:0] address, input logic [7:0] value);
  rd_addr=address;
  #1;
  if (dout !== value) $fatal(1, "address %d expected %h got %h", address, value, dout);
endtask

initial begin
  write_word(0, 8'h37);
  write_word(11, 8'h62);
  expect_word(0, 8'h37);
  expect_word(11, 8'h62);
  wr_addr=11; din=8'hff;
  #1; clk=1; #1; clk=0;
  expect_word(11, 8'h62);
  we=1; din=8'h34;
  expect_word(11, 8'h62);
  clk=1; #1; clk=0; we=0;
  expect_word(11, 8'h34);
  write_word(15, 8'hb1);
`ifdef SHALLOW
  expect_word(15, 0);
  expect_word(0, 8'h37);
`else
  expect_word(15, 8'hb1);
`endif
  expect_word(11, 8'h34);
  $display("RAM PASS");
  $finish;
end
endmodule
