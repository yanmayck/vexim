module differential;
  reg clk=0, rst=1;
  reg [31:0] instr=0, mem_rdata=0;
  wire [98:0] reference_outputs, vexim_outputs;
  reg [31:0] prng=32'h73ae1105, data;
  reg [4:0] rs1, rs2, rd;
  rv32_reference reference_cpu(.clk(clk), .rst(rst), .instr(instr), .mem_rdata(mem_rdata),
    .pc(reference_outputs[98:67]), .mem_addr(reference_outputs[66:35]),
    .mem_wdata(reference_outputs[34:3]), .mem_write(reference_outputs[2]),
    .mem_read(reference_outputs[1]), .illegal(reference_outputs[0]));
  rv32_demo vexim_cpu(.clk(clk), .rst(rst), .instr(instr), .mem_rdata(mem_rdata),
    .pc(vexim_outputs[98:67]), .mem_addr(vexim_outputs[66:35]),
    .mem_wdata(vexim_outputs[34:3]), .mem_write(vexim_outputs[2]),
    .mem_read(vexim_outputs[1]), .illegal(vexim_outputs[0]));

  function automatic [31:0] next_random(input [31:0] x);
    reg [31:0] y;
    y = x ^ (x << 13);
    y = y ^ (y >> 17);
    return y ^ (y << 5);
  endfunction

  task automatic tick;
    #1; clk=1; #1; clk=0;
  endtask

  initial begin
    tick();
    for (integer cycle=0; cycle<20000; cycle++) begin
      prng=next_random(prng); data=prng;
      prng=next_random(prng); mem_rdata=prng;
      rs1=prng[4:0]; rs2=prng[9:5]; rd=prng[14:10];
      rst=(cycle%709==708);
      case (cycle%10)
        0: instr={data[19:0],rd,7'h37};
        1: instr={data[11:0],rs1,3'd0,rd,7'h13};
        2: instr={7'd0,rs2,rs1,3'd0,rd,7'h33};
        3: instr={7'd32,rs2,rs1,3'd0,rd,7'h33};
        4: instr={data[11:2],2'b00,rs1,3'd2,rd,7'h03};
        5: instr={data[11:5],rs2,rs1,3'd2,data[4:2],2'b00,7'h23};
        6: instr={data[11],data[10:5],rs1,rs1,3'd0,data[4:1],data[0],7'h63};
        7: instr={data[11],data[10:5],rs2,rs1,3'd0,data[4:1],data[0],7'h63};
        8: instr={data[11:2],2'b01,5'd0,3'd2,rd,7'h03};
        9: instr=data;
      endcase
      #1;
      if (reference_outputs !== vexim_outputs)
        $fatal(1,"cycle %0d instr=%h gold=%h vexim=%h", cycle, instr, reference_outputs, vexim_outputs);
      tick();
      #1;
      if (reference_outputs !== vexim_outputs)
        $fatal(1,"after cycle %0d instr=%h gold=%h vexim=%h", cycle, instr, reference_outputs, vexim_outputs);
    end
    $display("PASS"); $finish;
  end
endmodule
