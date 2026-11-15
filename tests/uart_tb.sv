module tb;
logic clk=0, rst=1, start=0;
logic [7:0] data=0;
logic tx, busy;
logic [9:0] expected;
uart_tx dut(.*);

task tick;
  #1; clk=1; #1; clk=0;
endtask

task check_idle;
  if (tx !== 1 || busy !== 0) $fatal(1, "UART must be idle");
endtask

task transmit(input logic [7:0] value);
  data=value;
  start=1;
  tick();
  expected={1'b1,value,1'b0};
  for (int bit_index=0;bit_index<10;bit_index++)
    for (int cycle=0;cycle<4;cycle++) begin
      if (busy !== 1 || tx !== expected[bit_index])
        $fatal(1, "byte %h, bit %d, cycle %d",value,bit_index,cycle);
      // Try to restart during transmission, including on the last cycle.
      start=(cycle==3);
      data=~value;
      tick();
    end
  start=0;
  check_idle();
endtask

initial begin
  tick();
  check_idle();
  rst=0;
  for (int value=0;value<256;value++) transmit(8'(value));
  data=8'hc3;
  start=1;
  tick();
  start=0;
  repeat(7) tick();
  if (busy !== 1) $fatal(1, "expected an active frame before reset");
  rst=1;
  tick();
  check_idle();
  rst=0;
  tick();
  check_idle();
  transmit(8'h5a);
  $display("UART PASS");
  $finish;
end
endmodule
