// RISC Pipeline Hazard Detection and Forwarding Unit
`default_nettype none

module risc_hazard (
    // Forwarding inputs
    input wire [4:0] id_ex_rs1,
    input wire [4:0] id_ex_rs2,
    input wire [4:0] ex_mem_rd,
    input wire       ex_mem_reg_write,
    input wire [4:0] mem_wb_rd,
    input wire       mem_wb_reg_write,

    // Hazard stall inputs
    input wire [4:0] if_id_rs1,
    input wire [4:0] if_id_rs2,
    input wire [4:0] id_ex_rd,
    input wire       id_ex_mem_read,

    // Forwarding outputs
    output reg [1:0] forward_a,
    output reg [1:0] forward_b,

    // Hazard stall outputs
    output wire      stall,
    output wire      flush
);

    // Forwarding multiplexer controls
    // 2'b00: From Register File (no hazard)
    // 2'b01: Forward from MEM/WB stage
    // 2'b10: Forward from EX/MEM stage

    always @(*) begin
        // Forward A (rs1)
        if (ex_mem_reg_write && (ex_mem_rd != 5'b00000) && (ex_mem_rd == id_ex_rs1)) begin
            forward_a = 2'b10;
        end else if (mem_wb_reg_write && (mem_wb_rd != 5'b00000) && (mem_wb_rd == id_ex_rs1)) begin
            forward_a = 2'b01;
        end else begin
            forward_a = 2'b00;
        end

        // Forward B (rs2)
        if (ex_mem_reg_write && (ex_mem_rd != 5'b00000) && (ex_mem_rd == id_ex_rs2)) begin
            forward_b = 2'b10;
        end else if (mem_wb_reg_write && (mem_wb_rd != 5'b00000) && (mem_wb_rd == id_ex_rs2)) begin
            forward_b = 2'b01;
        end else begin
            forward_b = 2'b00;
        end
    end

    // Load-use hazard detection:
    // If an instruction in EX stage is a LOAD, and its destination register (id_ex_rd)
    // matches either source register of the instruction in ID stage (if_id_rs1 or if_id_rs2),
    // stall the IF/ID stages and flush the ID/EX stage by inserting a bubble.
    wire load_use_hazard;
    assign load_use_hazard = id_ex_mem_read &&
                            (id_ex_rd != 5'b00000) &&
                            ((id_ex_rd == if_id_rs1) || (id_ex_rd == if_id_rs2));

    assign stall = load_use_hazard;
    assign flush = load_use_hazard;

endmodule
`default_nettype wire
