module packet_switch_ref #(
    parameter PORTS=4, PTR=6
) (
    input clk, rst,
    input [PORTS-1:0] in_valid, in_last, out_ready,
    input [4*PORTS-1:0] in_dest,
    input [32*PORTS-1:0] in_data,
    output [PORTS-1:0] in_ready, out_valid, out_last,
    output [32*PORTS-1:0] out_data
);
    wire [PORTS-1:0] can_accept [0:PORTS-1];
    wire [PORTS-1:0] available [0:PORTS-1];
    wire [PORTS-1:0] grant [0:PORTS-1];
    wire [32:0] word_at [0:PORTS-1][0:PORTS-1];

    for (genvar i=0; i<PORTS; i++) begin : ingress
        assign in_ready[i] = !rst && (|can_accept[i]);
        for (genvar o=0; o<PORTS; o++) begin : queues
            reg [32:0] memory [0:(1<<PTR)-1];
            reg [PTR-1:0] rd, wr;
            reg full, valid;
            reg [32:0] ram_q, bypass_word;
            reg bypass;
            wire push = in_valid[i] && can_accept[i][o] && !rst;
            wire pop = grant[o][i] && out_valid[o] && out_ready[o];
            wire [PTR-1:0] rd_next = rd + PTR'(pop);
            wire [PTR-1:0] wr_next = wr + PTR'(push);
            wire [32:0] data = {in_last[i], in_data[32*i+:32]};

            assign can_accept[i][o] = in_dest[4*i+:4]==4'(o) && !full;
            assign available[o][i] = valid;
            assign word_at[o][i] = bypass ? bypass_word : ram_q;

            always @(posedge clk) begin
                if (push)
                    memory[wr] <= data;
                ram_q <= memory[rd_next];
                if (rst) begin
                    rd <= 0;
                    wr <= 0;
                    full <= 0;
                    valid <= 0;
                    bypass <= 0;
                    bypass_word <= 0;
                end else begin
                    rd <= rd_next;
                    wr <= wr_next;
                    if (push && !pop && rd_next==wr_next)
                        full <= 1;
                    else if (pop)
                        full <= 0;
                    if (push)
                        valid <= 1;
                    else if (pop && rd_next==wr_next)
                        valid <= 0;
                    bypass <= push && rd_next==wr;
                    bypass_word <= data;
                end
            end
        end
    end

    for (genvar o=0; o<PORTS; o++) begin : egress
        reg locked;
        reg [3:0] cursor, lock_id;
        reg [3:0] first_eligible, first_any, pick;
        reg [32:0] payload;
        reg [PORTS-1:0] mask;
        always @* begin
            first_eligible=0;
            first_any=0;
            for (integer i=PORTS-1; i>=0; i=i-1) begin
                if (available[o][i]) begin
                    first_any=4'(i+1);
                    if (4'(i)>=cursor)
                        first_eligible=4'(i+1);
                end
            end
            pick=first_eligible!=0 ? first_eligible : first_any;
            if (locked)
                pick=available[o][lock_id] ? lock_id+4'd1 : 4'd0;
            payload=0;
            mask=0;
            for (integer i=0; i<PORTS; i=i+1)
                if (pick==4'(i+1)) begin
                    payload=payload | word_at[o][i];
                    mask[i]=1;
                end
        end
        assign grant[o]=mask;
        assign out_valid[o]=pick!=0 && !rst;
        assign {out_last[o],out_data[32*o+:32]}=payload;

        wire completed=out_valid[o] && out_ready[o] && out_last[o];
        always @(posedge clk) begin
            if (rst) begin
                locked<=0;
                cursor<=0;
                lock_id<=0;
            end else begin
                locked<=(locked || out_valid[o]) && !completed;
                if (out_valid[o])
                    lock_id<=pick-4'd1;
                if (completed)
                    cursor<=pick;
            end
        end
    end
endmodule
