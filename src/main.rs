use std::{
    env, fs,
    io::{self, Write},
    process::ExitCode,
};

fn run() -> Result<(), String> {
    let args: Vec<_> = env::args_os().skip(1).collect();
    let usage = "Usage: veximc check INPUT.vxm | veximc build INPUT.vxm [-o OUTPUT.sv]";
    if args.len() == 1 && args[0] == "--help" {
        println!("{usage}");
        return Ok(());
    }
    if args.len() == 1 && args[0] == "--version" {
        println!("veximc {}", env!("CARGO_PKG_VERSION"));
        return Ok(());
    }
    let (input, output, build) = match args.as_slice() {
        [cmd, input] if cmd == "check" => (input, None, false),
        [cmd, input] if cmd == "build" => (input, None, true),
        [cmd, input, flag, output] if cmd == "build" && flag == "-o" => (input, Some(output), true),
        _ => return Err(usage.into()),
    };
    let path = std::path::Path::new(input);
    let source = fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let module = veximc::parse(&source).map_err(|e| format!("{}:{e}", path.display()))?;
    if build {
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
