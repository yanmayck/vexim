module tb;
    reg clk = 0;
    reg [7:0] address;
    wire [7:0] value;
    reg [7:0] expected [0:255];

    aes_sbox dut(.clk(clk), .address(address), .value(value));

    initial begin
        $readmemh("/output/expected.hex", expected);
        for (integer i = 0; i < 256; i = i + 1) begin
            address = 8'(i);
            #2;
            if (i > 0 && value !== expected[i-1])
                $fatal(1,"ROM output changed before a rising edge at address %0d",i);
            clk = 1;
            #2;
            if (value !== expected[i])
                $fatal(1,"ROM lookup %0d: got %h expected %h",i,value,expected[i]);
            clk = 0;
            #2;
        end
        $display("PASS 256 registered lookups");
        $finish;
    end
endmodule
