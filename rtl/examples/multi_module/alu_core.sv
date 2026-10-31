module alu_core (
    input  logic [7:0] a,
    input  logic [7:0] b,
    input  logic       subtract,
    output logic [7:0] result
);
    always_comb begin
        if (subtract) result = a - b;
        else          result = a + b;
    end
endmodule
