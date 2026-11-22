module increment_selector (
    input wire clk, rst, advance,
    input wire [31:0] left_value, right_value,
    output reg phase,
    output wire [31:0] result
);
    wire [31:0] left, right;
    inc_lane left_lane(.value(left_value), .incremented(left));
    inc_lane right_lane(.value(right_value), .incremented(right));
    always @(posedge clk)
        if (rst) phase <= 1'b0;
        else if (advance) phase <= !phase;
    assign result = phase ? right : left;
endmodule
