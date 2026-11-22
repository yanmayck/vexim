module icebreaker_soc (
    input wire clk_12m, button_n, spi_miso,
    output wire uart_tx, spi_mosi, spi_sck, spi_cs_n, pass_led_n
);
    reg [3:0] reset_pipe = 4'hf;
    wire [31:0] signature;

    always @(posedge clk_12m)
        reset_pipe <= button_n ? {reset_pipe[2:0], 1'b0} : 4'hf;

    serv_soc system (
        .clk(clk_12m), .rst(reset_pipe[3]), .spi_miso(spi_miso), .uart_tx(uart_tx),
        .spi_mosi(spi_mosi), .spi_sck(spi_sck), .spi_cs_n(spi_cs_n),
        .signature(signature)
    );
    assign pass_led_n = signature != 32'h5a;
endmodule
