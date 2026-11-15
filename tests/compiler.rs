use veximc::parse;

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
