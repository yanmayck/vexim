module serv_soc (
    input wire clk, rst,
    input wire spi_miso,
    output wire spi_mosi, spi_sck, spi_cs_n, uart_tx,
    output reg [31:0] signature
);
    wire [31:0] iaddr, daddr, wdata;
    wire [3:0] dsel;
    wire icyc, dcyc, dwe;
    reg iack;
`ifdef VEXIM_BUS_DMA
    wire dack, dma_ack;
`else
    reg dack, dma_ack;
`endif
    reg [31:0] idata, mmio_read;
    reg read_sram;
    wire [31:0] rdata = read_sram ? sram_read : mmio_read;
    reg [31:0] rom [0:63];
`ifdef UP5K_SPRAM
    wire [31:0] sram_read;
`else
    reg [31:0] sram_read;
    reg [7:0] sram0 [0:4095];
    reg [7:0] sram1 [0:4095];
    reg [7:0] sram2 [0:4095];
    reg [7:0] sram3 [0:4095];
`endif
    reg [31:0] timer_count, timer_compare;
    reg timer_enable;

    initial $readmemh("boot.hex", rom);

`ifdef VEXIM_CPU
    serv_rf_vex cpu (
        .no_reset(1'b0),
`else
    serv_rf_top cpu (
`endif
        .clk(clk), .i_rst(rst),
        .i_timer_irq(timer_enable && timer_count >= timer_compare),
        .o_ibus_adr(iaddr), .o_ibus_cyc(icyc),
        .i_ibus_rdt(idata), .i_ibus_ack(iack),
        .o_dbus_adr(daddr), .o_dbus_dat(wdata), .o_dbus_sel(dsel),
        .o_dbus_we(dwe), .o_dbus_cyc(dcyc), .i_dbus_rdt(rdata), .i_dbus_ack(dack),
        .o_ext_rs1(), .o_ext_rs2(), .o_ext_funct3(), .o_mdu_valid(),
        .i_ext_rd(32'd0), .i_ext_ready(1'b0)
    );

    always @(posedge clk) begin
        if (rst) iack <= 0;
        else begin
            iack <= icyc && !iack;
            if (icyc && !iack)
                idata <= iaddr[31:8] == 0 ? rom[iaddr[7:2]] : 32'h0000006f;
        end
    end

    localparam [31:0] IO = 32'h10000000;
`ifdef VEXIM_BUS_DMA
    wire [31:0] dma_src, dma_dst, addr, data;
    wire [15:0] dma_length;
    wire dma_busy, take_dma, request, wr;
    wire [3:0] mask;
    soc_bus_dma bus_dma (
        .clk(clk), .rst(rst), .dcyc(dcyc), .dwe(dwe),
        .daddr(daddr), .wdata(wdata), .dsel(dsel),
        .set_src(io_write && addr == IO + 0), .set_dst(io_write && addr == IO + 4),
        .set_len(io_write && addr == IO + 8), .start(io_write && addr == IO + 12),
        .sram_read(sram_read), .dack(dack), .dma_ack(dma_ack), .dma_busy(dma_busy),
        .take_dma(take_dma), .request(request), .addr(addr), .data(data),
        .mask(mask), .wr(wr), .dma_src(dma_src), .dma_dst(dma_dst), .dma_length(dma_length)
    );
`else
    reg [31:0] dma_src, dma_dst, dma_address_src, dma_address_dst;
    reg [15:0] dma_length, dma_left;
    reg [31:0] dma_buffer;
    localparam [1:0] IDLE=0, READ_WORD=1, WRITE_WORD=2;
    reg [1:0] dma_state;
    wire dma_busy = dma_state != IDLE;

    reg last_dma;
    wire take_dma = dma_busy && (!dcyc || !last_dma);
    wire request = !rst && !dack && !dma_ack && (take_dma || dcyc);
    wire [31:0] addr = take_dma
        ? (dma_state == WRITE_WORD ? dma_address_dst : dma_address_src) : daddr;
    wire [31:0] data = take_dma ? dma_buffer : wdata;
    wire [3:0] mask = take_dma ? 4'hf : dsel;
    wire wr = take_dma ? dma_state == WRITE_WORD : dwe;
`endif
    wire in_sram = addr[31:14] == 0;
    wire [11:0] word_index = addr[13:2];
    wire io_write = request && !take_dma && wr && mask == 4'hf;

`ifdef UP5K_SPRAM
    // Each byte enable drives two nibble enables in the hard SRAM.
    for (genvar half=0; half<2; half=half+1) begin: spram
        SB_SPRAM256KA bank (
            .ADDRESS({2'b00,word_index}), .DATAIN(data[half*16+:16]),
            .MASKWREN({{2{mask[half*2+1]}},{2{mask[half*2]}}}),
            .WREN(wr), .CHIPSELECT(request && in_sram), .CLOCK(clk),
            .STANDBY(1'b0), .SLEEP(1'b0), .POWEROFF(1'b1),
            .DATAOUT(sram_read[half*16+:16])
        );
    end
`endif

    reg [9:0] uart_frame;
    reg [3:0] uart_left;
    reg [3:0] uart_div;
    assign uart_tx = uart_left == 0 ? 1'b1 : uart_frame[0];

    reg [7:0] spi_tx, spi_rx;
    reg [3:0] spi_left;
    reg spi_clock;
    assign spi_mosi = spi_tx[7];
    assign spi_sck = spi_clock;
    assign spi_cs_n = spi_left == 0;

    reg [31:0] read_value;
    always @* begin
        case (addr)
            IO + 0: read_value = dma_src;
            IO + 4: read_value = dma_dst;
            IO + 8: read_value = {16'b0, dma_length};
            IO + 12: read_value = {31'b0, dma_busy};
            IO + 20: read_value = {31'b0, uart_left != 0};
            IO + 24: read_value = timer_count;
            IO + 28: read_value = timer_compare;
            IO + 32: read_value = {31'b0, timer_enable};
            IO + 40: read_value = {31'b0, spi_left != 0};
            IO + 44: read_value = {24'b0, spi_rx};
            IO + 48: read_value = signature;
            default: read_value = 0;
        endcase
    end

    always @(posedge clk) begin
        if (rst) begin
`ifndef VEXIM_BUS_DMA
            dack <= 0;
            dma_ack <= 0;
            last_dma <= 0;
`endif
        end else begin
`ifndef VEXIM_BUS_DMA
            dack <= request && !take_dma;
            dma_ack <= request && take_dma;
`endif
            if (request) begin
`ifndef VEXIM_BUS_DMA
                last_dma <= take_dma;
`endif
                read_sram <= in_sram;
                mmio_read <= read_value;
`ifndef UP5K_SPRAM
                sram_read <= {sram3[word_index], sram2[word_index],
                              sram1[word_index], sram0[word_index]};
                if (wr && in_sram) begin
                    if (mask[0]) sram0[word_index] <= data[7:0];
                    if (mask[1]) sram1[word_index] <= data[15:8];
                    if (mask[2]) sram2[word_index] <= data[23:16];
                    if (mask[3]) sram3[word_index] <= data[31:24];
                end
`endif
            end
        end
    end

    always @(posedge clk) begin
        if (rst) begin
`ifndef VEXIM_BUS_DMA
            dma_src <= 0;
            dma_dst <= 0;
            dma_length <= 0;
            dma_left <= 0;
            dma_state <= IDLE;
`endif
            timer_count <= 0;
            timer_compare <= 0;
            timer_enable <= 0;
            uart_left <= 0;
            uart_div <= 0;
            uart_frame <= '1;
            spi_left <= 0;
            spi_clock <= 0;
            spi_tx <= 0;
            spi_rx <= 0;
            signature <= 0;
        end else begin
            timer_count <= timer_count+1;
            if (uart_left != 0) begin
                if (uart_div == 7) begin
                    uart_div <= 0;
                    uart_left <= uart_left-1;
                    uart_frame <= {1'b1,uart_frame[9:1]};
                end else uart_div <= uart_div+1;
            end
            if (spi_left != 0) begin
                spi_clock <= !spi_clock;
                if (!spi_clock) spi_rx <= {spi_rx[6:0],spi_miso};
                else begin
                    spi_tx <= {spi_tx[6:0],1'b0};
                    spi_left <= spi_left-1;
                end
            end
`ifndef VEXIM_BUS_DMA
            if (dma_ack) begin
                if (dma_state == READ_WORD) begin
                    dma_buffer <= sram_read;
                    dma_state <= WRITE_WORD;
                end else if (dma_state == WRITE_WORD) begin
                    dma_address_src <= dma_address_src+4;
                    dma_address_dst <= dma_address_dst+4;
                    dma_left <= dma_left-1;
                    dma_state <= dma_left == 1 ? IDLE : READ_WORD;
                end
            end
`endif
            if (io_write) begin
                case (addr)
`ifndef VEXIM_BUS_DMA
                    IO + 0: if (!dma_busy) dma_src <= data;
                    IO + 4: if (!dma_busy) dma_dst <= data;
                    IO + 8: if (!dma_busy) dma_length <= data[15:0];
                    IO + 12: if (!dma_busy && data[0] && dma_length != 0 &&
                        dma_src[1:0] == 0 && dma_dst[1:0] == 0 &&
                        dma_src < 16384 && dma_dst < 16384 &&
                        {16'b0,dma_length} <= ((16384-dma_src)>>2) &&
                        {16'b0,dma_length} <= ((16384-dma_dst)>>2)) begin
                        dma_address_src <= dma_src;
                        dma_address_dst <= dma_dst;
                        dma_left <= dma_length;
                        dma_state <= READ_WORD;
                    end
`endif
                    IO + 16: if (uart_left == 0) begin
                        uart_frame <= {1'b1,data[7:0],1'b0};
                        uart_left <= 10;
                        uart_div <= 0;
                    end
                    IO + 28: timer_compare <= data;
                    IO + 32: timer_enable <= data[0];
                    IO + 36: if (spi_left == 0) begin
                        spi_tx <= data[7:0];
                        spi_left <= 8;
                        spi_rx <= 0;
                    end
                    IO + 48: signature <= data;
                    default: ;
                endcase
            end
        end
    end
endmodule
