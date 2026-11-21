module tb;
logic clk=0,rst;
logic [31:0] instr,mem_rdata,pc,mem_addr,mem_wdata;
logic mem_write,mem_read,illegal;
rv32_demo dut(.*);
task tick;
  #1; clk=1; #1; clk=0;
endtask
task execute(input logic [31:0] word_in,next_pc);
  instr=word_in;
  #1;
  if(illegal) $fatal(1,"illegal %h",instr);
  tick();
  if(pc!==next_pc) $fatal(1,"pc %h expected %h",pc,next_pc);
endtask
initial begin
  rst=1; instr=0; mem_rdata=11; tick(); rst=0;
  execute(32'h00500093,4); // addi x1,x0,5
  execute(32'h00108133,8); // add x2,x1,x1
  execute(32'h401101b3,12); // sub x3,x2,x1
  execute(32'h00308463,20); // beq x1,x3,+8
  instr=32'h00202223; #1; // sw x2,4(x0)
  if(mem_write!==1 || mem_addr!==4 || mem_wdata!==10) $fatal(1,"store");
  execute(instr,24);
  instr=32'h00402203; #1; // lw x4,4(x0)
  if(mem_read!==1 || mem_addr!==4) $fatal(1,"load");
  execute(instr,28);
  instr=32'h00402423; #1; // sw x4,8(x0)
  if(mem_write!==1 || mem_addr!==8 || mem_wdata!==11) $fatal(1,"load result");
  instr='1; #1;
  if(illegal!==1 || mem_write!==0) $fatal(1,"illegal handling");
  tick();
  if(pc!==28) $fatal(1,"illegal instruction advanced PC");
  $display("PASS"); $finish;
end
endmodule
