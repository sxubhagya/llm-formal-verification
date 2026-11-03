// D Flip-Flop with clock enable, synchronous reset, and active-low asynchronous reset
`default_nettype none

module dff_en (
    input  wire clk,
    input  wire rst_n,
    input  wire sync_clr,
    input  wire en,
    input  wire d,
    output reg  q
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            q <= 1'b0;
        end else if (sync_clr) begin
            q <= 1'b0;
        end else if (en) begin
            q <= d;
        end
    end

endmodule
