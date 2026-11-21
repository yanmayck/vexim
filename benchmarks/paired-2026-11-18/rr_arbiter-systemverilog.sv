module rr_arbiter (
    input  logic       clk,
    input  logic       rst,
    input  logic [3:0] req,
    input  logic       ready,
    output logic       valid,
    output logic [3:0] grant
);

    logic [1:0] prio_idx;
    logic       locked;
    logic [3:0] locked_grant;

    logic [3:0] arb_grant;
    logic [1:0] grant_idx;

    always_comb begin
        arb_grant = 4'b0000;
        case (prio_idx)
            2'd0: begin
                if      (req[0]) arb_grant = 4'b0001;
                else if (req[1]) arb_grant = 4'b0010;
                else if (req[2]) arb_grant = 4'b0100;
                else if (req[3]) arb_grant = 4'b1000;
            end
            2'd1: begin
                if      (req[1]) arb_grant = 4'b0010;
                else if (req[2]) arb_grant = 4'b0100;
                else if (req[3]) arb_grant = 4'b1000;
                else if (req[0]) arb_grant = 4'b0001;
            end
            2'd2: begin
                if      (req[2]) arb_grant = 4'b0100;
                else if (req[3]) arb_grant = 4'b1000;
                else if (req[0]) arb_grant = 4'b0001;
                else if (req[1]) arb_grant = 4'b0010;
            end
            2'd3: begin
                if      (req[3]) arb_grant = 4'b1000;
                else if (req[0]) arb_grant = 4'b0001;
                else if (req[1]) arb_grant = 4'b0010;
                else if (req[2]) arb_grant = 4'b0100;
            end
        endcase
    end

    always_comb begin
        if (rst) begin
            grant = 4'b0000;
            valid = 1'b0;
        end else if (locked) begin
            grant = locked_grant;
            valid = 1'b1;
        end else begin
            grant = arb_grant;
            valid = |arb_grant;
        end
    end

    always_comb begin
        case (grant)
            4'b0001: grant_idx = 2'd0;
            4'b0010: grant_idx = 2'd1;
            4'b0100: grant_idx = 2'd2;
            4'b1000: grant_idx = 2'd3;
            default: grant_idx = 2'd0;
        endcase
    end

    always_ff @(posedge clk) begin
        if (rst) begin
            prio_idx     <= 2'd0;
            locked       <= 1'b0;
            locked_grant <= 4'b0000;
        end else begin
            if (valid && ready) begin
                prio_idx <= grant_idx + 2'd1;
                locked   <= 1'b0;
            end else if (valid && !ready) begin
                locked       <= 1'b1;
                locked_grant <= grant;
            end
        end
    end

endmodule
