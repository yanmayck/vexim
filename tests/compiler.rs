use veximc::parse;

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
