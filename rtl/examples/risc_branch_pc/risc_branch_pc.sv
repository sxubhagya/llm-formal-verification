// RISC Program Counter and Branch Target Unit
`default_nettype none

module risc_branch_pc (
    input wire        clk,
    input wire        rst_n,
    input wire        pc_enable,
    input wire [31:0] imm,
    input wire [2:0]  branch_type,
    input wire        is_branch,
    input wire        is_jump,
    input wire [31:0] jump_target,
    input wire        zero_flag,
    input wire        less_flag,
    output reg [31:0] pc,
    output wire [31:0] pc_plus_4,
    output wire [31:0] branch_target,
    output reg        take_branch
);

    localparam BR_BEQ  = 3'b000;
    localparam BR_BNE  = 3'b001;
    localparam BR_BLT  = 3'b100;
    localparam BR_BGE  = 3'b101;

    assign pc_plus_4 = pc + 32'd4;
    assign branch_target = pc + imm;

    // Evaluate branch condition
    always @(*) begin
        take_branch = 1'b0;
        if (is_branch) begin
            case (branch_type)
                BR_BEQ: take_branch = zero_flag;
                BR_BNE: take_branch = !zero_flag;
                BR_BLT: take_branch = less_flag;
                BR_BGE: take_branch = !less_flag;
                default: take_branch = 1'b0;
            endcase
        end
    end

    // Next PC selection
    wire [31:0] next_pc;
    assign next_pc = is_jump ? jump_target :
                     take_branch ? branch_target : pc_plus_4;

    // Program Counter register
    always @(posedge clk) begin
        if (!rst_n) begin
            pc <= 32'b0;
        end else if (pc_enable) begin
            pc <= next_pc;
        end
    end

endmodule
`default_nettype wire
