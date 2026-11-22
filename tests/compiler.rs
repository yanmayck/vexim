use veximc::parse;

const ROM: &str = "module lookup\ninput clk u1\ninput addr u2\noutput q u8\nrom words u8 99 124 119\nrom_read q words clk addr\nend";

#[test]
fn synchronous_rom_is_zero_padded_and_unused_tables_are_removed() {
    let source = ROM.replace("end", "rom unused u8 0 1 2\nend");
    let rtl = parse(&source).unwrap().system_verilog();
    assert!(rtl.contains("\\words [0:3]"));
    assert!(rtl.contains("\\words [3] = 8'd0"));
    assert!(rtl.contains("always_ff @(posedge \\clk ) \\q <= \\words [\\addr ];"));
    assert!(!rtl.contains("unused"));
}

#[test]
fn synchronous_rom_rejects_invalid_values_ports_and_writes() {
    for (old, new, message) in [
        ("99 124 119", "99 256 119", "fits u8"),
        ("input addr u2", "input addr u3", "expected u2"),
        ("output q u8", "output q u16", "destination width"),
        (
            "rom_read q words clk addr",
            "comb q read words addr",
            "synchronous rom_read",
        ),
        (
            "\nend",
            "\nwrite words clk clk addr q\nend",
            "cannot target a ROM",
        ),
    ] {
        let error = parse(&ROM.replace(old, new)).err().expect(new);
        assert!(error.message.contains(message), "{error}");
    }
}

const RAM: &str = include_str!("../examples/ram.vxm");

#[test]
fn emission_removes_dead_chains_and_keeps_registered_state() {
    let source = "module demo\ninput clk u1\ninput rst u1\ninput a u8\noutput q u8\nwire dead u8\nwire chain u8\ncomb dead const 7\ncomb chain copy dead\nsync q clk rst a\nend";
    let sv = parse(source).unwrap().system_verilog();
    assert!(!sv.contains("\\dead "));
    assert!(!sv.contains("\\chain "));
    assert!(sv.contains("always_ff"));
    assert!(sv.contains("\\a "));
    let ram = parse(RAM).unwrap().system_verilog();
    assert!(ram.contains("\\din "));
    assert!(ram.contains("\\wr_addr "));
    assert!(ram.contains("always_ff"));
}

#[test]
fn rejects_invalid_memory_ports_and_cycles() {
    for (from, to, expected) in [
        (
            "input wr_addr uADDR_BITS",
            "input wr_addr u3",
            "expected u4",
        ),
        ("output dout uWORD_BITS", "output dout u4", "word width"),
        (
            "write words clk we wr_addr din",
            "write words clk we wr_addr din\nwrite words clk we wr_addr din",
            "already has a write port",
        ),
        ("write words clk we wr_addr din", "", "no write port"),
        (
            "comb dout read words rd_addr",
            "wire loop_addr u4\ncomb dout read words loop_addr\ncomb loop_addr slice dout 3 0",
            "combinational cycle",
        ),
    ] {
        let error = parse(&RAM.replace(from, to)).err().expect(to);
        assert!(error.message.contains(expected), "{error}");
    }
}

#[test]
fn validates_parameter_overrides_before_emission() {
    use std::collections::BTreeMap;
    use veximc::parse_with_parameters;
    for (name, value, expected) in [
        ("DEPTH", 0, "memory depth"),
        ("DEPTH", 32, "expected u5"),
        ("WORD_BITS", 65, "unsigned width"),
        ("MISSING", 1, "unknown parameter"),
    ] {
        let overrides = BTreeMap::from([(name.to_owned(), value)]);
        let error = parse_with_parameters(RAM, &overrides)
            .err()
            .expect(expected);
        assert!(error.message.contains(expected), "{error}");
    }
    assert!(parse_with_parameters(
        RAM,
        &BTreeMap::from([("DEPTH".to_owned(), 32), ("ADDR_BITS".to_owned(), 5)])
    )
    .is_ok());
}

#[test]
fn rejects_implicit_widening() {
    let source = "module demo\ninput a u8\noutput b u9\ncomb b copy a\nend";
    let error = parse(source).err().expect("width error");
    assert_eq!(error.line, 4);
    assert!(error.message.contains("expected u9"));
}

#[test]
fn rejects_combinational_cycle_and_accepts_registered_feedback() {
    let looped = "module demo\ninput clk u1\ninput rst u1\noutput a u1\nwire b u1\ncomb a copy b\ncomb b copy a\nend";
    let error = parse(looped).err().expect("cycle error");
    assert!(error.message.contains("cycle"));
    let registered = looped.replace("comb a copy b", "sync a clk rst b");
    assert!(parse(&registered).is_ok());
}

#[test]
fn rejects_bad_operation_widths_and_bounds() {
    for (statement, diagnostic) in [
        ("comb y const 16", "fits u4"),
        ("comb y slice a 4 1", "outside source width"),
        ("comb y slice a 0 3", "descending"),
        ("comb y slice a 2 0", "destination width"),
        ("comb y concat a a", "destination width"),
        ("comb y eq a a", "u1 destination"),
        ("comb y mux a a a", "expected u1"),
        ("comb y mux sel sel a", "expected u4"),
        ("sync y sel sel a 16", "fits u4"),
    ] {
        let source =
            format!("module demo\ninput a u4\ninput sel u1\noutput y u4\n{statement}\nend");
        let error = parse(&source).err().expect(statement);
        assert_eq!(error.line, 5, "{statement}");
        assert!(error.message.contains(diagnostic), "{statement}: {error}");
    }
}

#[test]
fn mux_selector_participates_in_cycle_detection() {
    let source = "module demo\ninput a u1\noutput y u1\ncomb y mux y a a\nend";
    let error = parse(source).err().expect("cycle through mux selector");
    assert_eq!(error.line, 4);
    assert!(error.message.contains("cycle"));
}

#[test]
fn area_pass_folds_constants_and_drops_unselected_logic() {
    let source = r#"module fold
input clk u1
input rst u1
input input_value u64
output always_zero u64
output wrapped u64
output registered u64
wire zero u1
wire one64 u64
wire max u64
wire dead u64
wire inactive u64
comb zero const 0
comb one64 const 1
comb max const 18446744073709551615
comb dead mul input_value input_value
comb inactive and input_value wrapped
comb wrapped add max one64
comb always_zero mux zero dead inactive
sync registered clk rst input_value
end"#;
    let mut module = parse(source).unwrap();
    assert!(module.system_verilog().contains("\\dead "));
    module.propagate_constants();
    let sv = module.system_verilog();
    assert!(!sv.contains("\\dead "));
    assert!(!sv.contains("\\inactive "));
    assert!(sv.contains("assign \\always_zero = 64'd0;"));
    assert!(sv.contains("assign \\wrapped = 64'd0;"));
    assert!(sv.contains("always_ff"));
}

#[test]
fn operator_sharing_respects_other_consumers_and_subtraction_order() {
    let source = "module share\ninput choose u1\ninput a u32\ninput b u32\ninput c u32\noutput result u32\nwire left u32\nwire right u32\ncomb left sub a c\ncomb right sub b c\ncomb result mux choose left right\nend";
    let emit = |source: &str| {
        let mut module = parse(source).unwrap();
        module.share_operators();
        module.system_verilog()
    };
    let shared = emit(source);
    assert!(shared.contains("(\\choose ? \\a : \\b )- \\c "));
    assert!(!shared.contains("\\left "));
    let reversed = emit(&source.replace("sub b c", "sub c b"));
    assert!(reversed.contains("\\left "));
    assert!(reversed.contains("\\right "));
    let with_other_use = emit(&source.replace("wire left u32", "output left u32"));
    assert!(with_other_use.contains("\\right "));
    let comparisons = source
        .replace("output result u32", "output result u1")
        .replace("wire left u32", "wire left u1")
        .replace("wire right u32", "wire right u1")
        .replace("sub a c", "eq c a")
        .replace("sub b c", "eq b c");
    assert!(emit(&comparisons).contains("(\\choose ? \\a : \\b )== \\c "));
}

#[test]
fn narrowing_preserves_port_widths_and_full_range_feedback() {
    let source = r#"module narrow
input clk u1
input rst u1
input a u8
input b u8
output sum u32
output registered u32
output count u32
wire wide_a u32
wire wide_b u32
wire one u32
wire next_count u32
comb wide_a zext a
comb wide_b zext b
comb sum add wide_a wide_b
sync registered clk rst sum
comb one const 1
comb next_count add count one
sync count clk rst next_count
end"#;
    let mut module = parse(source).unwrap();
    module.narrow_widths();
    let sv = module.system_verilog();
    assert!(sv.contains("output logic [31:0] \\registered "));
    assert!(sv.contains("logic [8:0] \\vexim$reg"));
    assert!(sv.contains("logic [8:0] \\vexim$arith"));
    assert!(sv.contains("\\count <= 32'd0;"));
}
