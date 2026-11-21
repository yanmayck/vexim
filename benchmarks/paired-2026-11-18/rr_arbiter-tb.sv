module tb;
logic clk=0, rst=1, ready=0, valid;
logic [3:0] req=0, grant;
rr_arbiter dut(.*);

int priority_index=0, locked=-1, checked_transfers=0;
logic [31:0] rng=32'hc97f80ad;
logic [3:0] pending=0;

task automatic step(input logic reset_value, accept_value,
                    input logic [3:0] added_requests);
  int selected, index_value;
  logic [3:0] expected;
  rst=reset_value;
  ready=accept_value;
  req=pending | added_requests;
  selected=-1;
  if(!rst) begin
    selected=locked;
    for(int offset=0;offset<4;offset++) begin
      index_value=(priority_index+offset)%4;
      if(selected<0 && req[index_value]) selected=index_value;
    end
  end
  expected=0;
  if(selected>=0) expected[selected]=1;
  #1;
  if(valid !== (selected>=0) || grant !== expected)
    $fatal(1,"req=%b ready=%b rst=%b priority=%d lock=%d grant=%b expected=%b",
           req,ready,rst,priority_index,locked,grant,expected);
  if(rst) begin priority_index=0; locked=-1; pending=0; end
  else begin
    pending=req;
    if(selected>=0 && ready) begin
      pending[selected]=0;
      priority_index=(selected+1)%4;
      locked=-1;
      checked_transfers++;
    end else if(selected>=0) locked=selected;
  end
  clk=1; #1; clk=0; #1;
endtask

initial begin
  step(1,0,0);
  step(0,1,0);
  step(0,0,4'b1000);
  step(0,0,4'b0001);
  step(0,1,4'b0110);
  repeat(20) step(0,1,4'b1111);
  step(0,0,4'b1111);
  step(1,0,4'b1111);
  step(0,1,4'b1111);
  for(int i=0;i<4096;i++) begin
    rng=rng^(rng<<13); rng=rng^(rng>>17); rng=rng^(rng<<5);
    step(i%257==0,rng[4],rng[3:0]);
  end
  if(checked_transfers<1000) $fatal(1,"too few transfers checked");
  $display("Checked %0d transfers",checked_transfers);
  $display("PASS");
  $finish;
end
endmodule
