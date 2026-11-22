module mul_lane (
    input wire [7:0] a, b,
    output wire [15:0] product
);
    assign product = a * b;
endmodule
