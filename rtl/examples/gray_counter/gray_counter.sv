// 4-bit Parameterized Gray Code Counter with synchronous active-low reset and enable
`default_nettype none

module gray_counter (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       enable,
    output reg  [3:0] gray_out,
    output reg  [3:0] bin_out
);

    reg  [3:0] bin_next;
    wire [3:0] gray_next;

    always @(*) begin
        if (enable)
            bin_next = bin_out + 4'd1;
        else
            bin_next = bin_out;
    end

    assign gray_next = bin_next ^ (bin_next >> 1);

    always @(posedge clk) begin
        if (!rst_n) begin
            bin_out  <= 4'b0000;
            gray_out <= 4'b0000;
        end else begin
            bin_out  <= bin_next;
            gray_out <= gray_next;
        end
    end

endmodule
