module round_selector_tb;
    reg clk = 0, rst = 1, advance = 0;
    reg [7:0] left_a = 0, left_b = 0, right_a = 0, right_b = 0;
    wire gold_phase, gate_phase;
    wire [15:0] gold_result, gate_result;
    gold gold_impl(.clk(clk), .rst(rst), .advance(advance),
        .left_a(left_a), .left_b(left_b), .right_a(right_a), .right_b(right_b),
        .phase(gold_phase), .result(gold_result));
    gate gate_impl(.clk(clk), .rst(rst), .advance(advance),
        .left_a(left_a), .left_b(left_b), .right_a(right_a), .right_b(right_b),
        .phase(gate_phase), .result(gate_result));

    task automatic tick;
        #1; clk = 1;
        #1; clk = 0;
    endtask

    task automatic compare(input bit expected_phase, input logic [15:0] expected);
        #1;
        if (gold_phase !== expected_phase || gate_phase !== expected_phase ||
            gold_result !== expected || gate_result !== expected)
            $fatal(1, "phase %0d: expected %h, gold %h, gate %h",
                   expected_phase, expected, gold_result, gate_result);
    endtask

    initial begin
        tick();
        rst = 0;
        for (integer i=0; i<256; i=i+1)
            for (integer j=0; j<256; j=j+1) begin
                left_a = i; left_b = j;
                right_a = 255-i; right_b = 255-j;
                advance = 1;
                compare(0, i*j);
                tick();
                compare(1, (255-i)*(255-j));
                tick();
            end
        $display("PASS all 65,536 operand pairs in both phases");
        $finish;
    end
endmodule
