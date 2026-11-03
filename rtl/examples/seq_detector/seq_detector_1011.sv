// Sequence Detector FSM for pattern 1011 (with overlapping detection)
`default_nettype none

module seq_detector_1011 (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       data_in,
    output reg        detected,
    output reg  [2:0] state
);

    localparam S_IDLE = 3'b000;
    localparam S_1    = 3'b001;
    localparam S_10   = 3'b010;
    localparam S_101  = 3'b011;
    localparam S_1011 = 3'b100;

    reg [2:0] next_state;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
        end else begin
            state <= next_state;
        end
    end

    always @(*) begin
        next_state = state;
        detected = 1'b0;
        case (state)
            S_IDLE: begin
                next_state = data_in ? S_1 : S_IDLE;
            end
            S_1: begin
                next_state = data_in ? S_1 : S_10;
            end
            S_10: begin
                next_state = data_in ? S_101 : S_IDLE;
            end
            S_101: begin
                if (data_in) begin
                    next_state = S_1011;
                end else begin
                    next_state = S_10;
                end
            end
            S_1011: begin
                detected = 1'b1;
                next_state = data_in ? S_1 : S_10;
            end
            default: begin
                next_state = S_IDLE;
            end
        endcase
    end

endmodule
