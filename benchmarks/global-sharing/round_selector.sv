module round_selector (
    input wire clk, rst, advance,
    input wire [7:0] left_a, left_b, right_a, right_b,
    output reg phase,
    output wire [15:0] result
);
    wire [15:0] left, right;
    mul_lane left_lane(.a(left_a), .b(left_b), .product(left));
    mul_lane right_lane(.a(right_a), .b(right_b), .product(right));
    always @(posedge clk)
        if (rst) phase <= 1'b0;
        else if (advance) phase <= !phase;
    assign result = phase ? right : left;
endmodule
