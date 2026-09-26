mod ffmpeg;
mod img;
mod render;
mod template;
mod text;

use anyhow::{bail, Context, Result};
use std::path::{Path, PathBuf};

fn main() {
    if let Err(e) = run() {
        eprintln!("error: {e:#}");
        std::process::exit(1);
    }
}

fn usage() -> &'static str {
    "splash_engine — ishowsplash-style short-video rendering engine

USAGE:
  splash_engine render <template.json> [-o out.mp4] [--crf N] [--preset slow|medium|fast] [--quiet]
  splash_engine frame  <template.json> --at <seconds> -o frame.png
  splash_engine check  <template.json>

Renders 1080x1440@60fps templates (motion, grade, captions, flashes, watermark) via
ffmpeg pipe I/O and a pure-Rust per-frame pipeline. Text styles: marker | italic | impact.
"
}

fn run() -> Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let cmd = args.first().map(String::as_str).unwrap_or("");
    match cmd {
        "render" => {
            let mut tpl_path: Option<PathBuf> = None;
            let mut out: Option<PathBuf> = None;
            let mut crf: Option<u8> = None;
            let mut preset: Option<String> = None;
            let mut quiet = false;
            let mut it = args.iter().skip(1);
            while let Some(a) = it.next() {
                match a.as_str() {
                    "-o" => out = Some(PathBuf::from(it.next().context("-o needs value")?)),
                    "--crf" => crf = Some(it.next().context("--crf needs value")?.parse()?),
                    "--preset" => preset = Some(it.next().context("--preset needs value")?.to_string()),
                    "--quiet" | "-q" => quiet = true,
                    other if !other.starts_with('-') => tpl_path = Some(PathBuf::from(other)),
                    other => bail!("unknown flag {other}"),
                }
            }
            let tpl_path = tpl_path.context("template path required")?;
            let mut tpl = template::Template::load(&tpl_path)?;
            if let Some(c) = crf { tpl.output.crf = c; }
            if let Some(p) = preset { tpl.output.preset = p; }
            let out = out.unwrap_or_else(|| PathBuf::from("out.mp4"));
            render::validate(&tpl)?;
            render::render_template(&tpl, &out, quiet)?;
            eprintln!("[done] wrote {}", out.display());
            Ok(())
        }
        "frame" => {
            let mut tpl_path: Option<PathBuf> = None;
            let mut at: Option<f64> = None;
            let mut out: Option<PathBuf> = None;
            let mut it = args.iter().skip(1);
            while let Some(a) = it.next() {
                match a.as_str() {
                    "--at" => at = Some(it.next().context("--at needs value")?.parse()?),
                    "-o" => out = Some(PathBuf::from(it.next().context("-o needs value")?)),
                    other if !other.starts_with('-') => tpl_path = Some(PathBuf::from(other)),
                    other => bail!("unknown flag {other}"),
                }
            }
            let tpl_path = tpl_path.context("template path required")?;
            let at = at.context("--at seconds required")?;
            let out = out.unwrap_or_else(|| PathBuf::from("frame.png"));
            let tpl = template::Template::load(&tpl_path)?;
            render::render_frame_png(&tpl, at, &out)?;
            eprintln!("[done] wrote {}", out.display());
            Ok(())
        }
        "check" => {
            let tpl_path = args.get(1).context("template path required")?;
            let tpl = template::Template::load(Path::new(tpl_path))?;
            render::validate(&tpl)?;
            Ok(())
        }
        _ => {
            println!("{}", usage());
            Ok(())
        }
    }
}
