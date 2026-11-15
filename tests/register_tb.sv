module tb;
logic clk=0, rst=1;
logic [7:0] data=8'h42, q;
register_demo dut(.*);
initial begin
  #1; clk=1;
  #1; if (q !== 0) $fatal(1, "reset failed");
  clk=0; rst=0;
  #1; clk=1;
  #1; if (q !== 8'h42) $fatal(1, "data capture failed");
  data=8'hff;
  #1; if (q !== 8'h42) $fatal(1, "register changed without an edge");
  $display("PASS");
  $finish;
end
endmodule
