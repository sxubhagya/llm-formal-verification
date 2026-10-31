// 32-register x 32-bit RISC Register File with Hardwired x0 Zero
`default_nettype none

module risc_regfile (
    input wire        clk,
    input wire        rst_n,
    input wire        we,
    input wire [4:0]  waddr,
    input wire [31:0] wdata,
    input wire [4:0]  raddr1,
    output wire [31:0] rdata1,
    input wire [4:0]  raddr2,
    output wire [31:0] rdata2
);

    reg [31:0] registers [31:1];
    integer i;

    // Synchronous write; x0 is never stored
    always @(posedge clk) begin
        if (!rst_n) begin
            for (i = 1; i < 32; i = i + 1) begin
                registers[i] <= 32'b0;
            end
        end else if (we && (waddr != 5'b00000)) begin
            registers[waddr] <= wdata;
        end
    end

    // Asynchronous read: raddr == 0 always yields 32'b0
    assign rdata1 = (raddr1 == 5'b00000) ? 32'b0 :
                    (we && (waddr == raddr1)) ? wdata : registers[raddr1];

    assign rdata2 = (raddr2 == 5'b00000) ? 32'b0 :
                    (we && (waddr == raddr2)) ? wdata : registers[raddr2];

endmodule
`default_nettype wire
