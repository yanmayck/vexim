//! Elaborate structural repetition before ordinary Vexim validation.

use super::{decimal, identifier, Diagnostic};
use std::collections::BTreeMap;

const MAX_LINES: usize = 100_000;
const MAX_DEPTH: usize = 16;

type Line = (usize, String);

fn error(line: usize, message: &str) -> Diagnostic {
    Diagnostic {
        line,
        message: message.into(),
    }
}

fn interpolate(
    text: &str,
    line: usize,
    indices: &BTreeMap<String, u64>,
) -> Result<String, Diagnostic> {
    let mut output = String::new();
    let mut rest = text;
    while let Some((prefix, substitution)) = rest.split_once("${") {
        output.push_str(prefix);
        let (key, tail) = substitution
            .split_once('}')
            .ok_or_else(|| error(line, "unclosed generation index"))?;
        let (name, add) = if let Some((name, offset)) = key.split_once('+') {
            (
                name,
                decimal(offset).ok_or_else(|| error(line, "expected a decimal index offset"))?,
            )
        } else {
            (key, 0)
        };
        let index = indices
            .get(name)
            .ok_or_else(|| error(line, "unknown generation index"))?;
        let value = index
            .checked_add(add)
            .ok_or_else(|| error(line, "generation index overflow"))?;
        output.push_str(&value.to_string());
        rest = tail;
    }
    output.push_str(rest);
    Ok(output)
}

fn interpolate_parameters(
    text: &str,
    line: usize,
    parameters: &BTreeMap<String, u64>,
) -> Result<String, Diagnostic> {
    let mut output = String::new();
    let mut rest = text;
    while let Some((prefix, substitution)) = rest.split_once("$(") {
        output.push_str(prefix);
        let (name, tail) = substitution
            .split_once(')')
            .ok_or_else(|| error(line, "unclosed generation parameter"))?;
        let value = parameters
            .get(name)
            .ok_or_else(|| error(line, "unknown generation parameter"))?;
        output.push_str(&value.to_string());
        rest = tail;
    }
    output.push_str(rest);
    Ok(output)
}

struct Generator<'a> {
    overrides: &'a BTreeMap<String, u64>,
    parameters: BTreeMap<String, u64>,
    indices: BTreeMap<String, u64>,
    output: Vec<Line>,
    steps: usize,
}

impl Generator<'_> {
    fn expand(&mut self, mut lines: &[(usize, &str)]) -> Result<(), Diagnostic> {
        while let Some((&(line, text), rest)) = lines.split_first() {
            let fields: Vec<_> = text.split_whitespace().collect();
            lines = rest;
            match fields.as_slice() {
                ["generate", name, count] if identifier(name) => {
                    if self.indices.contains_key(*name) || self.indices.len() >= MAX_DEPTH {
                        return Err(error(
                            line,
                            "duplicate generation index or nesting too deep",
                        ));
                    }
                    let limit = decimal(count)
                        .or_else(|| self.parameters.get(*count).copied())
                        .filter(|n| (1..=1024).contains(n))
                        .ok_or_else(|| {
                            error(line, "generation count must be between 1 and 1024")
                        })?;
                    let mut depth = 1;
                    let end = lines
                        .iter()
                        .position(|&(_, member)| {
                            match member.split_whitespace().next() {
                                Some("generate") => depth += 1,
                                Some("endgenerate") => depth -= 1,
                                _ => {}
                            }
                            depth == 0
                        })
                        .ok_or_else(|| error(line, "missing endgenerate"))?;
                    if lines[end].1.trim() != "endgenerate" {
                        return Err(error(lines[end].0, "expected endgenerate"));
                    }
                    for index in 0..limit {
                        self.steps += 1;
                        if self.steps > MAX_LINES {
                            return Err(error(line, "generation exceeds 100000 iterations"));
                        }
                        self.indices.insert((*name).to_owned(), index);
                        self.expand(&lines[..end])?;
                    }
                    self.indices.remove(*name);
                    lines = &lines[end + 1..];
                }
                ["generate", ..] => return Err(error(line, "expected generate INDEX COUNT")),
                ["endgenerate", ..] => return Err(error(line, "unexpected endgenerate")),
                ["param", name, default] if self.indices.is_empty() => {
                    if let Some(value) = decimal(default) {
                        self.parameters.insert(
                            (*name).to_owned(),
                            self.overrides.get(*name).copied().unwrap_or(value),
                        );
                    }
                    self.output.push((line, text.to_owned()));
                }
                ["param" | "module" | "end", ..] if !self.indices.is_empty() => {
                    return Err(error(line, "generate may only contain module body items"));
                }
                _ => {
                    let text = interpolate(text, line, &self.indices)?;
                    self.output
                        .push((line, interpolate_parameters(&text, line, &self.parameters)?));
                }
            }
            if !self.indices.is_empty() {
                self.steps += 1;
                if self.steps > MAX_LINES {
                    return Err(error(line, "generation exceeds 100000 expansion steps"));
                }
            }
        }
        Ok(())
    }
}

pub(super) fn expand(
    source: &str,
    overrides: &BTreeMap<String, u64>,
) -> Result<Vec<Line>, Diagnostic> {
    let lines: Vec<_> = source
        .lines()
        .enumerate()
        .map(|(i, text)| (i + 1, text.split_once('#').map_or(text, |(code, _)| code)))
        .filter(|(_, text)| !text.trim().is_empty())
        .collect();
    let mut generator = Generator {
        overrides,
        parameters: BTreeMap::new(),
        indices: BTreeMap::new(),
        output: Vec::new(),
        steps: 0,
    };
    generator.expand(&lines)?;
    Ok(generator.output)
}
