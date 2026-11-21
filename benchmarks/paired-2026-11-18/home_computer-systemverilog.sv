module home_computer (
    input  logic        clk,
    input  logic        rst,
    input  logic [15:0] instruction,
    input  logic [7:0]  sensors,
    input  logic [7:0]  net_data,
    input  logic        net_valid,
    output logic [7:0]  pc,
    output logic [7:0]  accumulator,
    output logic [7:0]  gpio,
    output logic        halted,
    output logic        fault,
    output logic        net_ack,
    output logic        reboot
);

    logic [3:0] opcode;
    logic [3:0] unused_instr_mid;
    logic [7:0] imm;
    logic [3:0] addr;

    assign opcode           = instruction[15:12];
    assign unused_instr_mid = instruction[11:8];
    assign imm              = instruction[7:0];
    assign addr             = instruction[3:0];

    logic [7:0] ram [0:15];
    logic [7:0] watchdog;

    wire wdt_expire = (watchdog == 8'd255);
    wire running    = !rst && !wdt_expire && !halted && !fault;

    assign net_ack = running && (opcode == 4'd6) && (imm == 8'd1) && net_valid;

    always_ff @(posedge clk) begin
        if (rst) begin
            pc          <= 8'd0;
            accumulator <= 8'd0;
            gpio        <= 8'd0;
            halted      <= 1'b0;
            fault       <= 1'b0;
            watchdog    <= 8'd0;
            reboot      <= 1'b0;
        end else if (wdt_expire) begin
            pc          <= 8'd0;
            accumulator <= 8'd0;
            gpio        <= 8'd0;
            halted      <= 1'b0;
            fault       <= 1'b0;
            watchdog    <= 8'd0;
            reboot      <= 1'b1;
        end else begin
            reboot <= 1'b0;
            if (halted) begin
                watchdog <= watchdog + 8'd1;
            end else begin
                if (opcode == 4'd10) begin
                    watchdog <= 8'd0;
                end else begin
                    watchdog <= watchdog + 8'd1;
                end

                case (opcode)
                    4'd0: begin // NOP
                        pc <= pc + 8'd1;
                    end
                    4'd1: begin // LDI
                        accumulator <= imm;
                        pc <= pc + 8'd1;
                    end
                    4'd2: begin // ADDI
                        accumulator <= accumulator + imm;
                        pc <= pc + 8'd1;
                    end
                    4'd3: begin // XORI
                        accumulator <= accumulator ^ imm;
                        pc <= pc + 8'd1;
                    end
                    4'd4: begin // LOAD
                        accumulator <= ram[addr];
                        pc <= pc + 8'd1;
                    end
                    4'd5: begin // STORE
                        ram[addr] <= accumulator;
                        pc <= pc + 8'd1;
                    end
                    4'd6: begin // IN
                        case (imm)
                            8'd0: accumulator <= sensors;
                            8'd1: accumulator <= net_valid ? net_data : 8'd0;
                            8'd2: accumulator <= {7'd0, net_valid};
                            default: accumulator <= 8'd0;
                        endcase
                        pc <= pc + 8'd1;
                    end
                    4'd7: begin // OUT
                        gpio <= accumulator;
                        pc <= pc + 8'd1;
                    end
                    4'd8: begin // JMP
                        pc <= imm;
                    end
                    4'd9: begin // JZ
                        if (accumulator == 8'd0)
                            pc <= imm;
                        else
                            pc <= pc + 8'd1;
                    end
                    4'd10: begin // KICK
                        pc <= pc + 8'd1;
                    end
                    4'd11: begin // HALT
                        halted <= 1'b1;
                    end
                    default: begin // 12 through 15: FAULT
                        halted <= 1'b1;
                        fault  <= 1'b1;
                    end
                endcase
            end
        end
    end

endmodule
