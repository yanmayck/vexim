use std::{
    ffi::OsString,
    fs, io,
    path::{Path, PathBuf},
    process::Command,
    sync::atomic::{AtomicUsize, Ordering},
};

pub(crate) const USAGE: &str =
    "veximc design TOP INPUT.sv|INPUT.vxm... -o OUTPUT.sv [--prune] [--share]";

struct Staging(PathBuf);

impl Staging {
    fn create() -> io::Result<Self> {
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let root = std::env::temp_dir();
        let mut builder = fs::DirBuilder::new();
        #[cfg(unix)]
        {
            use std::os::unix::fs::DirBuilderExt;
            builder.mode(0o700);
        }
        for _ in 0..32 {
            let number = NEXT.fetch_add(1, Ordering::Relaxed);
            let path = root.join(format!("vexim-design-{}-{number}", std::process::id()));
            match builder.create(&path) {
                Ok(()) => return Ok(Self(path)),
                Err(error) if error.kind() == io::ErrorKind::AlreadyExists => {}
                Err(error) => return Err(error),
            }
        }
        Err(io::Error::new(
            io::ErrorKind::AlreadyExists,
            "could not create a unique design staging directory",
        ))
    }
}

impl Drop for Staging {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn stage_source(source: &Path, target: &Path) -> Result<(), String> {
    if source.extension().is_some_and(|suffix| suffix == "vxm") {
        let text =
            fs::read_to_string(source).map_err(|error| format!("{}: {error}", source.display()))?;
        let module =
            veximc::parse(&text).map_err(|error| format!("{}:{error}", source.display()))?;
        fs::write(target, module.system_verilog())
    } else {
        fs::copy(source, target).map(|_| ())
    }
    .map_err(|error| format!("{}: {error}", source.display()))
}

pub(crate) fn run(args: &[OsString]) -> Result<(), String> {
    if args.len() == 1 && args[0] == "--help" {
        println!("Usage: {USAGE}");
        return Ok(());
    }
    let [top, flags @ ..] = args else {
        return Err(format!("Usage: {USAGE}"));
    };
    let top = top
        .to_str()
        .filter(|name| {
            let mut chars = name.bytes();
            chars
                .next()
                .is_some_and(|c| c.is_ascii_alphabetic() || c == b'_')
                && chars.all(|c| c.is_ascii_alphanumeric() || c == b'_')
        })
        .ok_or("TOP must be a plain SystemVerilog identifier")?;
    let mut sources = Vec::new();
    let mut output = None;
    let mut prune = false;
    let mut share = false;
    let mut flags = flags.iter();
    while let Some(flag) = flags.next() {
        if flag == "-o" && output.is_none() {
            output = Some(flags.next().ok_or("missing output path after -o")?);
        } else if flag == "--prune" && !prune {
            prune = true;
        } else if flag == "--share" && !share {
            share = true;
        } else if flag.to_string_lossy().starts_with('-') {
            return Err(format!(
                "unexpected flag: {}\nUsage: {USAGE}",
                flag.to_string_lossy()
            ));
        } else {
            sources.push(Path::new(flag));
        }
    }
    let output = output
        .filter(|_| !sources.is_empty())
        .ok_or_else(|| format!("Usage: {USAGE}"))?;
    let stage = Staging::create().map_err(|error| format!("cannot stage HDL design: {error}"))?;
    let mut inputs = Vec::new();
    for (index, source) in sources.into_iter().enumerate() {
        let name = format!("input{index}.sv");
        stage_source(source, &stage.0.join(&name))?;
        inputs.push(name);
    }

    // Use literal staging filenames so neither source paths nor the
    // destination can be interpreted as part of the Yosys script.
    let mut script = format!(
        "read_verilog -sv {}; hierarchy -check -top {top}; proc; flatten; ",
        inputs.join(" ")
    );
    if share {
        script.push_str(crate::global_share::RESOURCE_SHARING);
    }
    if prune {
        script.push_str("opt_clean -purge; ");
    }
    script.push_str("write_verilog -norename output.sv");

    let result = Command::new("yosys")
        .current_dir(&stage.0)
        .args(["-Q", "-p", &script])
        .output()
        .map_err(|error| format!("could not start Yosys: {error}"))?;
    if !result.status.success() {
        return Err(format!(
            "Yosys design processing failed ({})\n{}{}",
            result.status,
            String::from_utf8_lossy(&result.stdout),
            String::from_utf8_lossy(&result.stderr)
        ));
    }
    fs::copy(stage.0.join("output.sv"), output)
        .map_err(|error| format!("{}: {error}", Path::new(output).display()))?;
    Ok(())
}
