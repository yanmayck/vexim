module board_tb;
    reg clk_12m=0, button_n=1;
    wire uart_tx, spi_mosi, spi_sck, spi_cs_n, pass_led_n;
    icebreaker_soc dut (
        .clk_12m(clk_12m), .button_n(button_n), .spi_miso(spi_mosi),
        .uart_tx(uart_tx), .spi_mosi(spi_mosi), .spi_sck(spi_sck),
        .spi_cs_n(spi_cs_n), .pass_led_n(pass_led_n)
    );
    always #5 clk_12m = !clk_12m;

    localparam [55:0] EXPECTED = 56'h56504153530d0a;
    initial begin
        for (integer index=0; index<7; index=index+1) begin
            reg [7:0] received;
            @(negedge uart_tx);
            repeat(156) @(posedge clk_12m);
            #1;
            for (integer bit_index=0; bit_index<8; bit_index=bit_index+1) begin
                received[bit_index] = uart_tx;
                repeat(104) @(posedge clk_12m);
                #1;
            end
            if (uart_tx !== 1 || received !== EXPECTED[(6-index)*8+:8])
                $fatal(1,"UART byte %0d invalid: %02h",index,received);
        end
        wait(pass_led_n === 0);
        $display("PASS board wrapper: UART bytes 56 50 41 53 53 0d 0a and green LED");
        $finish;
    end
    initial begin
        repeat(50000) @(posedge clk_12m);
        $fatal(1,"board boot timeout");
    end
endmodule
