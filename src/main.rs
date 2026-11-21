use std::{
    collections::BTreeMap,
    env, fs,
    io::{self, Write},
    process::ExitCode,
};

fn run() -> Result<(), String> {
    let args: Vec<_> = env::args_os().skip(1).collect();
    let usage = "Usage: veximc check INPUT.vxm [--param NAME=VALUE]...\n       veximc build INPUT.vxm [-o OUTPUT.sv] [--param NAME=VALUE]... [--opt-area]";
    if args.len() == 1 && args[0] == "--help" {
        println!("{usage}");
        return Ok(());
    }
    if args.len() == 1 && args[0] == "--version" {
        println!("veximc {}", env!("CARGO_PKG_VERSION"));
        return Ok(());
    }
    let (input, flags, build) = match args.as_slice() {
        [cmd, input, flags @ ..] if cmd == "check" => (input, flags, false),
        [cmd, input, flags @ ..] if cmd == "build" => (input, flags, true),
        _ => return Err(usage.into()),
    };
    let mut output = None;
    let mut opt_area = false;
    let mut overrides = BTreeMap::new();
    let mut flags = flags.iter();
    while let Some(flag) = flags.next() {
        if flag == "--opt-area" && build && !opt_area {
            opt_area = true;
            continue;
        }
        let value = flags.next().ok_or(usage)?;
        if flag == "-o" && build && output.is_none() {
            output = Some(value);
        } else if flag == "--param" {
            let (name, number) = value
                .to_str()
                .and_then(|text| text.split_once('='))
                .ok_or("expected --param NAME=VALUE")?;
            let number = number
                .bytes()
                .all(|c| c.is_ascii_digit())
                .then(|| number.parse::<u64>().ok())
                .flatten()
                .ok_or("parameter override must be an unsigned decimal integer")?;
            if overrides.insert(name.to_owned(), number).is_some() {
                return Err(format!("duplicate parameter override {name}"));
            }
        } else {
            return Err(usage.into());
        }
    }
    let path = std::path::Path::new(input);
    let source = fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut module = veximc::parse_with_parameters(&source, &overrides)
        .map_err(|e| format!("{}:{e}", path.display()))?;
    if build {
        if opt_area {
            module.propagate_constants();
            module.share_operators();
        }
        let sv = module.system_verilog();
        if let Some(output) = output {
            fs::write(output, sv)
                .map_err(|e| format!("{}: {e}", std::path::Path::new(output).display()))?;
        } else {
            io::stdout()
                .lock()
                .write_all(sv.as_bytes())
                .map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}
