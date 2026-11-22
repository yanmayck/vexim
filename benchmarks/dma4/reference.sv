module dma4 (
    input logic clk, rst,
    input logic cmd_valid, input logic [1:0] cmd_channel,
    input logic [15:0] cmd_src, cmd_dst, input logic [7:0] cmd_words,
    output logic cmd_ready,
    output logic rd_valid, output logic [15:0] rd_addr, input logic rd_ready,
    input logic rsp_valid, input logic [31:0] rsp_data,
    output logic wr_valid, output logic [15:0] wr_addr,
    output logic [31:0] wr_data, input logic wr_ready,
    output logic done, output logic [1:0] done_channel
);
    localparam IDLE=2'd0, READ=2'd1, RESPONSE=2'd2, WRITE=2'd3;
    logic [1:0] state, next_channel, owner, pick;
    logic [1:0] count [0:3];
    logic head [0:3], tail [0:3];
    logic [15:0] src [0:3][0:1], dst [0:3][0:1];
    logic [7:0] words [0:3][0:1];
    logic [31:0] buffer_data;
    logic found, push, write_fire;
    logic [1:0] candidate;

    always_comb begin
        found=0;
        pick=0;
        for (int offset=0; offset<4; offset++) begin
            candidate=next_channel + 2'(offset);
            if (!found && count[candidate]!=0) begin
                found=1;
                pick=candidate;
            end
        end
    end

    assign cmd_ready = !rst && cmd_words!=0 && count[cmd_channel]!=2;
    assign push = cmd_ready && cmd_valid;
    wire [7:0] active_words = words[owner][head[owner]];
    wire [15:0] next_src = rd_addr + 16'd4;
    wire [15:0] next_dst = wr_addr + 16'd4;
    wire [7:0] remaining = active_words - 8'd1;
    assign rd_valid = !rst && state==READ;
    assign rd_addr = src[owner][head[owner]];
    assign wr_valid = !rst && state==WRITE;
    assign wr_addr = dst[owner][head[owner]];
    assign wr_data = buffer_data;
    assign write_fire = wr_valid && wr_ready;
    assign done = write_fire && active_words==1;
    assign done_channel = owner;

    always_ff @(posedge clk) begin
        if (rst) begin
            state <= IDLE;
            owner <= 0;
            next_channel <= 0;
            buffer_data <= 0;
        end else begin
            if (state==IDLE && found) begin
                owner <= pick;
                state <= READ;
            end
            if (rd_valid && rd_ready) begin
                state <= RESPONSE;
            end
            if (state==RESPONSE && rsp_valid) begin
                buffer_data <= rsp_data;
                state <= WRITE;
            end
            if (write_fire) begin
                next_channel <= owner + 2'd1;
                state <= IDLE;
            end
        end
    end

    for (genvar ch=0; ch<4; ch++) begin : queues
        wire enqueue = push && cmd_channel==ch;
        wire update_head = write_fire && owner==ch;
        wire dequeue = done && owner==ch;
        always_ff @(posedge clk) begin
            if (rst) begin
                count[ch] <= 0;
                head[ch] <= 0;
                tail[ch] <= 0;
                for (int slot=0; slot<2; slot++) begin
                    src[ch][slot] <= 0;
                    dst[ch][slot] <= 0;
                    words[ch][slot] <= 0;
                end
            end else begin
                case ({enqueue,dequeue})
                    2'b10: count[ch] <= count[ch] + 2'd1;
                    2'b01: count[ch] <= count[ch] - 2'd1;
                    default: ;
                endcase
                if (enqueue) begin
                    src[ch][tail[ch]] <= cmd_src;
                    dst[ch][tail[ch]] <= cmd_dst;
                    words[ch][tail[ch]] <= cmd_words;
                    tail[ch] <= !tail[ch];
                end
                if (dequeue)
                    head[ch] <= !head[ch];
                if (update_head && !dequeue) begin
                    src[ch][head[ch]] <= next_src;
                    dst[ch][head[ch]] <= next_dst;
                    words[ch][head[ch]] <= remaining;
                end
            end
        end
    end
endmodule
