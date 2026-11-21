module tb;
    reg clk=0, rst=1;
    wire spi_mosi, spi_sck, spi_cs_n, uart_tx;
    wire [31:0] signature;
    reg [7:0] tx_byte;
    reg uart_seen=0;
    integer contention=0, spi_bits=0, cycles=0;
    serv_soc dut(.clk(clk), .rst(rst), .spi_miso(spi_mosi), .spi_mosi(spi_mosi),
                 .spi_sck(spi_sck), .spi_cs_n(spi_cs_n), .uart_tx(uart_tx),
                 .signature(signature));

    always #5 clk=~clk;
    initial begin
        repeat(5) @(negedge clk);
        rst=0;
    end

    initial begin
        @(negedge uart_tx);
        repeat(12) @(posedge clk);
        #1;
        for(integer i=0;i<8;i++) begin
            tx_byte[i]=uart_tx;
            repeat(8) @(posedge clk);
            #1;
        end
        if(tx_byte!==8'h56 || uart_tx!==1'b1)
            $fatal(1,"invalid UART frame: %h",tx_byte);
        uart_seen=1;
    end

    always @(posedge spi_sck) begin
        if(spi_cs_n) $fatal(1,"SPI clock while chip deselected");
        spi_bits=spi_bits+1;
    end

    always @(posedge clk) begin
        cycles=cycles+1;
        if(!rst && dut.request && dut.dcyc && dut.dma_busy)
            contention=contention+1;
        if(signature===32'hffffffff) $fatal(1,"boot program verification failed");
        if(signature===32'h5a) begin
            if(!uart_seen || spi_bits!=8 || contention==0)
                $fatal(1,"missing UART/SPI/contention: %b %d %d",uart_seen,spi_bits,contention);
            $display("PASS boot=%0d cycles, DMA contention=%0d, UART=%h, SPI=%0d bits",
                     cycles, contention, tx_byte, spi_bits);
            $finish;
        end
        if(cycles>40000) $fatal(1,"timeout");
    end
endmodule
