module mem_controller (
    input  logic        clk,
    input  logic        rst,
    input  logic        cmd_valid,
    input  logic        cmd_write,
    input  logic [39:0] cmd_addr,
    input  logic [7:0]  cmd_beats,
    input  logic        w_valid,
    input  logic [63:0] w_data,
    input  logic [7:0]  w_strb,
    input  logic        r_ready,
    input  logic        mem_ready,
    input  logic        mem_w_ready,
    input  logic        mem_r_valid,
    input  logic [63:0] mem_r_data,

    output logic        cmd_ready,
    output logic        w_ready,
    output logic        r_valid,
    output logic [63:0] r_data,
    output logic        r_last,
    output logic        mem_valid,
    output logic        mem_write,
    output logic [39:0] mem_addr,
    output logic [7:0]  mem_beats,
    output logic        mem_w_valid,
    output logic [63:0] mem_w_data,
    output logic [7:0]  mem_w_strb,
    output logic        mem_r_ready,
    output logic        done
);

    typedef enum logic [1:0] {
        S_IDLE,
        S_DESC,
        S_DATA
    } state_t;

    state_t state;

    logic        cur_write;
    logic [39:0] cur_addr;
    logic [7:0]  rem_beats;      // total remaining beats for command
    logic [7:0]  desc_beats;     // beats in current descriptor
    logic [7:0]  desc_rem_beats; // remaining beats in current descriptor

    // Calculate beats to 4 KiB boundary: (4096 - cur_addr[11:0]) / 8
    // Since cur_addr[2:0] == 3'b000, this is 10'd512 - {1'b0, cur_addr[11:3]}
    logic [9:0] beats_to_4k;
    assign beats_to_4k = 10'd512 - {1'b0, cur_addr[11:3]};

    // Calculate min(16, rem_beats, beats_to_4k)
    logic [7:0] min_rem_16;
    assign min_rem_16 = (rem_beats < 8'd16) ? rem_beats : 8'd16;

    logic [7:0] calc_desc_beats;
    assign calc_desc_beats = ( {2'b00, min_rem_16} < beats_to_4k ) ? min_rem_16 : beats_to_4k[7:0];

    // Handshake conditions
    logic data_beat_handshake;
    assign data_beat_handshake = (state == S_DATA) && !rst && (
        cur_write ? (w_valid && mem_w_ready) : (mem_r_valid && r_ready)
    );

    // Combinational outputs
    assign cmd_ready   = !rst && (state == S_IDLE);

    assign mem_valid   = !rst && (state == S_DESC);
    assign mem_write   = cur_write;
    assign mem_addr    = cur_addr;
    assign mem_beats   = desc_beats;

    assign mem_w_valid = !rst && (state == S_DATA) && cur_write && w_valid;
    assign mem_w_data  = w_data;
    assign mem_w_strb  = w_strb;
    assign w_ready     = !rst && (state == S_DATA) && cur_write && mem_w_ready;

    assign r_valid     = !rst && (state == S_DATA) && !cur_write && mem_r_valid;
    assign r_data      = mem_r_data;
    assign r_last      = !rst && (state == S_DATA) && !cur_write && mem_r_valid && (rem_beats == 8'd1);
    assign mem_r_ready = !rst && (state == S_DATA) && !cur_write && r_ready;

    assign done        = data_beat_handshake && (rem_beats == 8'd1);

    // Helper for initialization on command accept or descriptor transition
    logic [9:0] cmd_beats_to_4k;
    assign cmd_beats_to_4k = 10'd512 - {1'b0, cmd_addr[11:3]};
    logic [7:0] cmd_min_16;
    assign cmd_min_16 = (cmd_beats < 8'd16) ? cmd_beats : 8'd16;
    logic [7:0] cmd_first_desc_beats;
    assign cmd_first_desc_beats = ( {2'b00, cmd_min_16} < cmd_beats_to_4k ) ? cmd_min_16 : cmd_beats_to_4k[7:0];

    always_ff @(posedge clk) begin
        if (rst) begin
            state          <= S_IDLE;
            cur_write      <= 1'b0;
            cur_addr       <= 40'd0;
            rem_beats      <= 8'd0;
            desc_beats     <= 8'd0;
            desc_rem_beats <= 8'd0;
        end else begin
            case (state)
                S_IDLE: begin
                    if (cmd_valid) begin
                        cur_write  <= cmd_write;
                        cur_addr   <= cmd_addr;
                        rem_beats  <= cmd_beats;
                        desc_beats <= cmd_first_desc_beats;
                        state      <= S_DESC;
                    end
                end

                S_DESC: begin
                    if (mem_ready) begin
                        desc_rem_beats <= desc_beats;
                        state          <= S_DATA;
                    end
                end

                S_DATA: begin
                    if (data_beat_handshake) begin
                        if (rem_beats == 8'd1) begin
                            state          <= S_IDLE;
                            rem_beats      <= 8'd0;
                            desc_rem_beats <= 8'd0;
                        end else if (desc_rem_beats == 8'd1) begin
                            // Finished current descriptor, prepare next descriptor
                            // Note: cur_addr and rem_beats are updated, so we compute next desc_beats from updated values
                            logic [39:0] next_addr;
                            logic [7:0]  next_rem;
                            logic [9:0]  next_b4k;
                            logic [7:0]  next_m16;
                            next_addr = cur_addr + 40'd8;
                            next_rem  = rem_beats - 8'd1;
                            next_b4k  = 10'd512 - {1'b0, next_addr[11:3]};
                            next_m16  = (next_rem < 8'd16) ? next_rem : 8'd16;

                            cur_addr       <= next_addr;
                            rem_beats      <= next_rem;
                            desc_beats     <= ( {2'b00, next_m16} < next_b4k ) ? next_m16 : next_b4k[7:0];
                            desc_rem_beats <= 8'd0;
                            state          <= S_DESC;
                        end else begin
                            cur_addr       <= cur_addr + 40'd8;
                            rem_beats      <= rem_beats - 8'd1;
                            desc_rem_beats <= desc_rem_beats - 8'd1;
                        end
                    end
                end

                default: begin
                    state <= S_IDLE;
                end
            endcase
        end
    end

    // Suppress unused warnings if any
    logic unused_calc;
    assign unused_calc = ^calc_desc_beats;

endmodule
