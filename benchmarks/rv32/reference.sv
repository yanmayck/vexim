// Educational RV32I subset: LUI, ADDI, ADD, SUB, BEQ, LW, SW.
module rv32_demo(input logic clk,rst, input logic [31:0] instr,mem_rdata,
 output logic [31:0] pc,mem_addr,mem_wdata, output logic mem_write,mem_read,illegal);
logic [31:0] regs [1:31];
logic [31:0] a,b,result,next_pc;
logic write_rd;
logic [4:0] rs1,rs2,rd;
assign rs1=instr[19:15];
assign rs2=instr[24:20];
assign rd=instr[11:7];
assign a=rs1==0 ? 0 : regs[rs1];
assign b=rs2==0 ? 0 : regs[rs2];
always_comb begin
  next_pc=pc+4; result=0; write_rd=0; illegal=0;
  mem_addr=0; mem_wdata=b; mem_write=0; mem_read=0;
  case(instr[6:0])
    7'h37: begin result={instr[31:12],12'b0}; write_rd=1; end
    7'h13: if(instr[14:12]==0) begin
      result=a+{{20{instr[31]}},instr[31:20]}; write_rd=1;
    end else illegal=1;
    7'h33: case ({instr[31:25],instr[14:12]})
      10'h000: begin result=a+b; write_rd=1; end
      10'h100: begin result=a-b; write_rd=1; end
      default: illegal=1;
    endcase
    7'h63: if(instr[14:12]==0) begin
      if (a==b) next_pc=pc+{{19{instr[31]}},instr[31],instr[7],instr[30:25],instr[11:8],1'b0};
      if (next_pc[1:0]!=0) illegal=1;
    end else illegal=1;
    7'h03: begin
      mem_addr=a+{{20{instr[31]}},instr[31:20]};
      if(instr[14:12]==2 && mem_addr[1:0]==0) begin mem_read=1; result=mem_rdata; write_rd=1; end
      else illegal=1;
    end
    7'h23: begin
      mem_addr=a+{{20{instr[31]}},instr[31:25],instr[11:7]};
      if(instr[14:12]==2 && mem_addr[1:0]==0) mem_write=1;
      else illegal=1;
    end
    default: illegal=1;
  endcase
  if (rst) begin mem_write=0; mem_read=0; end
end
always_ff @(posedge clk) begin
  if (rst) begin
    pc<=0;
    for(int i=1;i<32;i++) regs[i]<=0;
  end else if (!illegal) begin
    pc<=next_pc;
    if (write_rd && rd!=0) regs[rd]<=result;
  end
end
endmodule
