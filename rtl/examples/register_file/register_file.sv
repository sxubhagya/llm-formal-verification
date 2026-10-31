module register_file (
    input  logic       clk,
    input  logic       write_enable,
    input  logic [2:0] write_address,
    input  logic [2:0] read_address,
    input  logic [7:0] write_data,
    output logic [7:0] read_data
);
    logic [7:0] registers [0:7];

    always_ff @(posedge clk) begin
        if (write_enable)
            registers[write_address] <= write_data;
    end

    always_comb begin
        read_data = registers[read_address];
    end
endmodule
