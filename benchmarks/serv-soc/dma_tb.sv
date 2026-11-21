module dma_tb;
    reg clk=0, rst=1;
    reg dcyc=0, dwe=0;
    reg [31:0] daddr=0, wdata=0;
    reg [3:0] dsel=15;
    reg set_src=0, set_dst=0, set_len=0, start=0;
    reg [31:0] sram_read=32'hcafe1234;
    wire dack, dma_ack, dma_busy, take_dma, request, wr;
    wire [31:0] addr, data, dma_src, dma_dst;
    wire [3:0] mask;
    wire [15:0] dma_length;
    integer transfers=0;
    soc_bus_dma dut(.*);

    always #5 clk=~clk;
    task automatic configure(input integer slot, input logic [31:0] value);
        @(negedge clk);
        dcyc=1; dwe=1; wdata=value;
        set_src=slot==0; set_dst=slot==1; set_len=slot==2; start=slot==3;
        @(posedge clk); #1;
        if (dack !== 1) $fatal(1,"configuration request rejected");
        @(negedge clk);
        dcyc=0; dwe=0; set_src=0; set_dst=0; set_len=0; start=0;
        @(posedge clk); #1;
    endtask

    task automatic program_dma(input integer src, dst, length);
        configure(0,src);
        configure(1,dst);
        configure(2,length);
        if (dma_src !== src || dma_dst !== dst || dma_length !== 16'(length))
            $fatal(1,"configuration readback");
        configure(3,1);
    endtask

    initial begin
        repeat(2) @(negedge clk);
        rst=0;
        program_dma(16380,0,2);
        if (dma_busy !== 0) $fatal(1,"accepted source crossing SRAM boundary");
        program_dma(0,16380,2);
        if (dma_busy !== 0) $fatal(1,"accepted destination crossing SRAM boundary");
        program_dma(1,0,1);
        if (dma_busy !== 0) $fatal(1,"accepted unaligned source");
        program_dma(16384,0,1);
        if (dma_busy !== 0) $fatal(1,"accepted out-of-range source");
        program_dma(0,0,4097);
        if (dma_busy !== 0) $fatal(1,"accepted oversize count");
        program_dma(0,0,0);
        if (dma_busy !== 0) $fatal(1,"accepted empty transfer");

        program_dma(16380,0,1);
        if (dma_busy !== 1) $fatal(1,"rejected valid final SRAM word");
        repeat(8) @(negedge clk);
        if (dma_busy !== 0 || transfers != 2) $fatal(1,"word copy did not complete");

        program_dma(0,0,4096);
        if (dma_busy !== 1) $fatal(1,"rejected full SRAM range");
        @(negedge clk); rst=1;
        @(posedge clk); #1;
        if ({dma_busy,dack,dma_ack,request} !== 0) $fatal(1,"reset did not cancel DMA");
        $display("PASS DMA limits, exact bank edges, payload and reset");
        $finish;
    end

    always @(posedge clk) if (!rst && request && take_dma) begin
        if (mask !== 4'hf) $fatal(1,"DMA must use all four lanes");
        if (transfers==0 && (addr !== 32'd16380 || wr !== 0))
            $fatal(1,"wrong read at high edge");
        if (transfers==1 && (addr !== 0 || wr !== 1 || data !== 32'hcafe1234))
            $fatal(1,"wrong write payload");
        transfers=transfers+1;
    end
endmodule
