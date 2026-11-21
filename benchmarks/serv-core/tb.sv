module tb;
  reg clk=0;
  reg i_rst=1;
  wire i_timer_irq=0;
  wire [31:0] o_ibus_adr, o_dbus_adr, o_dbus_dat;
  wire o_ibus_cyc, o_dbus_we, o_dbus_cyc, o_mdu_valid;
  wire [3:0] o_dbus_sel;
  wire [31:0] o_ext_rs1, o_ext_rs2;
  wire [2:0] o_ext_funct3;
  reg [31:0] i_ibus_rdt;
  reg [31:0] memory_word=0;
  wire [31:0] i_dbus_rdt=memory_word, i_ext_rd=0;
  wire i_ext_ready=0;
  integer cycles=0;
  wire i_ibus_ack=o_ibus_cyc && cycles%3==2;
  wire i_dbus_ack=o_dbus_cyc && cycles%5==4;

  serv_rf_top dut(.*);

  always @* begin
    case (o_ibus_adr)
      32'h00: i_ibus_rdt=32'h00500093; // addi x1,x0,5
      32'h04: i_ibus_rdt=32'h00108133; // add x2,x1,x1
      32'h08: i_ibus_rdt=32'h00202023; // sw x2,0(x0)
      32'h0c: i_ibus_rdt=32'h00002183; // lw x3,0(x0)
      32'h10: i_ibus_rdt=32'h00218463; // beq x3,x2,+8
      32'h14: i_ibus_rdt=32'h00102223; // unexpected store on failure
      32'h18: i_ibus_rdt=32'h00119213; // slli x4,x3,1
      32'h1c: i_ibus_rdt=32'h401202b3; // sub x5,x4,x1
      32'h20: i_ibus_rdt=32'h0080036f; // jal x6,+8
      32'h24: i_ibus_rdt=32'h00102223; // unexpected store on failure
      32'h28: i_ibus_rdt=32'h00502223; // sw x5,4(x0)
      default: i_ibus_rdt=32'h0000006f;
    endcase
  end

  always #5 clk=~clk;
  initial begin
    repeat(4) @(negedge clk);
    i_rst=0;
  end
  always @(posedge clk) begin
    cycles <= cycles+1;
    if (!i_rst && i_ibus_ack)
      $display("fetch %0d %08h", cycles, o_ibus_adr);
    if (!i_rst && i_dbus_ack) begin
      if (o_dbus_we) begin
        $display("store %0d %08h %08h %h", cycles, o_dbus_adr, o_dbus_dat, o_dbus_sel);
        if (o_dbus_sel !== 4'hf) $fatal(1,"unexpected write mask");
        case (o_dbus_adr)
          0: begin
            if (o_dbus_dat !== 32'd10) $fatal(1,"first store should be 10");
            memory_word <= o_dbus_dat;
          end
          4: begin
            if (o_dbus_dat !== 32'd15 || memory_word !== 32'd10)
              $fatal(1,"final store should be 15");
            $display("PASS");
            $finish;
          end
          default: $fatal(1,"unexpected address");
        endcase
      end else
        $display("load %0d %08h", cycles, o_dbus_adr);
    end
    if (cycles>2000) $fatal(1,"timeout");
  end
endmodule
