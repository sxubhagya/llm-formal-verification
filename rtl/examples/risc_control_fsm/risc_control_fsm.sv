// Multi-cycle RISC instruction decoder and control FSM
`default_nettype none

module risc_control_fsm (
    input wire       clk,
    input wire       rst_n,
    input wire [6:0] opcode,
    output reg       pc_write,
    output reg       ir_write,
    output reg       reg_write,
    output reg       mem_read,
    output reg       mem_write,
    output reg       alu_src_a,
    output reg [1:0] alu_src_b,
    output reg [1:0] alu_op,
    output reg [2:0] state_out
);

    // State definitions
    localparam S_FETCH     = 3'b000;
    localparam S_DECODE    = 3'b001;
    localparam S_EXEC_ALU  = 3'b010;
    localparam S_MEM_ADDR  = 3'b011;
    localparam S_MEM_READ  = 3'b100;
    localparam S_MEM_WRITE = 3'b101;
    localparam S_WRITEBACK = 3'b110;

    // RISC-V 32I base opcodes
    localparam OP_R_TYPE = 7'b0110011;
    localparam OP_I_TYPE = 7'b0010011;
    localparam OP_LOAD   = 7'b0000011;
    localparam OP_STORE  = 7'b0100011;
    localparam OP_BRANCH = 7'b1100011;

    reg [2:0] current_state, next_state;

    // Sequential state register
    always @(posedge clk) begin
        if (!rst_n) begin
            current_state <= S_FETCH;
        end else begin
            current_state <= next_state;
        end
    end

    // Next-state transition logic
    always @(*) begin
        case (current_state)
            S_FETCH: begin
                next_state = S_DECODE;
            end
            S_DECODE: begin
                case (opcode)
                    OP_R_TYPE: next_state = S_EXEC_ALU;
                    OP_I_TYPE: next_state = S_EXEC_ALU;
                    OP_LOAD:   next_state = S_MEM_ADDR;
                    OP_STORE:  next_state = S_MEM_ADDR;
                    default:   next_state = S_FETCH;
                endcase
            end
            S_EXEC_ALU: begin
                next_state = S_WRITEBACK;
            end
            S_MEM_ADDR: begin
                if (opcode == OP_LOAD) begin
                    next_state = S_MEM_READ;
                end else begin
                    next_state = S_MEM_WRITE;
                end
            end
            S_MEM_READ: begin
                next_state = S_WRITEBACK;
            end
            S_MEM_WRITE: begin
                next_state = S_FETCH;
            end
            S_WRITEBACK: begin
                next_state = S_FETCH;
            end
            default: begin
                next_state = S_FETCH;
            end
        endcase
    end

    // Output control signals
    always @(*) begin
        pc_write   = 1'b0;
        ir_write   = 1'b0;
        reg_write  = 1'b0;
        mem_read   = 1'b0;
        mem_write  = 1'b0;
        alu_src_a  = 1'b0;
        alu_src_b  = 2'b00;
        alu_op     = 2'b00;
        state_out  = current_state;

        case (current_state)
            S_FETCH: begin
                mem_read  = 1'b1;
                ir_write  = 1'b1;
                alu_src_a = 1'b0; // PC
                alu_src_b = 2'b01; // +4
                pc_write  = 1'b1;
            end
            S_DECODE: begin
                alu_src_a = 1'b0;
                alu_src_b = 2'b10; // offset
            end
            S_EXEC_ALU: begin
                alu_src_a = 1'b1;
                alu_src_b = 2'b00;
                alu_op    = 2'b10; // Function determined
            end
            S_MEM_ADDR: begin
                alu_src_a = 1'b1;
                alu_src_b = 2'b10; // Immediate offset
            end
            S_MEM_READ: begin
                mem_read = 1'b1;
            end
            S_MEM_WRITE: begin
                mem_write = 1'b1;
            end
            S_WRITEBACK: begin
                reg_write = 1'b1;
            end
            default: begin
                // Defaults
            end
        endcase
    end

endmodule
`default_nettype wire
