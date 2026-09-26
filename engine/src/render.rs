use crate::ffmpeg::{FrameDecoder, VideoEncoder};
use crate::img::Frame;
use crate::template::{Clip, Template, TextItem};
use crate::text::{draw_emoji, draw_nametag, hex_to_rgb, FontStore, TextDraw};
use anyhow::{bail, Context, Result};
use std::path::Path;

struct TextLayer {
    layer: crate::img::Layer,
    scale: f32,
    pivot: (f32, f32),
    dx: i64,
    dy: i64,
}

/// Which clip contains global time `t`; returns (index, clip_start).
fn clip_at(timeline: &[(f64, f64)], t: f64) -> Option<usize> {
    timeline.iter().position(|&(s, e)| t >= s && t < e)
}

fn clip_timeline(tpl: &Template) -> Vec<(f64, f64)> {
    let mut out = Vec::new();
    let mut acc = 0.0;
    for c in &tpl.clips {
        out.push((acc, acc + c.dur));
        acc += c.dur;
    }
    out
}

fn pop_scale(local: f64, pop_dur: f64) -> f32 {
    if pop_dur <= 0.0 {
        return 1.0;
    }
    if local <= 0.0 {
        return 0.0;
    }
    if local >= pop_dur {
        return 1.0;
    }
    let t = (local / pop_dur) as f32;
    // Physical spring simulation (stiffness=180, damping=20, zeta=0.74)
    let w0 = 12.0f32;
    let z = 0.74f32;
    let wd = w0 * (1.0 - z * z).sqrt();
    let env = (-z * w0 * t).exp();
    let val = 1.0 - env * ((wd * t).cos() + (z * w0 / wd) * (wd * t).sin());
    val.max(0.0)
}

fn wobble_offset(item: &TextItem, t: f64) -> (i64, i64) {
    match &item.wobble {
        Some(w) => {
            let seed = item.id.bytes().map(|b| b as f64).sum::<f64>();
            let dx = (t * w.freq as f64 * 6.28318 + seed).sin() * w.amp as f64;
            let dy = (t * w.freq as f64 * 6.28318 * 1.37 + seed * 1.7).sin() * w.amp as f64 * 0.6;
            (dx.round() as i64, dy.round() as i64)
        }
        None => (0, 0),
    }
}

pub struct Renderer<'a> {
    pub tpl: &'a Template,
    pub fonts: &'a FontStore,
    pub cw: u32,
    pub ch: u32,
    pub fps: f64,
}

impl<'a> Renderer<'a> {
    fn watermark_item(wm: &crate::template::Watermark) -> TextItem {
        TextItem {
            id: "__watermark".into(),
            style: "italic".into(),
            text: wm.text.clone(),
            colors: vec![wm.color.clone()],
            start: 0.0,
            end: f64::MAX,
            x: 0.5,
            y: wm.y,
            size: wm.size,
            type_reveal: None,
            word_starts: vec![],
            pop_dur: 0.0,
            wobble: None,
            rotate_jitter_deg: 0.0,
            tracking: 0.0,
            stroke: wm.outline,
            shadow: Some(crate::template::Shadow { dx: 2.0, dy: 3.0, blur: 2.0, opacity: 0.75 }),
            glow: 0.0,
            glow_color: "#000000".into(),
            shear: Some(0.0),
            font: wm.font.clone(),
            plate: 0.0,
        }
    }

    /// Compose one output frame.
    pub fn compose(&self, src_frame: &Frame, t: f64, local_t: f64, clip: &Clip, zoom: f32) -> Result<Frame> {
        let mut frame = if clip.burst > 0 && local_t < 0.30 {
            let steps = clip.burst.max(3);
            src_frame.zoom_burst(zoom, clip.anchor[0], clip.anchor[1], steps, self.cw, self.ch)
        } else {
            src_frame.motion_resample(zoom, clip.anchor[0], clip.anchor[1], self.cw, self.ch)
        };

        // ── grade pipeline ──
        let tint = clip.tint.clone().unwrap_or_else(|| self.tpl.grade.tint.clone());
        if let Some(darken) = clip.blur_darken {
            frame.blur_darken(9.0, darken.clamp(0.0, 0.95));
        }
        frame.chromatic_shift(self.tpl.grade.ca_px * clip.ca_mult);
        frame.grade(self.tpl.grade.contrast, self.tpl.grade.saturation, &tint);
        frame.unsharp(self.tpl.grade.sharpen);
        frame.vignette(self.tpl.grade.vignette);

        // ── overlays ──
        let td = TextDraw { store: self.fonts, canvas_w: self.cw, canvas_h: self.ch };
        let mut layers: Vec<TextLayer> = Vec::new();
        for item in &self.tpl.texts {
            if t < item.start || t > item.end { continue; }
            if let Some(l) = td.draw_text(item, t, "") {
                let local = t - item.start;
                let s = pop_scale(local, item.pop_dur);
                let (wx, wy) = wobble_offset(item, t);
                layers.push(TextLayer {
                    layer: l,
                    scale: s,
                    pivot: (item.x * self.cw as f32, item.y * self.ch as f32),
                    dx: wx,
                    dy: wy,
                });
            }
        }
        for tag in &self.tpl.nametags {
            if let Some(l) = draw_nametag(self.fonts, tag, t, self.cw, self.ch) {
                layers.push(TextLayer {
                    layer: l,
                    scale: 1.0,
                    pivot: (tag.x * self.cw as f32, tag.y * self.ch as f32),
                    dx: 0,
                    dy: 0,
                });
            }
        }
        for e in &self.tpl.emojis {
            if let Some(l) = draw_emoji(self.fonts, e, t, self.cw, self.ch) {
                layers.push(TextLayer {
                    layer: l,
                    scale: 1.0,
                    pivot: (e.x * self.cw as f32, e.y * self.ch as f32),
                    dx: 0,
                    dy: 0,
                });
            }
        }
        for tl in layers {
            frame.blend_layer_scaled(&tl.layer, tl.scale, tl.pivot.0, tl.pivot.1, tl.dx, tl.dy);
        }

        // ── flashes (above overlays, below watermark) ──
        for fl in &self.tpl.flashes {
            if t < fl.start || t > fl.start + fl.dur { continue; }
            let p = ((t - fl.start) / fl.dur.max(1e-6)) as f32;
            let env = if p < 0.12 { p / 0.12 } else { (-(p - 0.12) * 4.2).exp() };
            match fl.kind.as_str() {
                "black" => frame.overlay_solid([0, 0, 0], (env * fl.peak).min(1.0)),
                "white" => frame.overlay_solid([255, 255, 255], (env * fl.peak).min(1.0)),
                _ => frame.overlay_solid([227, 22, 28], (env * fl.peak).min(1.0)),
            }
        }

        // ── watermark (topmost) ──
        if let Some(wm) = &self.tpl.watermark {
            if !wm.text.is_empty() {
                let item = Self::watermark_item(wm);
                if let Some(mut l) = td.draw_text(&item, t, "") {
                    let op = wm.opacity.clamp(0.0, 1.0);
                    for px in l.data.chunks_exact_mut(4) {
                        px[3] = (px[3] as f32 * op) as u8;
                    }
                    frame.blend_layer(&l);
                }
            }
        }

        let _ = hex_to_rgb("#FFFFFF"); // keep import used for template-driven paths
        Ok(frame)
    }
}

/// Full sequential render of the template to `out`.
pub fn render_template(tpl: &Template, out: &Path, quiet: bool) -> Result<()> {
    let fps = tpl.canvas.fps;
    let total_frames = (tpl.duration() * fps).floor() as u64;
    if total_frames == 0 { bail!("template has zero frames"); }

    let fonts = FontStore::load(tpl)?;
    let renderer = Renderer { tpl, fonts: &fonts, cw: tpl.canvas.width, ch: tpl.canvas.height, fps };

    let audio_src = tpl
        .audio
        .as_ref()
        .map(|a| (a.src.clone(), a.offset))
        .or_else(|| tpl.clips.first().map(|c| (c.src.clone(), 0.0)));

    let mut encoder = VideoEncoder::open(
        out,
        tpl.canvas.width,
        tpl.canvas.height,
        fps,
        tpl.output.crf,
        &tpl.output.preset,
        audio_src
            .as_ref()
            .map(|(src, off)| (src.as_path(), *off, tpl.output.audio_bitrate.as_str())),
    )?;

    let timeline = clip_timeline(tpl);
    let mut current_clip: Option<usize> = None;
    let mut decoder: Option<FrameDecoder> = None;
    let mut src_buf: Vec<u8> = Vec::new();
    let mut local_frame: u64 = 0;
    let mut clip_src_frame = Frame::new(tpl.canvas.width, tpl.canvas.height);

    for f in 0..total_frames {
        let t = f as f64 / fps;
        let idx = clip_at(&timeline, t)
            .with_context(|| format!("no clip covers t={t:.3}"))?;
        let clip_start = timeline[idx].0;
        let local_t = t - clip_start;

        if current_clip != Some(idx) {
            decoder = Some(FrameDecoder::open(
                &tpl.clips[idx].src,
                tpl.clips[idx].src_in,
                tpl.clips[idx].dur + 0.5,
                tpl.canvas.width,
                tpl.canvas.height,
            )?);
            current_clip = Some(idx);
            local_frame = 0;
        }

        let want_frame = (local_t * fps).floor() as u64;
        let dec = decoder.as_mut().unwrap();
        while local_frame <= want_frame {
            if !dec.next_frame(&mut src_buf)? {
                bail!("clip {} ran out of frames at t={t:.3}", tpl.clips[idx].src.display());
            }
            local_frame += 1;
        }
        clip_src_frame.data = src_buf.clone();

        let clip = &tpl.clips[idx];
        let prog = if clip.dur > 0.0 { (local_t / clip.dur).clamp(0.0, 1.0) as f32 } else { 0.0 };
        let zoom = clip.zoom_from + (clip.zoom_to - clip.zoom_from) * prog;

        let frame = renderer.compose(&clip_src_frame, t, local_t, clip, zoom)?;
        encoder.write_frame(&frame.data)?;

        if !quiet && f % ((fps as u64) * 2).max(1) == 0 {
            eprintln!("[render] frame {f}/{total_frames} t={t:.2}s");
        }
    }

    encoder.finish()?;
    Ok(())
}

/// Render a single frame at global time `t` to a PNG (fast preview path).
pub fn render_frame_png(tpl: &Template, t: f64, out: &Path) -> Result<()> {
    let fonts = FontStore::load(tpl)?;
    let renderer = Renderer { tpl, fonts: &fonts, cw: tpl.canvas.width, ch: tpl.canvas.height, fps: tpl.canvas.fps };
    let timeline = clip_timeline(tpl);
    let idx = clip_at(&timeline, t).context("time outside timeline")?;
    let clip_start = timeline[idx].0;
    let local_t = t - clip_start;
    let mut dec = FrameDecoder::open(
        &tpl.clips[idx].src,
        tpl.clips[idx].src_in + local_t,
        0.2,
        tpl.canvas.width,
        tpl.canvas.height,
    )?;
    let mut buf = Vec::new();
    if !dec.next_frame(&mut buf)? { bail!("no frame at t={t}"); }
    let mut src = Frame::new(tpl.canvas.width, tpl.canvas.height);
    src.data = buf;
    let clip = &tpl.clips[idx];
    let prog = if clip.dur > 0.0 { (local_t / clip.dur).clamp(0.0, 1.0) as f32 } else { 0.0 };
    let zoom = clip.zoom_from + (clip.zoom_to - clip.zoom_from) * prog;
    let frame = renderer.compose(&src, t, local_t, clip, zoom)?;
    let rgb = image::RgbImage::from_raw(tpl.canvas.width, tpl.canvas.height, frame.data)
        .context("frame buffer size mismatch")?;
    rgb.save(out)?;
    Ok(())
}

pub fn validate(tpl: &Template) -> Result<()> {
    if tpl.clips.is_empty() { bail!("no clips"); }
    for (i, c) in tpl.clips.iter().enumerate() {
        if !c.src.exists() { bail!("clip {i}: source missing: {}", c.src.display()); }
        if c.dur <= 0.0 { bail!("clip {i}: non-positive duration"); }
    }
    let d = tpl.duration();
    eprintln!(
        "[check] OK: {} clips, {d:.2}s, {} texts, {} nametags, {} flashes, {} emojis",
        tpl.clips.len(),
        tpl.texts.len(),
        tpl.nametags.len(),
        tpl.flashes.len(),
        tpl.emojis.len()
    );
    Ok(())
}
