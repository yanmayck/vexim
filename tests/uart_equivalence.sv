module uart_equivalence(input logic clk, rst, start, input logic [7:0] data);
wire generated_tx, generated_busy, reference_tx, reference_busy;
uart_tx generated(clk, rst, start, data, generated_tx, generated_busy);
uart_tx_reference reference_uart(clk, rst, start, data, reference_tx, reference_busy);

always @(posedge clk) begin
  if ($initstate) assume(rst);
  else begin
    assert(generated_tx == reference_tx);
    assert(generated_busy == reference_busy);
  end
end
endmodule
