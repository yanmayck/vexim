module tb;
  reg clk=0, resetn=0;
  reg [31:0] noise;
  integer seed, cycles=0, writes=0;
  wire trap, mem_valid, mem_instr;
  wire [31:0] mem_addr, mem_wdata;
  wire [3:0] mem_wstrb;
  reg [31:0] rom[0:63];
  reg [31:0] scratch=0;
  wire mem_ready = resetn && mem_valid && (noise[1:0] == 2'b11);
  wire [31:0] mem_rdata = mem_addr == 32'h200 ? scratch :
                          mem_addr < 256 ? rom[mem_addr[7:2]] : 32'd0;
`ifdef OFFICIAL
  picorv32 #(.ENABLE_MUL(1), .ENABLE_DIV(1)) dut (
`else
  picorv32 dut (
`endif
    .clk(clk), .resetn(resetn), .trap(trap), .mem_valid(mem_valid),
    .mem_instr(mem_instr), .mem_ready(mem_ready), .mem_addr(mem_addr),
    .mem_wdata(mem_wdata), .mem_wstrb(mem_wstrb), .mem_rdata(mem_rdata),
    .pcpi_wr(1'b0), .pcpi_rd(32'd0), .pcpi_wait(1'b0), .pcpi_ready(1'b0), .irq(32'd0)
  );

  function automatic [31:0] ins_addi(input [4:0] rd, rs, input [11:0] value);
    return {value,rs,3'b0,rd,7'h13};
  endfunction
  function automatic [31:0] ins_m(input [4:0] rd, rs1, rs2, input [2:0] op);
    return {7'd1,rs2,rs1,op,rd,7'h33};
  endfunction
  function automatic [31:0] ins_sw(input [4:0] rs, input [11:0] addr);
    return {addr[11:5],rs,5'd0,3'd2,addr[4:0],7'h23};
  endfunction

  initial begin
    if (!$value$plusargs("seed=%d", seed)) seed=1;
    noise=seed;
    for(integer i=0;i<64;i++) rom[i]=32'h0000006f;
    rom[0]=ins_addi(1,0,-37);
    rom[1]=ins_addi(2,0,5);
    rom[2]=ins_m(3,1,2,0);          // mul -185
    rom[3]=ins_sw(3,'h100);
    rom[4]=ins_m(3,1,2,1);          // mulh -1
    rom[5]=ins_sw(3,'h104);
    rom[6]=ins_m(3,1,2,4);          // div -7
    rom[7]=ins_sw(3,'h108);
    rom[8]=ins_m(3,1,2,6);          // rem -2
    rom[9]=ins_sw(3,'h10c);
    rom[10]=ins_m(3,1,0,4);         // div by zero -1
    rom[11]=ins_sw(3,'h110);
    rom[12]=ins_m(3,1,0,6);         // rem by zero -37
    rom[13]=ins_sw(3,'h114);
    rom[14]=32'h80000237;           // lui x4,0x80000
    rom[15]=ins_addi(5,0,-1);
    rom[16]=ins_m(3,4,5,4);         // signed overflow INT_MIN / -1
    rom[17]=ins_sw(3,'h118);
    rom[18]=ins_m(3,4,5,6);
    rom[19]=ins_sw(3,'h11c);
    rom[20]=ins_m(3,4,2,5);         // unsigned div
    rom[21]=ins_sw(3,'h120);
    rom[22]=ins_sw(3,'h200);
    rom[23]=32'h20002303;           // lw x6,0x200(x0)
    rom[24]=32'h00330463;           // beq x6,x3,+8
    rom[25]=ins_sw(0,'h124);        // fault signature
    rom[26]=ins_addi(7,0,'h5a);
    rom[27]=ins_sw(7,'h124);
    repeat(5) @(negedge clk);
    resetn=1;
  end

  always #5 clk=~clk;
  always @(posedge clk) begin
    integer feedback;
    cycles<=cycles+1;
    feedback=noise ^ (noise << 13);
    feedback=feedback ^ (feedback >> 17);
    noise<=feedback ^ (feedback << 5);
    if (cycles>20000) $fatal(1,"timeout");
    if(resetn && trap) $fatal(1,"unexpected trap");
    if(mem_ready) begin
      if(mem_wstrb != 0) begin
        reg [31:0] expected;
        case (mem_addr)
          'h100: expected=-185;
          'h104: expected=-1;
          'h108: expected=-7;
          'h10c: expected=-2;
          'h110: expected=-1;
          'h114: expected=-37;
          'h118: expected=32'h80000000;
          'h11c: expected=0;
          'h120,'h200: expected=32'd429496729;
          'h124: expected=32'h5a;
          default: $fatal(1,"unexpected store address %h",mem_addr);
        endcase
        if(mem_wdata !== expected || mem_wstrb !== 4'hf)
          $fatal(1,"store at %h expected %h got %h",mem_addr, expected,mem_wdata);
        $display("BUS %0d W %08h %08h",cycles,mem_addr,mem_wdata);
        writes=writes+1;
        if(mem_addr=='h200) scratch<=mem_wdata;
        if(mem_addr=='h124) begin
          if(writes != 11) $fatal(1,"wrong number of writes");
          $display("PASS seed=%0d cycles=%0d",seed,cycles); $finish;
        end
      end else $display("BUS %0d R %b %08h",cycles,mem_instr,mem_addr);
    end
  end
endmodule
