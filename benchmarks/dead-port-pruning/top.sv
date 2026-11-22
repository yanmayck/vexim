module prune_demo(
    input wire clk,
    input wire rst,
    input wire [7:0] data,
    input wire [15:0] scratch_data,
    output wire [7:0] value
);
    ip_leaf leaf (
        .clk(clk),
        .rst(rst),
        .data(data),
        .scratch_data(scratch_data),
        .main_result(value),
        .unused_diagnostic()
    );
endmodule
