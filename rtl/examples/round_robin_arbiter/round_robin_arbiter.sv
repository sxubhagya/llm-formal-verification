// 4-Agent Round-Robin Arbiter with rotating priority pointer
`default_nettype none

module round_robin_arbiter (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [3:0] req,
    output reg  [3:0] grant
);

    reg [1:0] pointer;

    always @(*) begin
        grant = 4'b0000;
        case (pointer)
            2'd0: begin
                if (req[0])      grant = 4'b0001;
                else if (req[1]) grant = 4'b0010;
                else if (req[2]) grant = 4'b0100;
                else if (req[3]) grant = 4'b1000;
            end
            2'd1: begin
                if (req[1])      grant = 4'b0010;
                else if (req[2]) grant = 4'b0100;
                else if (req[3]) grant = 4'b1000;
                else if (req[0]) grant = 4'b0001;
            end
            2'd2: begin
                if (req[2])      grant = 4'b0100;
                else if (req[3]) grant = 4'b1000;
                else if (req[0]) grant = 4'b0001;
                else if (req[1]) grant = 4'b0010;
            end
            2'd3: begin
                if (req[3])      grant = 4'b1000;
                else if (req[0]) grant = 4'b0001;
                else if (req[1]) grant = 4'b0010;
                else if (req[2]) grant = 4'b0100;
            end
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pointer <= 2'd0;
        end else begin
            case (grant)
                4'b0001: pointer <= 2'd1;
                4'b0010: pointer <= 2'd2;
                4'b0100: pointer <= 2'd3;
                4'b1000: pointer <= 2'd0;
                default: pointer <= pointer;
            endcase
        end
    end

endmodule
