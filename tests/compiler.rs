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
