use anyhow::{bail, Context, Result};
use std::io::{BufRead, BufReader, Read, Write};
use std::process::{Child, ChildStderr, ChildStdin, ChildStdout, Command, Stdio};
use std::path::Path;

/// Decodes a clip region into raw RGB24 frames via an ffmpeg pipe.
pub struct FrameDecoder {
    child: Child,
    stdout: ChildStdout,
    pub width: u32,
    pub height: u32,
    frame_size: usize,
    eof: bool,
}

impl FrameDecoder {
    /// Open `src`, seek to `seek_sec`, decode `dur_sec` of frames scaled to cover `out_w x out_h`.
    /// Frames keep the source aspect (cover-fit is done by the renderer per frame).
    pub fn open(src: &Path, seek_sec: f64, dur_sec: f64, out_w: u32, out_h: u32) -> Result<Self> {
        // Probe native size first so the renderer can do sub-pixel motion sampling at full detail.
        let (sw, sh) = probe_size(src)?;
        // Feed the renderer at (at least) canvas size; upscale small sources, keep large ones native.
        let scale = format!("scale={out_w}:{out_h}:force_original_aspect_ratio=increase:flags=bicubic");
        let mut args = vec![
            "-v".into(), "error".into(),
            "-ss".into(), format!("{seek_sec:.3}"),
            "-i".into(), src.to_string_lossy().into_owned(),
            "-t".into(), format!("{dur_sec:.3}"),
            "-an".into(),
            "-vf".into(), scale,
            "-f".into(), "rawvideo".into(),
            "-pix_fmt".into(), "rgb24".into(),
            "-".into(),
        ];
        if (sw as i64) < out_w as i64 || (sh as i64) < out_h as i64 {
            args[7] = format!("scale={out_w}:{out_h}:force_original_aspect_ratio=increase:flags=lanczos");
        }
        let mut child = Command::new("ffmpeg")
            .args(&args)
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .context("failed to spawn ffmpeg decoder (is ffmpeg in PATH?)")?;
        let stdout = child.stdout.take().context("decoder stdout")?;
        let frame_size = (out_w * out_h * 3) as usize;
        Ok(FrameDecoder { child, stdout, width: out_w, height: out_h, frame_size, eof: false })
    }

    /// Next frame; returns None at end of stream.
    pub fn next_frame(&mut self, buf: &mut Vec<u8>) -> Result<bool> {
        if self.eof { return Ok(false); }
        buf.resize(self.frame_size, 0);
        let mut read = 0usize;
        while read < self.frame_size {
            let n = self.stdout.read(&mut buf[read..])?;
            if n == 0 {
                self.eof = true;
                if read == 0 { return Ok(false); }
                bail!("decoder stream truncated mid-frame");
            }
            read += n;
        }
        Ok(true)
    }
}

impl Drop for FrameDecoder {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

pub fn probe_size(src: &Path) -> Result<(u32, u32)> {
    let out = Command::new("ffprobe")
        .args(["-v", "error", "-select_streams", "v:0",
               "-show_entries", "stream=width,height",
               "-of", "csv=p=0:s=x", &src.to_string_lossy()])
        .output()
        .context("failed to run ffprobe")?;
    if !out.status.success() { bail!("ffprobe failed for {}", src.display()); }
    let s = String::from_utf8_lossy(&out.stdout);
    let mut it = s.trim().split('x');
    let w: u32 = it.next().unwrap_or("0").parse().context("probe width")?;
    let h: u32 = it.next().unwrap_or("0").parse().context("probe height")?;
    Ok((w, h))
}

pub struct VideoEncoder {
    child: Child,
    stdin: ChildStdin,
    stderr: BufReader<ChildStderr>,
}

impl VideoEncoder {
    /// Spawn the final x264 encode reading raw RGB24 frames on stdin.
    #[allow(clippy::too_many_arguments)]
    pub fn open(
        out: &Path,
        width: u32,
        height: u32,
        fps: f64,
        crf: u8,
        preset: &str,
        audio: Option<(&Path, f64, &str)>,
    ) -> Result<Self> {
        let mut cmd = Command::new("ffmpeg");
        cmd.arg("-y").arg("-v").arg("error")
            .args(["-f", "rawvideo", "-pix_fmt", "rgb24",
                   "-s", &format!("{width}x{height}"),
                   "-r", &format!("{fps:.6}"), "-i", "-"]);
        match audio {
            Some((src, offset, bitrate)) => {
                cmd.arg("-ss").arg(format!("{offset:.3}"))
                    .arg("-i").arg(src)
                    .args(["-map", "0:v:0", "-map", "1:a:0"])
                    .args(["-c:a", "aac", "-b:a", bitrate]);
            }
            None => {}
        }
        cmd.args(["-c:v", "libx264",
                  "-preset", preset,
                  "-crf", &crf.to_string(),
                  "-pix_fmt", "yuv420p",
                  "-profile:v", "high",
                  "-movflags", "+faststart"]);
        if audio.is_none() { cmd.args(["-an"]); }
        cmd.arg(out);
        let mut child = cmd
            .stdin(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .context("failed to spawn ffmpeg encoder")?;
        let stdin = child.stdin.take().context("encoder stdin")?;
        let stderr = BufReader::new(child.stderr.take().context("encoder stderr")?);
        Ok(VideoEncoder { child, stdin, stderr })
    }

    pub fn write_frame(&mut self, frame: &[u8]) -> Result<()> {
        self.stdin.write_all(frame)?;
        Ok(())
    }

    pub fn finish(mut self) -> Result<()> {
        self.stdin.flush()?;
        drop(self.stdin);
        if let Some(child) = self.child.wait().ok() {
            if !child.success() {
                let mut msg = String::new();
                let _ = self.stderr.read_line(&mut msg);
                bail!("encoder exited with {child}: {msg}");
            }
        }
        Ok(())
    }
}
