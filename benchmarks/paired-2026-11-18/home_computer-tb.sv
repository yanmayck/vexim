module tb;
logic clk=0,rst=1,net_valid=0;
logic [15:0] instruction;
logic [7:0] sensors=0,net_data=0,pc,accumulator,gpio;
logic halted,fault,net_ack,reboot;
home_computer dut(.*);
logic [15:0] rom[0:255];
logic [7:0] ram[0:15];
logic [7:0] ref_pc=0, ref_acc=0, ref_gpio=0, watchdog=0;
logic ref_halted=0,ref_fault=0,ref_reboot=0;
int steps=0, acks=0, reboots=0;
logic [31:0] rng=32'h073bc9ad;
assign instruction=rom[pc];

task automatic step;
  logic expected_ack;
  logic [15:0] word_value;
  int opcode;
  word_value=rom[ref_pc]; opcode=int'(word_value[15:12]);
  expected_ack=!rst && watchdog!=255 && !ref_halted &&
                opcode==6 && word_value[7:0]==1 && net_valid;
  #1;
  if(net_ack!==expected_ack) $fatal(1,"ack at step %d",steps);
  if(expected_ack) acks++;
  ref_reboot=0;
  if(rst || watchdog==255) begin
    ref_reboot=!rst;
    ref_pc=0; ref_acc=0; ref_gpio=0; ref_halted=0; ref_fault=0; watchdog=0;
  end else begin
    watchdog=watchdog+1'b1;
    if(!ref_halted) begin
      case(opcode)
        1: ref_acc=word_value[7:0];
        2: ref_acc=ref_acc+word_value[7:0];
        3: ref_acc=ref_acc^word_value[7:0];
        4: ref_acc=ram[word_value[3:0]];
        5: ram[word_value[3:0]]=ref_acc;
        6: case(word_value[7:0])
          0: ref_acc=sensors;
          1: ref_acc=net_valid ? net_data : 8'b0;
          2: ref_acc={7'b0,net_valid};
          default: ref_acc=0;
        endcase
        7: ref_gpio=ref_acc;
        10: watchdog=0;
        11: ref_halted=1;
        12,13,14,15: begin ref_halted=1; ref_fault=1; end
        default: ;
      endcase
      if(!ref_halted) begin
        if(opcode==8 || (opcode==9 && ref_acc==0)) ref_pc=word_value[7:0];
        else ref_pc=ref_pc+1'b1;
      end
    end
  end
  clk=1; #1; clk=0; #1; steps++;
  if(pc!==ref_pc || accumulator!==ref_acc || gpio!==ref_gpio ||
     halted!==ref_halted || fault!==ref_fault || reboot!==ref_reboot)
    $fatal(1,"step %d opcode %h pc %h/%h acc %h/%h gpio %h/%h halt %b/%b fault %b/%b reboot %b/%b",
      steps,word_value,pc,ref_pc,accumulator,ref_acc,gpio,ref_gpio,
      halted,ref_halted,fault,ref_fault,reboot,ref_reboot);
  if(reboot) reboots++;
endtask

task automatic clear_cpu;
  rst=1; step(); rst=0;
endtask

initial begin
  for(int i=0;i<256;i++) rom[i]=0;
  clear_cpu();
  // Mailbox command controls an output. Status polling avoids consuming an empty mailbox.
  rom[0]=16'ha000; rom[1]=16'h6002; rom[2]=16'h9000;
  rom[3]=16'h6001; rom[4]=16'h7000; rom[5]=16'h8000;
  repeat(20) step();
  if(acks!=0 || gpio!=0) $fatal(1,"mailbox empty");
  net_data=8'h01; net_valid=1;
  while(acks<1) step();
  net_valid=0;
  repeat(8) step();
  if(gpio!=1) $fatal(1,"home output did not turn on");
  net_data=0; net_valid=1;
  while(acks<2) step();
  net_valid=0; repeat(8) step();
  if(gpio!=0) $fatal(1,"home output did not turn off");
  // RAM and arithmetic exercise all addresses, wrapping, branches and input ports.
  clear_cpu();
  for(int i=0;i<16;i++) begin
    rom[i*2]=16'h1000 | 16'(i*17);
    rom[i*2+1]=16'h5000 | 16'(i);
    rom[32+i*3]=16'h4000 | 16'(i);
    rom[33+i*3]=16'h3000 | 16'h00a5;
    rom[34+i*3]=16'h7000;
  end
  rom[80]=16'h20ff; rom[81]=16'h6000; rom[82]=16'h6007;
  rom[83]=16'h9058; rom[88]=16'hb000;
  sensors=8'hc7;
  repeat(100) step();
  if(!halted) $fatal(1,"HALT missing");
  // Reboot a halted CPU and preserve RAM.
  while(reboots<1) step();
  rom[0]=16'h400f; rom[1]=16'h7000; rom[2]=16'hc000;
  repeat(8) step();
  if(!fault || gpio!=8'hff) $fatal(1,"RAM retention or illegal opcode");
  clear_cpu();
  // PC wrap and watchdog expiration at a KICK instruction.
  for(int i=0;i<256;i++) rom[i]=16'h8000;
  rom[0]=16'h80fe; rom[254]=16'h0000; rom[255]=16'h0000;
  repeat(255) step();
  rom[ref_pc]=16'ha000;
  step();
  if(!reboot) $fatal(1,"watchdog priority");
  clear_cpu();
  rom[0]=16'ha000; rom[1]=16'h8000;
  repeat(700) step();
  if(reboots!=2) $fatal(1,"unexpected reboot in KICK loop");
  // Inputs and current instruction vary, with a software interpreter as the oracle.
  for(int i=0;i<1024;i++) begin
    rng=rng^(rng<<13); rng=rng^(rng>>17); rng=rng^(rng<<5);
    rom[ref_pc]={rng[3:0],4'b0,rng[15:8]};
    sensors=rng[23:16]; net_data=rng[31:24]; net_valid=rng[4];
    rst=i%31==0;
    step();
  end
  $display("Checked %0d CPU cycles, %0d mailbox commands, %0d watchdog reboots",steps,acks,reboots);
  $display("PASS");
  $finish;
end
initial begin
  #10000; $fatal(1,"test watchdog");
end
endmodule
