module adder_ref(input logic [7:0] a,b, output logic [8:0] sum);
assign sum = {1'b0,a} + {1'b0,b};
endmodule
