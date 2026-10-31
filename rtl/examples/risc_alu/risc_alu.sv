// 32-bit RISC ALU with arithmetic, logical, shift, and status flags
`default_nettype none

module risc_alu (
    input wire [31:0] a,
    input wire [31:0] b,
    input wire [3:0]  alu_op,
    output reg [31:0] out,
    output wire       zero,
    output wire       negative,
    output reg        overflow,
    output reg        carry
);

    // ALU Operations
    localparam OP_ADD  = 4'b0000;
    localparam OP_SUB  = 4'b0001;
    localparam OP_AND  = 4'b0010;
    localparam OP_OR   = 4'b0011;
    localparam OP_XOR  = 4'b0100;
    localparam OP_SLL  = 4'b0101;
    localparam OP_SRL  = 4'b0110;
    localparam OP_SRA  = 4'b0111;
    localparam OP_SLT  = 4'b1000;
    localparam OP_SLTU = 4'b1001;

    reg [32:0] ext_sum;
    reg signed [31:0] signed_a;
    reg signed [31:0] signed_b;

    always @(*) begin
        signed_a = a;
        signed_b = b;
        ext_sum = 33'b0;
        carry = 1'b0;
        overflow = 1'b0;

        case (alu_op)
            OP_ADD: begin
                ext_sum = {1'b0, a} + {1'b0, b};
                out = ext_sum[31:0];
                carry = ext_sum[32];
                overflow = (a[31] == b[31]) && (out[31] != a[31]);
            end
            OP_SUB: begin
                ext_sum = {1'b0, a} - {1'b0, b};
                out = ext_sum[31:0];
                carry = ext_sum[32];
                overflow = (a[31] != b[31]) && (out[31] != a[31]);
            end
            OP_AND: begin
                out = a & b;
            end
            OP_OR: begin
                out = a | b;
            end
            OP_XOR: begin
                out = a ^ b;
            end
            OP_SLL: begin
                out = a << b[4:0];
            end
            OP_SRL: begin
                out = a >> b[4:0];
            end
            OP_SRA: begin
                out = signed_a >>> b[4:0];
            end
            OP_SLT: begin
                out = (signed_a < signed_b) ? 32'b1 : 32'b0;
            end
            OP_SLTU: begin
                out = (a < b) ? 32'b1 : 32'b0;
            end
            default: begin
                out = 32'b0;
            end
        endcase
    end

    assign zero = (out == 32'b0);
    assign negative = out[31];

endmodule
`default_nettype wire
