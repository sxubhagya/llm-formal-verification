module output_register (
    input  logic       clk,
    input  logic       rst_n,
    input  logic [7:0] d,
    output logic [7:0] q
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) q <= '0;
        else        q <= d;
    end
endmodule

module multi_module_top (
    input  logic       clk,
    input  logic       rst_n,
    input  logic [7:0] a,
    input  logic [7:0] b,
    input  logic       subtract,
    output logic [7:0] result
);
    logic [7:0] alu_result;
    alu_core u_alu (
        .a(a), .b(b), .subtract(subtract), .result(alu_result)
    );
    output_register u_out (
        .clk(clk), .rst_n(rst_n), .d(alu_result), .q(result)
    );
endmodule
