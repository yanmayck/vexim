/// Apply Yosys's SAT-based sharing to the flattened, elaborated design.
pub(crate) const RESOURCE_SHARING: &str = "opt_expr; opt_clean; share -aggressive; opt_clean; ";
