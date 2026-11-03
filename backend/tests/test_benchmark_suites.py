"""Comprehensive formal verification benchmark test suites for:
- Gray Code Counter (12-property suite)
- Flip-Flops (Enable, Synchronous & Asynchronous Reset)
- FSMs (Traffic Light controller & Sequence Detector)
- Round-Robin Arbiter (One-hot mutual exclusion, request-grant matching, quiescence)
- RISC processor components (ALU, RegFile, Control FSM, Branch PC, Hazard Unit)
"""
import unittest
from pathlib import Path

from backend.app.models.design_ir import DesignIR, ModuleIR, PortIR, ModuleSummaryIR, RegisterIR
from backend.app.models.property_models import (
    PropertyBatch, CandidateProperty, PropertyCategory, AssertionLanguage,
    SignalReference, ClockContext, ResetContext, VerificationStatus
)
from backend.app.models.formal_models import ProofMode, SolverEngine, FormalVerificationRequest
from backend.app.services.formal.checker_synthesizer import CheckerSynthesizer
from backend.app.services.formal.sby_runner import SBYRunner
from backend.app.services.formal.verification_service import FormalVerificationService


class BenchmarkSuitesTests(unittest.TestCase):

    def setUp(self):
        self.synthesizer = CheckerSynthesizer()
        self.runner = SBYRunner()

    # =========================================================================
    # 1. Gray Code Counter (12 Properties)
    # =========================================================================
    def test_gray_counter_12_properties_synthesis_and_parsing(self):
        design = DesignIR(
            top_module="gray_counter",
            source_files=["gray_counter.sv"],
            modules=[
                ModuleIR(
                    name="gray_counter",
                    ports=[
                        PortIR(name="clk", direction="input", bit_width=1, bits=[1]),
                        PortIR(name="rst_n", direction="input", bit_width=1, bits=[2]),
                        PortIR(name="enable", direction="input", bit_width=1, bits=[3]),
                        PortIR(name="gray_out", direction="output", bit_width=4, bits=[4, 5, 6, 7]),
                        PortIR(name="bin_out", direction="output", bit_width=4, bits=[8, 9, 10, 11]),
                    ],
                    registers=[RegisterIR(
                        cell_name="bin_out_reg", cell_type="",
                        clock_bits=[1], reset_bits=[2],
                        parameters={"CLK_POLARITY": "1", "SRST_POLARITY": "0"}
                    )],
                    clock_candidates=[{"name": "clk", "signal": "clk", "bits": [1]}],
                    reset_candidates=[{"name": "rst_n", "signal": "rst_n", "bits": [2], "kind": "synchronous"}],
                    summary=ModuleSummaryIR(port_count=5)
                )
            ]
        )

        clk_ctx = ClockContext(signal="clk", edge="posedge")
        rst_ctx = ResetContext(signal="rst_n", polarity="active_low", asynchronous=False)

        properties = [
            # P1: MSB of Gray code equals MSB of binary counter
            CandidateProperty(
                property_id="GRAY_P01_MSB_EQUAL", design_top="gray_counter", module="gray_counter",
                name="gray_msb_equals_bin_msb", description="Gray MSB always equals binary MSB",
                category=PropertyCategory.INVARIANT, assertion_language=AssertionLanguage.BOOLEAN,
                expression="gray_out[3] == bin_out[3]",
                signals=[SignalReference(name="gray_out", expected_width=4), SignalReference(name="bin_out", expected_width=4)],
                clock=clk_ctx, reset=rst_ctx
            ),
            # P2: Gray conversion equation invariant
            CandidateProperty(
                property_id="GRAY_P02_CONVERSION", design_top="gray_counter", module="gray_counter",
                name="gray_conversion_formula", description="gray_out equals bin_out ^ (bin_out >> 1)",
                category=PropertyCategory.INVARIANT, assertion_language=AssertionLanguage.BOOLEAN,
                expression="gray_out == (bin_out ^ (bin_out >> 1))",
                signals=[SignalReference(name="gray_out", expected_width=4), SignalReference(name="bin_out", expected_width=4)],
                clock=clk_ctx, reset=rst_ctx
            ),
            # P3: Zero preserve
            CandidateProperty(
                property_id="GRAY_P03_ZERO_PRESERVE", design_top="gray_counter", module="gray_counter",
                name="zero_preservation", description="bin_out is zero implies gray_out is zero",
                category=PropertyCategory.INVARIANT, assertion_language=AssertionLanguage.BOOLEAN,
                expression="!(bin_out == 4'b0000) || (gray_out == 4'b0000)",
                signals=[SignalReference(name="bin_out", expected_width=4), SignalReference(name="gray_out", expected_width=4)],
                clock=clk_ctx, reset=rst_ctx
            ),
            # P4: Binary count range upper bound
            CandidateProperty(
                property_id="GRAY_P04_BIN_BOUND", design_top="gray_counter", module="gray_counter",
                name="binary_count_bound", description="bin_out is bounded within 4 bits",
                category=PropertyCategory.INVARIANT, assertion_language=AssertionLanguage.BOOLEAN,
                expression="bin_out <= 4'd15",
                signals=[SignalReference(name="bin_out", expected_width=4)],
                clock=clk_ctx, reset=rst_ctx
            ),
            # P5: Gray count range upper bound
            CandidateProperty(
                property_id="GRAY_P05_GRAY_BOUND", design_top="gray_counter", module="gray_counter",
                name="gray_count_bound", description="gray_out is bounded within 4 bits",
                category=PropertyCategory.INVARIANT, assertion_language=AssertionLanguage.BOOLEAN,
                expression="gray_out <= 4'd15",
                signals=[SignalReference(name="gray_out", expected_width=4)],
                clock=clk_ctx, reset=rst_ctx
            ),
            # P6: Enable disabled holds binary counter
            CandidateProperty(
                property_id="GRAY_P06_ENABLE_HOLD_BIN", design_top="gray_counter", module="gray_counter",
                name="enable_hold_binary", description="Disabling enable preserves binary count",
                category=PropertyCategory.TEMPORAL, assertion_language=AssertionLanguage.SVA,
                expression="disable iff (!rst_n) !enable |=> bin_out == (bin_out)",
                signals=[SignalReference(name="enable", expected_width=1), SignalReference(name="bin_out", expected_width=4), SignalReference(name="rst_n", expected_width=1)],
                clock=clk_ctx, reset=rst_ctx
            ),
            # P7: Enable disabled holds gray output
            CandidateProperty(
                property_id="GRAY_P07_ENABLE_HOLD_GRAY", design_top="gray_counter", module="gray_counter",
                name="enable_hold_gray", description="Disabling enable preserves gray count",
                category=PropertyCategory.TEMPORAL, assertion_language=AssertionLanguage.SVA,
                expression="disable iff (!rst_n) !enable |=> gray_out == (gray_out)",
                signals=[SignalReference(name="enable", expected_width=1), SignalReference(name="gray_out", expected_width=4), SignalReference(name="rst_n", expected_width=1)],
                clock=clk_ctx, reset=rst_ctx
            ),
            # P8: Binary increment step
            CandidateProperty(
                property_id="GRAY_P08_BIN_INC", design_top="gray_counter", module="gray_counter",
                name="binary_step_progression", description="Active enable increments binary count by 1 mod 16",
                category=PropertyCategory.TEMPORAL, assertion_language=AssertionLanguage.SVA,
                expression="disable iff (!rst_n) enable |=> bin_out == (bin_out) + 4'd1",
                signals=[SignalReference(name="enable", expected_width=1), SignalReference(name="bin_out", expected_width=4), SignalReference(name="rst_n", expected_width=1)],
                clock=clk_ctx, reset=rst_ctx
            ),
            # P9: Reset sets bin_out to zero
            CandidateProperty(
                property_id="GRAY_P09_RESET_BIN", design_top="gray_counter", module="gray_counter",
                name="reset_clears_bin", description="Reset state enforces bin_out equals 0",
                category=PropertyCategory.SAFETY, assertion_language=AssertionLanguage.BOOLEAN,
                expression="rst_n || (bin_out == 4'b0000)",
                signals=[SignalReference(name="rst_n", expected_width=1), SignalReference(name="bin_out", expected_width=4)],
                clock=clk_ctx, reset=rst_ctx
            ),
            # P10: Reset sets gray_out to zero
            CandidateProperty(
                property_id="GRAY_P10_RESET_GRAY", design_top="gray_counter", module="gray_counter",
                name="reset_clears_gray", description="Reset state enforces gray_out equals 0",
                category=PropertyCategory.SAFETY, assertion_language=AssertionLanguage.BOOLEAN,
                expression="rst_n || (gray_out == 4'b0000)",
                signals=[SignalReference(name="rst_n", expected_width=1), SignalReference(name="gray_out", expected_width=4)],
                clock=clk_ctx, reset=rst_ctx
            ),
            # P11: Bit 2 formula: gray_out[2] == bin_out[2] ^ bin_out[3]
            CandidateProperty(
                property_id="GRAY_P11_BIT2_FORMULA", design_top="gray_counter", module="gray_counter",
                name="bit2_gray_formula", description="Second MSB equals bin[2] ^ bin[3]",
                category=PropertyCategory.INVARIANT, assertion_language=AssertionLanguage.BOOLEAN,
                expression="gray_out[2] == (bin_out[2] ^ bin_out[3])",
                signals=[SignalReference(name="gray_out", expected_width=4), SignalReference(name="bin_out", expected_width=4)],
                clock=clk_ctx, reset=rst_ctx
            ),
            # P12: Bit 0 formula: gray_out[0] == bin_out[0] ^ bin_out[1]
            CandidateProperty(
                property_id="GRAY_P12_BIT0_FORMULA", design_top="gray_counter", module="gray_counter",
                name="bit0_gray_formula", description="LSB of gray equals bin[0] ^ bin[1]",
                category=PropertyCategory.INVARIANT, assertion_language=AssertionLanguage.BOOLEAN,
                expression="gray_out[0] == (bin_out[0] ^ bin_out[1])",
                signals=[SignalReference(name="gray_out", expected_width=4), SignalReference(name="bin_out", expected_width=4)],
                clock=clk_ctx, reset=rst_ctx
            ),
        ]

        self.assertEqual(len(properties), 12)
        batch = PropertyBatch(batch_id="batch_gray_12", design_top="gray_counter", properties=properties)

        # Synthesize each property and check syntax
        for idx, prop in enumerate(properties):
            single = PropertyBatch(batch_id=f"batch_gray_{idx}", design_top="gray_counter", properties=[prop])
            synth = self.synthesizer.synthesize(design, single)
            self.assertTrue(synth.wrapper_module_name.startswith("formal_gray_counter_"))
            self.assertIn("gray_counter dut (", synth.wrapper_source_code)

        # Test Decisive Log Parsing: Induction Failure is FAIL, NOT UNKNOWN!
        induction_fail_log = (
            "SBY 10:00:00 [task] engine_0.basecase: returned pass\n"
            "SBY 10:00:01 [task] engine_0.induction: induction step failed!\n"
            "DONE (FAIL, rc=2)\n"
        )
        status, phase, vcd, _ = self.runner.parse_sby_output(induction_fail_log, "", Path("/tmp"), ProofMode.PROVE)
        self.assertEqual(status, VerificationStatus.FAIL, "Induction step failure must be FAIL, never UNKNOWN")
        self.assertEqual(phase, "step")

        # Test Decisive Log Parsing: Basecase Failure is FAIL with phase 'base'
        basecase_fail_log = (
            "SBY 10:00:00 [task] engine_0.basecase: BMC failed!\n"
            "DONE (FAIL, rc=2)\n"
        )
        status, phase, vcd, _ = self.runner.parse_sby_output(basecase_fail_log, "", Path("/tmp"), ProofMode.PROVE)
        self.assertEqual(status, VerificationStatus.FAIL)
        self.assertEqual(phase, "base")

        # Test Decisive Log Parsing: PASS
        pass_log = (
            "SBY 10:00:00 [task] engine_0: returned pass\n"
            "DONE (PASS, rc=0)\n"
        )
        status, phase, vcd, _ = self.runner.parse_sby_output(pass_log, "", Path("/tmp"), ProofMode.PROVE)
        self.assertEqual(status, VerificationStatus.PASS)

    # =========================================================================
    # 2. Flip-Flop Suite (Enable, Synchronous Reset, Asynchronous Reset)
    # =========================================================================
    def test_dff_suite_synthesis(self):
        design = DesignIR(
            top_module="dff_en",
            source_files=["dff_en.sv"],
            modules=[
                ModuleIR(
                    name="dff_en",
                    ports=[
                        PortIR(name="clk", direction="input", bit_width=1, bits=[1]),
                        PortIR(name="rst_n", direction="input", bit_width=1, bits=[2]),
                        PortIR(name="sync_clr", direction="input", bit_width=1, bits=[3]),
                        PortIR(name="en", direction="input", bit_width=1, bits=[4]),
                        PortIR(name="d", direction="input", bit_width=1, bits=[5]),
                        PortIR(name="q", direction="output", bit_width=1, bits=[6]),
                    ],
                    registers=[RegisterIR(
                        cell_name="q_reg", cell_type="",
                        clock_bits=[1], reset_bits=[2],
                        parameters={"CLK_POLARITY": "1", "SRST_POLARITY": "0"}
                    )],
                    clock_candidates=[{"name": "clk", "signal": "clk", "bits": [1]}],
                    reset_candidates=[{"name": "rst_n", "signal": "rst_n", "bits": [2], "kind": "synchronous"}],
                    summary=ModuleSummaryIR(port_count=6)
                )
            ]
        )
        clk_ctx = ClockContext(signal="clk", edge="posedge")
        rst_ctx = ResetContext(signal="rst_n", polarity="active_low", asynchronous=False)

        props = [
            # Reset Priority
            CandidateProperty(
                property_id="DFF_P1_RST", design_top="dff_en", module="dff_en",
                name="dff_reset_priority", description="Active-low reset drives q low",
                category=PropertyCategory.SAFETY, assertion_language=AssertionLanguage.BOOLEAN,
                expression="rst_n || (q == 1'b0)",
                signals=[SignalReference(name="rst_n", expected_width=1), SignalReference(name="q", expected_width=1)],
                clock=clk_ctx, reset=rst_ctx
            ),
            # Enable Sample
            CandidateProperty(
                property_id="DFF_P2_EN_SAMPLE", design_top="dff_en", module="dff_en",
                name="dff_enable_samples_d", description="Asserted enable captures d on clock edge",
                category=PropertyCategory.TEMPORAL, assertion_language=AssertionLanguage.SVA,
                expression="disable iff (!rst_n) (!sync_clr && en) |=> q == (d)",
                signals=[SignalReference(name="sync_clr", expected_width=1), SignalReference(name="en", expected_width=1), SignalReference(name="q", expected_width=1), SignalReference(name="d", expected_width=1), SignalReference(name="rst_n", expected_width=1)],
                clock=clk_ctx, reset=rst_ctx
            ),
            # Disabled Hold
            CandidateProperty(
                property_id="DFF_P3_EN_HOLD", design_top="dff_en", module="dff_en",
                name="dff_disabled_holds_q", description="Deasserted enable retains prior q",
                category=PropertyCategory.TEMPORAL, assertion_language=AssertionLanguage.SVA,
                expression="disable iff (!rst_n) (!sync_clr && !en) |=> q == (q)",
                signals=[SignalReference(name="sync_clr", expected_width=1), SignalReference(name="en", expected_width=1), SignalReference(name="q", expected_width=1), SignalReference(name="rst_n", expected_width=1)],
                clock=clk_ctx, reset=rst_ctx
            ),
        ]
        batch = PropertyBatch(batch_id="batch_dff", design_top="dff_en", properties=props)
        for p in props:
            res = self.synthesizer.synthesize(design, PropertyBatch(batch_id="b", design_top="dff_en", properties=[p]))
            self.assertIn("dff_en dut (", res.wrapper_source_code)
            self.assertTrue(len(res.wrapper_source_code) > 100)

    # =========================================================================
    # 3. FSM Suites (Traffic Light & Sequence Detector)
    # =========================================================================
    def test_fsm_traffic_light_and_sequence_detector(self):
        # 3A. Traffic Light
        tl_design = DesignIR(
            top_module="traffic_light",
            source_files=["traffic_light.sv"],
            modules=[
                ModuleIR(
                    name="traffic_light",
                    ports=[
                        PortIR(name="clk", direction="input", bit_width=1),
                        PortIR(name="rst_n", direction="input", bit_width=1),
                        PortIR(name="red", direction="output", bit_width=1),
                        PortIR(name="yellow", direction="output", bit_width=1),
                        PortIR(name="green", direction="output", bit_width=1),
                    ],
                    summary=ModuleSummaryIR(port_count=5)
                )
            ]
        )
        tl_props = [
            CandidateProperty(
                property_id="TL_MUTEX_RG", design_top="traffic_light", module="traffic_light",
                name="red_green_mutex", description="Red and Green cannot both be asserted",
                category=PropertyCategory.SAFETY, assertion_language=AssertionLanguage.BOOLEAN,
                expression="!(red && green)",
                signals=[SignalReference(name="red", expected_width=1), SignalReference(name="green", expected_width=1)],
                clock=ClockContext(signal="clk", edge="posedge")
            ),
            CandidateProperty(
                property_id="TL_MUTEX_RY", design_top="traffic_light", module="traffic_light",
                name="red_yellow_mutex", description="Red and Yellow cannot both be asserted",
                category=PropertyCategory.SAFETY, assertion_language=AssertionLanguage.BOOLEAN,
                expression="!(red && yellow)",
                signals=[SignalReference(name="red", expected_width=1), SignalReference(name="yellow", expected_width=1)],
                clock=ClockContext(signal="clk", edge="posedge")
            ),
            CandidateProperty(
                property_id="TL_AT_LEAST_ONE", design_top="traffic_light", module="traffic_light",
                name="at_least_one_active", description="At least one light is active",
                category=PropertyCategory.SAFETY, assertion_language=AssertionLanguage.BOOLEAN,
                expression="red || yellow || green",
                signals=[SignalReference(name="red", expected_width=1), SignalReference(name="yellow", expected_width=1), SignalReference(name="green", expected_width=1)],
                clock=ClockContext(signal="clk", edge="posedge")
            ),
        ]
        for p in tl_props:
            res = self.synthesizer.synthesize(tl_design, PropertyBatch(batch_id="b_tl", design_top="traffic_light", properties=[p]))
            self.assertIn("traffic_light dut (", res.wrapper_source_code)

        # 3B. Sequence Detector 1011
        seq_design = DesignIR(
            top_module="seq_detector_1011",
            source_files=["seq_detector_1011.sv"],
            modules=[
                ModuleIR(
                    name="seq_detector_1011",
                    ports=[
                        PortIR(name="clk", direction="input", bit_width=1),
                        PortIR(name="rst_n", direction="input", bit_width=1),
                        PortIR(name="data_in", direction="input", bit_width=1),
                        PortIR(name="detected", direction="output", bit_width=1),
                        PortIR(name="state", direction="output", bit_width=3),
                    ],
                    summary=ModuleSummaryIR(port_count=5)
                )
            ]
        )
        seq_props = [
            CandidateProperty(
                property_id="SEQ_DETECT_CORRELATION", design_top="seq_detector_1011", module="seq_detector_1011",
                name="detect_equals_state_1011", description="detected high if and only if state is S_1011",
                category=PropertyCategory.INVARIANT, assertion_language=AssertionLanguage.BOOLEAN,
                expression="detected == (state == 3'b100)",
                signals=[SignalReference(name="detected", expected_width=1), SignalReference(name="state", expected_width=3)],
                clock=ClockContext(signal="clk", edge="posedge")
            ),
            CandidateProperty(
                property_id="SEQ_STATE_BOUND", design_top="seq_detector_1011", module="seq_detector_1011",
                name="state_range_bound", description="state value never exceeds legal encoding 4",
                category=PropertyCategory.INVARIANT, assertion_language=AssertionLanguage.BOOLEAN,
                expression="state <= 3'd4",
                signals=[SignalReference(name="state", expected_width=3)],
                clock=ClockContext(signal="clk", edge="posedge")
            ),
        ]
        for p in seq_props:
            res = self.synthesizer.synthesize(seq_design, PropertyBatch(batch_id="b_seq", design_top="seq_detector_1011", properties=[p]))
            self.assertIn("seq_detector_1011 dut (", res.wrapper_source_code)

    # =========================================================================
    # 4. Round-Robin Arbiter Suite
    # =========================================================================
    def test_round_robin_arbiter_synthesis(self):
        arb_design = DesignIR(
            top_module="round_robin_arbiter",
            source_files=["round_robin_arbiter.sv"],
            modules=[
                ModuleIR(
                    name="round_robin_arbiter",
                    ports=[
                        PortIR(name="clk", direction="input", bit_width=1),
                        PortIR(name="rst_n", direction="input", bit_width=1),
                        PortIR(name="req", direction="input", bit_width=4),
                        PortIR(name="grant", direction="output", bit_width=4),
                    ],
                    summary=ModuleSummaryIR(port_count=4)
                )
            ]
        )
        arb_props = [
            # One-hot-zero grant mutual exclusion
            CandidateProperty(
                property_id="ARB_MUTEX", design_top="round_robin_arbiter", module="round_robin_arbiter",
                name="grant_mutex", description="At most one grant line asserted",
                category=PropertyCategory.SAFETY, assertion_language=AssertionLanguage.BOOLEAN,
                expression="grant == 4'b0000 || grant == 4'b0001 || grant == 4'b0010 || grant == 4'b0100 || grant == 4'b1000",
                signals=[SignalReference(name="grant", expected_width=4)],
                clock=ClockContext(signal="clk", edge="posedge")
            ),
            # Grant implies request
            CandidateProperty(
                property_id="ARB_LEGITIMATE_GRANT", design_top="round_robin_arbiter", module="round_robin_arbiter",
                name="grant_requires_req", description="A grant is given only to an active request",
                category=PropertyCategory.SAFETY, assertion_language=AssertionLanguage.BOOLEAN,
                expression="(grant & ~req) == 4'b0000",
                signals=[SignalReference(name="grant", expected_width=4), SignalReference(name="req", expected_width=4)],
                clock=ClockContext(signal="clk", edge="posedge")
            ),
            # Zero request implies zero grant
            CandidateProperty(
                property_id="ARB_IDLE_QUIESCENCE", design_top="round_robin_arbiter", module="round_robin_arbiter",
                name="idle_quiescence", description="No requests implies no grant",
                category=PropertyCategory.SAFETY, assertion_language=AssertionLanguage.BOOLEAN,
                expression="!(req == 4'b0000) || (grant == 4'b0000)",
                signals=[SignalReference(name="req", expected_width=4), SignalReference(name="grant", expected_width=4)],
                clock=ClockContext(signal="clk", edge="posedge")
            ),
            # Work conserving: any request implies non-zero grant
            CandidateProperty(
                property_id="ARB_WORK_CONSERVING", design_top="round_robin_arbiter", module="round_robin_arbiter",
                name="work_conserving", description="Active requests always receive a grant",
                category=PropertyCategory.TEMPORAL, assertion_language=AssertionLanguage.BOOLEAN,
                expression="!(req != 4'b0000) || (grant != 4'b0000)",
                signals=[SignalReference(name="req", expected_width=4), SignalReference(name="grant", expected_width=4)],
                clock=ClockContext(signal="clk", edge="posedge")
            ),
        ]
        for p in arb_props:
            res = self.synthesizer.synthesize(arb_design, PropertyBatch(batch_id="b_arb", design_top="round_robin_arbiter", properties=[p]))
            self.assertIn("round_robin_arbiter dut (", res.wrapper_source_code)

    # =========================================================================
    # 5. Full RISC Benchmark Suite (ALU, RegFile, Control FSM, Branch PC, Hazard)
    # =========================================================================
    def test_risc_benchmark_suite_comprehensive(self):
        # 5A. RegFile
        reg_design = DesignIR(
            top_module="risc_regfile", source_files=["risc_regfile.sv"],
            modules=[ModuleIR(name="risc_regfile", ports=[
                PortIR(name="clk", direction="input", bit_width=1),
                PortIR(name="rst_n", direction="input", bit_width=1),
                PortIR(name="we", direction="input", bit_width=1),
                PortIR(name="waddr", direction="input", bit_width=5),
                PortIR(name="wdata", direction="input", bit_width=32),
                PortIR(name="raddr1", direction="input", bit_width=5),
                PortIR(name="rdata1", direction="output", bit_width=32),
                PortIR(name="raddr2", direction="input", bit_width=5),
                PortIR(name="rdata2", direction="output", bit_width=32),
            ], summary=ModuleSummaryIR(port_count=9))]
        )
        reg_prop = CandidateProperty(
            property_id="REG_R0_ZERO", design_top="risc_regfile", module="risc_regfile",
            name="reg_x0_is_zero", description="Reading x0 always produces zero",
            category=PropertyCategory.INVARIANT, assertion_language=AssertionLanguage.BOOLEAN,
            expression="!(raddr1 == 5'b00000) || (rdata1 == 32'b0)",
            signals=[SignalReference(name="raddr1", expected_width=5), SignalReference(name="rdata1", expected_width=32)],
            clock=ClockContext(signal="clk", edge="posedge")
        )
        res = self.synthesizer.synthesize(reg_design, PropertyBatch(batch_id="b_reg", design_top="risc_regfile", properties=[reg_prop]))
        self.assertIn("assert (!(raddr1 == 5'b00000) || (rdata1 == 32'b0));", res.wrapper_source_code)

        # 5B. Control FSM
        fsm_design = DesignIR(
            top_module="risc_control_fsm", source_files=["risc_control_fsm.sv"],
            modules=[ModuleIR(name="risc_control_fsm", ports=[
                PortIR(name="clk", direction="input", bit_width=1, bits=[1]),
                PortIR(name="rst_n", direction="input", bit_width=1, bits=[2]),
                PortIR(name="opcode", direction="input", bit_width=7, bits=list(range(3, 10))),
                PortIR(name="pc_write", direction="output", bit_width=1, bits=[10]),
                PortIR(name="ir_write", direction="output", bit_width=1, bits=[11]),
                PortIR(name="reg_write", direction="output", bit_width=1, bits=[12]),
                PortIR(name="mem_read", direction="output", bit_width=1, bits=[13]),
                PortIR(name="mem_write", direction="output", bit_width=1, bits=[14]),
                PortIR(name="alu_src_a", direction="output", bit_width=1, bits=[15]),
                PortIR(name="alu_src_b", direction="output", bit_width=2, bits=[16, 17]),
                PortIR(name="alu_op", direction="output", bit_width=2, bits=[18, 19]),
                PortIR(name="state_out", direction="output", bit_width=3, bits=[20, 21, 22]),
            ],
            registers=[RegisterIR(
                cell_name="state_reg", cell_type="",
                clock_bits=[1], reset_bits=[2],
                parameters={"CLK_POLARITY": "1", "SRST_POLARITY": "0"}
            )],
            clock_candidates=[{"name": "clk", "signal": "clk", "bits": [1]}],
            reset_candidates=[{"name": "rst_n", "signal": "rst_n", "bits": [2], "kind": "synchronous"}],
            summary=ModuleSummaryIR(port_count=12))]
        )
        fsm_prop = CandidateProperty(
            property_id="FSM_FETCH_TO_DECODE", design_top="risc_control_fsm", module="risc_control_fsm",
            name="fetch_transitions_to_decode", description="S_FETCH unconditionally transitions to S_DECODE",
            category=PropertyCategory.TEMPORAL, assertion_language=AssertionLanguage.SVA,
            expression="disable iff (!rst_n) (state_out == 3'b000) |=> (state_out == 3'b001)",
            signals=[SignalReference(name="state_out", expected_width=3), SignalReference(name="rst_n", expected_width=1)],
            clock=ClockContext(signal="clk", edge="posedge"),
            reset=ResetContext(signal="rst_n", polarity="active_low", asynchronous=False)
        )
        res = self.synthesizer.synthesize(fsm_design, PropertyBatch(batch_id="b_fsm", design_top="risc_control_fsm", properties=[fsm_prop]))
        self.assertIn("risc_control_fsm dut (", res.wrapper_source_code)

        # 5C. Branch PC Unit
        pc_design = DesignIR(
            top_module="risc_branch_pc", source_files=["risc_branch_pc.sv"],
            modules=[ModuleIR(name="risc_branch_pc", ports=[
                PortIR(name="clk", direction="input", bit_width=1),
                PortIR(name="rst_n", direction="input", bit_width=1),
                PortIR(name="pc_enable", direction="input", bit_width=1),
                PortIR(name="imm", direction="input", bit_width=32),
                PortIR(name="branch_type", direction="input", bit_width=3),
                PortIR(name="is_branch", direction="input", bit_width=1),
                PortIR(name="is_jump", direction="input", bit_width=1),
                PortIR(name="jump_target", direction="input", bit_width=32),
                PortIR(name="zero_flag", direction="input", bit_width=1),
                PortIR(name="less_flag", direction="input", bit_width=1),
                PortIR(name="pc", direction="output", bit_width=32),
                PortIR(name="pc_plus_4", direction="output", bit_width=32),
                PortIR(name="branch_target", direction="output", bit_width=32),
                PortIR(name="take_branch", direction="output", bit_width=1),
            ], summary=ModuleSummaryIR(port_count=14))]
        )
        pc_prop = CandidateProperty(
            property_id="PC_INCREMENT", design_top="risc_branch_pc", module="risc_branch_pc",
            name="pc_plus_4_invariant", description="pc_plus_4 is always pc + 4",
            category=PropertyCategory.INVARIANT, assertion_language=AssertionLanguage.BOOLEAN,
            expression="pc_plus_4 == pc + 32'd4",
            signals=[SignalReference(name="pc_plus_4", expected_width=32), SignalReference(name="pc", expected_width=32)],
            clock=ClockContext(signal="clk", edge="posedge")
        )
        res = self.synthesizer.synthesize(pc_design, PropertyBatch(batch_id="b_pc", design_top="risc_branch_pc", properties=[pc_prop]))
        self.assertIn("pc_plus_4 == pc + 32'd4", res.wrapper_source_code)

        # 5D. Hazard Unit
        hz_design = DesignIR(
            top_module="risc_hazard", source_files=["risc_hazard.sv"],
            modules=[ModuleIR(name="risc_hazard", ports=[
                PortIR(name="id_ex_rs1", direction="input", bit_width=5),
                PortIR(name="id_ex_rs2", direction="input", bit_width=5),
                PortIR(name="ex_mem_rd", direction="input", bit_width=5),
                PortIR(name="ex_mem_reg_write", direction="input", bit_width=1),
                PortIR(name="mem_wb_rd", direction="input", bit_width=5),
                PortIR(name="mem_wb_reg_write", direction="input", bit_width=1),
                PortIR(name="if_id_rs1", direction="input", bit_width=5),
                PortIR(name="if_id_rs2", direction="input", bit_width=5),
                PortIR(name="id_ex_rd", direction="input", bit_width=5),
                PortIR(name="id_ex_mem_read", direction="input", bit_width=1),
                PortIR(name="forward_a", direction="output", bit_width=2),
                PortIR(name="forward_b", direction="output", bit_width=2),
                PortIR(name="stall", direction="output", bit_width=1),
                PortIR(name="flush", direction="output", bit_width=1),
            ], summary=ModuleSummaryIR(port_count=14))]
        )
        hz_prop = CandidateProperty(
            property_id="HAZARD_FLUSH_EQUALS_STALL", design_top="risc_hazard", module="risc_hazard",
            name="flush_equals_stall", description="Pipeline flush is directly tied to stall assertion",
            category=PropertyCategory.INVARIANT, assertion_language=AssertionLanguage.BOOLEAN,
            expression="flush == stall",
            signals=[SignalReference(name="flush", expected_width=1), SignalReference(name="stall", expected_width=1)],
            clock=None
        )
        res = self.synthesizer.synthesize(hz_design, PropertyBatch(batch_id="b_hz", design_top="risc_hazard", properties=[hz_prop]))
        self.assertIn("assert (flush == stall);", res.wrapper_source_code)


if __name__ == "__main__":
    unittest.main()
