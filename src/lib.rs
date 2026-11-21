use std::{
    collections::{BTreeMap, VecDeque},
    fmt,
    fmt::Write,
};

#[derive(Debug)]
pub struct Diagnostic {
    pub line: usize,
    pub message: String,
}

impl fmt::Display for Diagnostic {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.line, self.message)
    }
}

#[derive(Clone, Copy, PartialEq)]
enum Direction {
    Input,
    Output,
    Wire,
}

struct Signal {
    name: String,
    width: u8,
    direction: Direction,
    line: usize,
}

enum Operation {
    Constant(u64),
    Copy(usize),
    ZeroExtend(usize),
    Slice(usize, u8, u8),
    Concat(usize, usize),
    Binary(&'static str, usize, usize),
    Mux(usize, usize, usize),
    Read {
        memory: usize,
        address: usize,
    },
    Register {
        clock: usize,
        reset: usize,
        data: usize,
        reset_value: u64,
    },
}

impl Operation {
    fn combinational_inputs(&self) -> Vec<usize> {
        match *self {
            Self::Copy(a)
            | Self::ZeroExtend(a)
            | Self::Slice(a, _, _)
            | Self::Read { address: a, .. } => vec![a],
            Self::Binary(_, a, b) | Self::Concat(a, b) => vec![a, b],
            Self::Mux(select, a, b) => vec![select, a, b],
            Self::Constant(_) | Self::Register { .. } => vec![],
        }
    }
}

struct Driver {
    operation: Operation,
    line: usize,
}

struct Memory {
    name: String,
    width: u8,
    depth: u32,
    line: usize,
    write: Option<MemoryWrite>,
}

impl Memory {
    fn address_width(&self) -> u8 {
        (u32::BITS - (self.depth - 1).leading_zeros()).max(1) as u8
    }
}

fn memory_bound(memory: &Memory, address: &str) -> Option<String> {
    let width = memory.address_width();
    (u64::from(memory.depth) < (1_u64 << width))
        .then(|| format!("{address}< {width}'d{}", memory.depth))
}

struct MemoryWrite {
    clock: usize,
    enable: usize,
    address: usize,
    data: usize,
    line: usize,
}

/// Validated Vexim hardware IR. Names are resolved to signal indices.
pub struct Module {
    name: String,
    signals: Vec<Signal>,
    drivers: Vec<Option<Driver>>,
    memories: Vec<Memory>,
}

fn identifier(name: &str) -> bool {
    let mut chars = name.bytes();
    chars
        .next()
        .is_some_and(|c| c.is_ascii_alphabetic() || c == b'_')
        && chars.all(|c| c.is_ascii_alphanumeric() || c == b'_')
}

fn decimal(token: &str) -> Option<u64> {
    if token.is_empty() || !token.bytes().all(|c| c.is_ascii_digit()) {
        return None;
    }
    token.parse().ok()
}

/// Parse and validate a single module.
pub fn parse(source: &str) -> Result<Module, Diagnostic> {
    parse_with_parameters(source, &BTreeMap::new())
}

/// Parse and validate a module with compile-time parameter overrides.
pub fn parse_with_parameters(
    source: &str,
    overrides: &BTreeMap<String, u64>,
) -> Result<Module, Diagnostic> {
    let mut name = None;
    let mut signals = Vec::new();
    let mut names = BTreeMap::new();
    let mut parameters = BTreeMap::new();
    let mut memory_names = BTreeMap::new();
    let mut memories: Vec<Memory> = Vec::new();
    let mut statements = Vec::new();
    let mut ended = false;
    let mut last_line = 1;
    for (index, text) in source.lines().enumerate() {
        let line = index + 1;
        last_line = line;
        let tokens: Vec<_> = text
            .split('#')
            .next()
            .unwrap_or("")
            .split_whitespace()
            .collect();
        if tokens.is_empty() {
            continue;
        }
        let error = |message: &str| Diagnostic {
            line,
            message: message.into(),
        };
        if ended {
            return Err(error("unexpected content after end"));
        }
        if name.is_none() {
            match tokens.as_slice() {
                ["module", id] if identifier(id) => name = Some((*id).to_owned()),
                _ => return Err(error("expected module NAME")),
            }
            continue;
        }
        let unique_name = |id: &str| {
            if !identifier(id) {
                return Err(error("invalid declaration name"));
            }
            if names.contains_key(id)
                || parameters.contains_key(id)
                || memory_names.contains_key(id)
            {
                return Err(error("duplicate declaration name"));
            }
            Ok(())
        };
        let resolve = |token: &str| decimal(token).or_else(|| parameters.get(token).copied());
        let width = |ty: &str| {
            ty.strip_prefix('u')
                .and_then(resolve)
                .filter(|n| (1..=64).contains(n))
                .map(|n| n as u8)
                .ok_or_else(|| error("expected unsigned width u1 through u64 or uPARAM"))
        };
        match tokens.as_slice() {
            ["param", id, default] => {
                unique_name(id)?;
                let default = decimal(default)
                    .ok_or_else(|| error("expected a decimal parameter default"))?;
                parameters.insert(*id, overrides.get(*id).copied().unwrap_or(default));
            }
            ["mem", id, ty, depth] => {
                unique_name(id)?;
                let depth = resolve(depth)
                    .filter(|n| (1..=2_147_483_647).contains(n))
                    .ok_or_else(|| error("memory depth must be between 1 and 2147483647"))?;
                memory_names.insert(*id, memories.len());
                memories.push(Memory {
                    name: (*id).into(),
                    width: width(ty)?,
                    depth: depth as u32,
                    line,
                    write: None,
                });
            }
            [kind @ ("input" | "output" | "wire"), id, ty] => {
                unique_name(id)?;
                let width = width(ty)?;
                let direction = match *kind {
                    "input" => Direction::Input,
                    "output" => Direction::Output,
                    _ => Direction::Wire,
                };
                names.insert(*id, signals.len());
                signals.push(Signal {
                    name: (*id).into(),
                    width,
                    direction,
                    line,
                });
            }
            ["comb" | "sync" | "write", ..] => statements.push((line, tokens)),
            ["end"] => ended = true,
            _ => return Err(error("expected a declaration, driver, or end")),
        }
    }
    if !ended {
        return Err(Diagnostic {
            line: last_line,
            message: "expected module ending in end".into(),
        });
    }
    if let Some(unknown) = overrides
        .keys()
        .find(|name| !parameters.contains_key(name.as_str()))
    {
        return Err(Diagnostic {
            line: 1,
            message: format!("unknown parameter {unknown}"),
        });
    }
    let mut drivers: Vec<Option<Driver>> = (0..signals.len()).map(|_| None).collect();
    for (line, tokens) in statements {
        let error = |message: &str| Diagnostic {
            line,
            message: message.into(),
        };
        let lookup = |id: &str| {
            names
                .get(id)
                .copied()
                .ok_or_else(|| error(&format!("unknown signal {id}")))
        };
        let matching = |id: &str, expected| {
            let index = lookup(id)?;
            if signals[index].width != expected {
                return Err(error(&format!(
                    "{id} has width u{}, expected u{expected}",
                    signals[index].width
                )));
            }
            Ok(index)
        };
        let memory_index = |id: &str| {
            memory_names
                .get(id)
                .copied()
                .ok_or_else(|| error(&format!("unknown memory {id}")))
        };
        if let ["write", memory, clock, enable, address, data] = tokens.as_slice() {
            let memory = &mut memories[memory_index(memory)?];
            if memory.write.is_some() {
                return Err(error("memory already has a write port"));
            }
            let clock = matching(clock, 1)?;
            if signals[clock].direction != Direction::Input {
                return Err(error("memory clock must be a module input"));
            }
            memory.write = Some(MemoryWrite {
                clock,
                enable: matching(enable, 1)?,
                address: matching(address, memory.address_width())?,
                data: matching(data, memory.width)?,
                line,
            });
            continue;
        }
        if tokens[0] == "write" {
            return Err(error("expected write MEMORY CLOCK ENABLE ADDRESS DATA"));
        }
        let Some(target) = tokens.get(1) else {
            return Err(error("expected a destination"));
        };
        let target = lookup(target)?;
        if signals[target].direction == Direction::Input || drivers[target].is_some() {
            return Err(error("destination is an input or already has a driver"));
        }
        let width = signals[target].width;
        let literal = |token| {
            decimal(token)
                .filter(|&value| width == 64 || value < (1_u64 << width))
                .ok_or_else(|| error(&format!("expected a decimal literal that fits u{width}")))
        };
        let operation = match tokens.as_slice() {
            ["comb", _, "read", memory, address] => {
                let memory = memory_index(memory)?;
                let declaration = &memories[memory];
                if declaration.width != width {
                    return Err(error("read destination width must match memory word width"));
                }
                Operation::Read {
                    memory,
                    address: matching(address, declaration.address_width())?,
                }
            }
            ["comb", _, "const", value] => Operation::Constant(literal(value)?),
            ["comb", _, "copy", a] => Operation::Copy(matching(a, width)?),
            ["comb", _, "zext", a] => {
                let index = lookup(a)?;
                if signals[index].width >= width {
                    return Err(error("zext requires a wider destination"));
                }
                Operation::ZeroExtend(index)
            }
            ["comb", _, "slice", source, msb, lsb] => {
                let source = lookup(source)?;
                let index = |token| {
                    decimal(token)
                        .filter(|&bit| bit < u64::from(signals[source].width))
                        .map(|bit| bit as u8)
                        .ok_or_else(|| error("slice index outside source width"))
                };
                let (msb, lsb) = (index(msb)?, index(lsb)?);
                if msb < lsb || msb - lsb + 1 != width {
                    return Err(error(
                        "slice bounds must be descending and match destination width",
                    ));
                }
                Operation::Slice(source, msb, lsb)
            }
            ["comb", _, "concat", a, b] => {
                let (a, b) = (lookup(a)?, lookup(b)?);
                if u16::from(signals[a].width) + u16::from(signals[b].width) != u16::from(width) {
                    return Err(error("concatenation must match destination width"));
                }
                Operation::Concat(a, b)
            }
            ["comb", _, op @ ("eq" | "ne"), a, b] => {
                if width != 1 {
                    return Err(error("comparison requires a u1 destination"));
                }
                let a = lookup(a)?;
                let b = matching(b, signals[a].width)?;
                Operation::Binary(if *op == "eq" { "==" } else { "!=" }, a, b)
            }
            ["comb", _, "mux", select, a, b] => Operation::Mux(
                matching(select, 1)?,
                matching(a, width)?,
                matching(b, width)?,
            ),
            ["comb", _, op, a, b] => {
                let symbol = match *op {
                    "add" => "+",
                    "sub" => "-",
                    "mul" => "*",
                    "and" => "&",
                    "or" => "|",
                    "xor" => "^",
                    _ => return Err(error("unknown binary operation")),
                };
                Operation::Binary(symbol, matching(a, width)?, matching(b, width)?)
            }
            ["sync", _, clock, reset, data, rest @ ..] if rest.len() <= 1 => {
                let clock = matching(clock, 1)?;
                let reset = matching(reset, 1)?;
                if signals[clock].direction != Direction::Input
                    || signals[reset].direction != Direction::Input
                {
                    return Err(error("clock and reset must be module inputs"));
                }
                Operation::Register {
                    clock,
                    reset,
                    data: matching(data, width)?,
                    reset_value: rest
                        .first()
                        .map(|value| literal(value))
                        .transpose()?
                        .unwrap_or(0),
                }
            }
            _ => return Err(error("invalid driver syntax")),
        };
        drivers[target] = Some(Driver { operation, line });
    }
    if let Some(memory) = memories.iter().find(|memory| memory.write.is_none()) {
        return Err(Diagnostic {
            line: memory.line,
            message: format!("memory {} has no write port", memory.name),
        });
    }
    for (signal, driver) in signals.iter().zip(&drivers) {
        if signal.direction != Direction::Input && driver.is_none() {
            return Err(Diagnostic {
                line: signal.line,
                message: format!("undriven signal {}", signal.name),
            });
        }
    }
    let module = Module {
        name: name.expect("module header before end"),
        signals,
        drivers,
        memories,
    };
    module.combinational_order()?;
    Ok(module)
}

impl Module {
    fn live_signals(&self) -> Vec<bool> {
        let mut live = vec![false; self.signals.len()];
        let mut pending: Vec<_> = self
            .signals
            .iter()
            .enumerate()
            .filter_map(|(index, signal)| (signal.direction == Direction::Output).then_some(index))
            .collect();
        // Keep memory writes and their inputs, including stores that affect later reads.
        for memory in &self.memories {
            if let Some(write) = &memory.write {
                pending.extend([write.clock, write.enable, write.address, write.data]);
            }
        }
        while let Some(index) = pending.pop() {
            if live[index] {
                continue;
            }
            live[index] = true;
            if let Some(driver) = &self.drivers[index] {
                match driver.operation {
                    Operation::Register {
                        clock, reset, data, ..
                    } => {
                        pending.extend([clock, reset, data]);
                    }
                    _ => pending.extend(driver.operation.combinational_inputs()),
                }
            }
        }
        live
    }
    fn combinational_order(&self) -> Result<Vec<usize>, Diagnostic> {
        let mut dependents = vec![Vec::new(); self.signals.len()];
        let mut pending = vec![0; self.signals.len()];
        for (target, driver) in self.drivers.iter().enumerate() {
            if let Some(driver) = driver {
                for input in driver.operation.combinational_inputs() {
                    dependents[input].push(target);
                    pending[target] += 1;
                }
            }
        }
        let mut queue: VecDeque<_> = (0..pending.len()).filter(|&i| pending[i] == 0).collect();
        let mut order = Vec::with_capacity(self.signals.len());
        while let Some(signal) = queue.pop_front() {
            order.push(signal);
            for &dependent in &dependents[signal] {
                pending[dependent] -= 1;
                if pending[dependent] == 0 {
                    queue.push_back(dependent);
                }
            }
        }
        if let Some(index) = pending.iter().position(|&count| count != 0) {
            let signal = &self.signals[index];
            let line = self.drivers[index]
                .as_ref()
                .map_or(signal.line, |driver| driver.line);
            return Err(Diagnostic {
                line,
                message: format!("combinational cycle feeds {}", signal.name),
            });
        }
        Ok(order)
    }

    /// Fold combinational constants before emission. Stateful inputs remain unknown.
    pub fn propagate_constants(&mut self) {
        let order = self
            .combinational_order()
            .expect("validated combinational graph");
        let mut constants = vec![None; self.signals.len()];
        for index in order {
            let Some(driver) = &mut self.drivers[index] else {
                continue;
            };
            let width = self.signals[index].width;
            let mask = u64::MAX >> (64 - width);
            let known = |signal: usize| constants[signal];
            if let Operation::Mux(select, yes, no) = driver.operation {
                if let Some(value) = known(select) {
                    driver.operation = Operation::Copy(if value == 0 { no } else { yes });
                }
            }
            let value = match driver.operation {
                Operation::Constant(value) => Some(value),
                Operation::Copy(a) | Operation::ZeroExtend(a) => known(a),
                Operation::Slice(a, _, low) => known(a).map(|value| value >> low),
                Operation::Concat(a, b) => known(a)
                    .zip(known(b))
                    .map(|(high, low)| (high << self.signals[b].width) | low),
                Operation::Binary(op, a, b) => match (op, known(a), known(b)) {
                    ("&", Some(0), _) | ("&", _, Some(0)) => Some(0),
                    ("|", Some(a), _) if a == mask => Some(mask),
                    ("|", _, Some(b)) if b == mask => Some(mask),
                    (op, Some(a), Some(b)) => Some(match op {
                        "+" => a.wrapping_add(b),
                        "-" => a.wrapping_sub(b),
                        "*" => a.wrapping_mul(b),
                        "&" => a & b,
                        "|" => a | b,
                        "^" => a ^ b,
                        "==" => u64::from(a == b),
                        "!=" => u64::from(a != b),
                        _ => unreachable!("validated binary operation"),
                    }),
                    _ => None,
                },
                Operation::Read { memory, address } => known(address)
                    .filter(|&address| address >= u64::from(self.memories[memory].depth))
                    .map(|_| 0),
                Operation::Register { .. } | Operation::Mux(..) => None,
            };
            if let Some(value) = value {
                let value = value & mask;
                constants[index] = Some(value);
                driver.operation = Operation::Constant(value);
            }
        }
    }

    /// Emit synthesizable SystemVerilog with a source line comment for each driver.
    pub fn system_verilog(&self) -> String {
        let live = self.live_signals();
        fn escaped(name: &str) -> String {
            format!("\\{name} ")
        }
        fn range(width: u8) -> String {
            if width == 1 {
                String::new()
            } else {
                format!("[{}:0] ", width - 1)
            }
        }
        let signal = |i: usize| escaped(&self.signals[i].name);
        let ports: Vec<_> = self
            .signals
            .iter()
            .filter_map(|s| {
                let direction = match s.direction {
                    Direction::Input => "input",
                    Direction::Output => "output",
                    Direction::Wire => return None,
                };
                Some(format!(
                    "  {direction} logic {}{}",
                    range(s.width),
                    escaped(&s.name)
                ))
            })
            .collect();
        let mut out = format!(
            "module {}(\n{}\n);\n",
            escaped(&self.name),
            ports.join(",\n")
        );
        for s in
            self.signals.iter().enumerate().filter_map(|(index, s)| {
                (s.direction == Direction::Wire && live[index]).then_some(s)
            })
        {
            writeln!(out, "  logic {}{};", range(s.width), escaped(&s.name)).unwrap();
        }
        for memory in &self.memories {
            let name = escaped(&memory.name);
            writeln!(
                out,
                "  logic {}{name}[0:{}];",
                range(memory.width),
                memory.depth - 1
            )
            .unwrap();
            let write = memory.write.as_ref().expect("validated memory write port");
            let address = signal(write.address);
            let enable = signal(write.enable);
            let mut condition = enable.clone();
            if let Some(bound) = memory_bound(memory, &address) {
                condition = format!("{enable}&& ({bound})");
            }
            writeln!(out,
                "  // Vexim line {}\n  always_ff @(posedge {}) begin\n    if ({condition}) {name}[{address}] <= {};\n  end",
                write.line, signal(write.clock), signal(write.data)).unwrap();
        }
        for (i, driver) in self.drivers.iter().enumerate() {
            if !live[i] {
                continue;
            }
            let Some(driver) = driver else {
                continue;
            };
            let target = signal(i);
            let width = self.signals[i].width;
            writeln!(out, "  // Vexim line {}", driver.line).unwrap();
            match driver.operation {
                Operation::Read { memory, address } => {
                    let memory = &self.memories[memory];
                    let address = signal(address);
                    let word = format!("{}[{address}]", escaped(&memory.name));
                    if let Some(bound) = memory_bound(memory, &address) {
                        writeln!(out, "  assign {target}= ({bound}) ? {word} : {width}'d0;")
                    } else {
                        writeln!(out, "  assign {target}= {word};")
                    }
                }
                Operation::Constant(value) => writeln!(out, "  assign {target}= {width}'d{value};"),
                Operation::Copy(a) => writeln!(out, "  assign {target}= {};", signal(a)),
                Operation::Slice(a, msb, lsb) => {
                    if self.signals[a].width == 1 {
                        writeln!(out, "  assign {target}= {};", signal(a))
                    } else if msb == lsb {
                        writeln!(out, "  assign {target}= {}[{msb}];", signal(a))
                    } else {
                        writeln!(out, "  assign {target}= {}[{msb}:{lsb}];", signal(a))
                    }
                }
                Operation::Concat(a, b) => writeln!(out, "  assign {target}= {{{}, {}}};", signal(a), signal(b)),
                Operation::Mux(select, a, b) => writeln!(out, "  assign {target}= {}? {}: {};", signal(select), signal(a), signal(b)),
                Operation::ZeroExtend(a) => {
                    let gap = self.signals[i].width - self.signals[a].width;
                    writeln!(out, "  assign {target}= {{{gap}'d0, {}}};", signal(a))
                }
                Operation::Binary(op, a, b) => writeln!(out, "  assign {target}= {}{op} {};", signal(a), signal(b)),
                Operation::Register { clock, reset, data, reset_value } => writeln!(out,
                    "  always_ff @(posedge {}) begin\n    if ({}) {target}<= {width}'d{reset_value};\n    else {target}<= {};\n  end",
                    signal(clock), signal(reset), signal(data)),
            }.unwrap();
        }
        out.push_str("endmodule\n");
        out
    }
}
