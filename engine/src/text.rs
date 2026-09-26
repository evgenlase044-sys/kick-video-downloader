use crate::img::{dilate_alpha, gaussian_blur_u8, Layer};
use crate::template::{Emoji, NameTag, Shadow, TextItem};
use ab_glyph::{Font, FontVec, Glyph, PxScale, PxScaleFont, ScaleFont, VariableFont};
use anyhow::{Context, Result};

pub struct LoadedFont {
    pub font: FontVec,
}

pub struct FontStore {
    pub marker: LoadedFont,
    pub sans: LoadedFont,
    pub emoji: Option<LoadedFont>,
}

impl FontStore {
    pub fn load(tpl: &crate::template::Template) -> Result<Self> {
        let defaults = default_font_paths();
        let marker_path = tpl
            .fonts
            .marker
            .clone()
            .or_else(|| defaults.marker.clone())
            .context("no marker font found (set fonts.marker in template)")?;
        let sans_path = tpl
            .fonts
            .sans
            .clone()
            .or_else(|| defaults.sans.clone())
            .context("no sans font found (set fonts.sans in template)")?;
        let emoji_path = tpl.fonts.emoji.clone().or_else(|| defaults.emoji.clone());
        let load = |p: &std::path::Path| -> Result<FontVec> {
            let data = std::fs::read(p).with_context(|| format!("reading font {}", p.display()))?;
            Ok(FontVec::try_from_vec(data)?)
        };
        let mut marker_font = load(&marker_path)?;
        let _ = marker_font.set_variation(b"wght", 400.0);
        let mut sans_font = load(&sans_path)?;
        let _ = sans_font.set_variation(b"wght", 800.0);
        if std::env::var("SPLASH_DEBUG_FONTS").is_ok() {
            for (name, f) in [("marker", &marker_font), ("sans", &sans_font)] {
                let upm = f.units_per_em().unwrap_or(0.0);
                let asc = f.ascent_unscaled();
                let desc = f.descent_unscaled();
                let sf = f.as_scaled(PxScale::from(62.0));
                let adv_a = sf.h_advance(sf.glyph_id('A'));
                let adv_m = sf.h_advance(sf.glyph_id('M'));
                eprintln!(
                    "[font:{name}] upm={upm} asc={asc} desc={desc} height={} advA62={adv_a:.1} advM62={adv_m:.1}",
                    asc - desc
                );
            }
        }
        let emoji = match emoji_path {
            Some(p) => load(&p).ok().map(|f| LoadedFont { font: f }),
            None => None,
        };
        Ok(FontStore {
            marker: LoadedFont { font: marker_font },
            sans: LoadedFont { font: sans_font },
            emoji,
        })
    }
}

pub struct DefaultPaths {
    pub marker: Option<std::path::PathBuf>,
    pub sans: Option<std::path::PathBuf>,
    pub emoji: Option<std::path::PathBuf>,
}

pub fn default_font_paths() -> DefaultPaths {
    let job_fonts = std::path::PathBuf::from("../fonts");
    let win = std::path::PathBuf::from("C:/Windows/Fonts");
    let pick = |name: &str| -> Option<std::path::PathBuf> {
        let candidates = [
            job_fonts.join(name),
            std::path::PathBuf::from("fonts").join(name),
        ];
        candidates.into_iter().find(|p| p.exists())
    };
    DefaultPaths {
        marker: std::env::var("SPLASH_MARKER_FONT")
            .ok()
            .map(std::path::PathBuf::from)
            .or_else(|| pick("Bangers-Regular.ttf")),
        sans: pick("montserrat-montserrat-extrabold.ttf")
            .or_else(|| pick("Montserrat-VariableFont_wght.ttf")),
        emoji: win.join("seguiemj.ttf").exists().then(|| win.join("seguiemj.ttf")),
    }
}

pub fn hex_to_rgb(s: &str) -> [u8; 3] {
    let s = s.trim().trim_start_matches('#');
    if s.len() >= 6 {
        let v = u32::from_str_radix(&s[..6], 16).unwrap_or(0xFFFFFF);
        [(v >> 16) as u8, (v >> 8) as u8, v as u8]
    } else {
        [255, 255, 255]
    }
}

struct GlyphBitmap {
    w: i64,
    h: i64,
    alpha: Vec<u8>,
    /// Top-left of the bitmap relative to the pen origin (canvas space).
    dx: f32,
    dy: f32,
}

/// Rasterize a glyph with rotation (deg) and shear applied via inverse mapping.
fn rasterize_glyph<F: Font>(sf: &PxScaleFont<F>, glyph: &Glyph, rot_deg: f32, shear: f32) -> Option<GlyphBitmap> {
    let og = sf.outline_glyph(glyph.clone())?;
    let bb = og.px_bounds();
    let bw = bb.width().ceil().max(1.0) as usize;
    let bh = bb.height().ceil().max(1.0) as usize;
    let mut raw = vec![0u8; bw * bh];
    og.draw(|x, y, c| {
        let xi = x as usize;
        let yi = y as usize;
        if xi < bw && yi < bh {
            let i = yi * bw + xi;
            raw[i] = (raw[i] as f32 + c * 255.0).min(255.0) as u8;
        }
    });
    let (sin, cos) = rot_deg.to_radians().sin_cos();
    let tan = shear;
    let cx = bw as f32 / 2.0;
    let cy = bh as f32 / 2.0;
    let corners = [(-cx, -cy), (bw as f32 - cx, -cy), (-cx, bh as f32 - cy), (bw as f32 - cx, bh as f32 - cy)];
    let (mut minx, mut maxx, mut miny, mut maxy) = (f32::MAX, f32::MIN, f32::MAX, f32::MIN);
    for &(x, y) in &corners {
        let tx = x * cos - y * sin + tan * y;
        let ty = x * sin + y * cos;
        minx = minx.min(tx);
        maxx = maxx.max(tx);
        miny = miny.min(ty);
        maxy = maxy.max(ty);
    }
    let out_w = (maxx - minx).ceil().max(1.0) as usize;
    let out_h = (maxy - miny).ceil().max(1.0) as usize;
    let mut alpha = vec![0u8; out_w * out_h];
    for oy in 0..out_h {
        for ox in 0..out_w {
            let px = ox as f32 + minx - out_w as f32 / 2.0;
            let py = oy as f32 + miny - out_h as f32 / 2.0;
            let ix = px * cos + py * sin;
            let iy = -px * sin + py * cos;
            let sx = ix - tan * iy;
            let sy = iy;
            let rx = sx + cx;
            let ry = sy + cy;
            if rx < 0.0 || ry < 0.0 || rx >= bw as f32 - 0.01 || ry >= bh as f32 - 0.01 {
                continue;
            }
            let x0 = rx.floor() as usize;
            let y0 = ry.floor() as usize;
            let tx = rx - x0 as f32;
            let ty = ry - y0 as f32;
            let g = |xx: usize, yy: usize| -> f32 {
                if xx < bw && yy < bh { raw[yy * bw + xx] as f32 } else { 0.0 }
            };
            let top = g(x0, y0) * (1.0 - tx) + g(x0 + 1, y0) * tx;
            let bot = g(x0, y0 + 1) * (1.0 - tx) + g(x0 + 1, y0 + 1) * tx;
            let v = top * (1.0 - ty) + bot * ty;
            alpha[oy * out_w + ox] = v.clamp(0.0, 255.0) as u8;
        }
    }
    Some(GlyphBitmap {
        w: out_w as i64,
        h: out_h as i64,
        alpha,
        dx: bb.min.x + (out_w as f32 / 2.0 - cx),
        dy: bb.min.y + (out_h as f32 / 2.0 - cy),
    })
}

fn stamp(layer: &mut Layer, gb: &GlyphBitmap, color: [u8; 3]) {
    let lw = layer.w as i64;
    let lh = layer.h as i64;
    for gy in 0..gb.h {
        for gx in 0..gb.w {
            let a = gb.alpha[(gy * gb.w + gx) as usize];
            if a == 0 { continue; }
            let px = gb.dx as i64 + gx;
            let py = gb.dy as i64 + gy;
            if px < 0 || py < 0 || px >= lw || py >= lh { continue; }
            let idx = ((py * lw + px) * 4) as usize;
            if a as u32 >= layer.data[idx + 3] as u32 {
                layer.data[idx] = color[0];
                layer.data[idx + 1] = color[1];
                layer.data[idx + 2] = color[2];
                layer.data[idx + 3] = a;
            }
        }
    }
}

fn hash_seed(s: &str) -> u64 {
    let mut h: u64 = 1469598103934665603;
    for b in s.bytes() {
        h ^= b as u64;
        h = h.wrapping_mul(1099511628211);
    }
    h
}

fn measure<F: Font>(sf: &PxScaleFont<F>, text: &str, tracking_px: f32) -> f32 {
    let mut x = 0f32;
    for ch in text.chars() {
        let gid = sf.glyph_id(ch);
        if gid.0 == 0 && ch != ' ' { continue; }
        x += sf.h_advance(gid) + tracking_px;
    }
    x.max(0.0)
}

pub struct TextDraw<'a> {
    pub store: &'a FontStore,
    pub canvas_w: u32,
    pub canvas_h: u32,
}

impl<'a> TextDraw<'a> {
    fn font_for<'f>(&'f self, item: &TextItem) -> &'f LoadedFont {
        let has_cyrillic = item.text.chars().any(|c| ('\u{0400}'..='\u{04FF}').contains(&c));
        if has_cyrillic {
            return &self.store.sans;
        }
        match item.style.as_str() {
            "italic" | "impact" => &self.store.sans,
            _ => &self.store.marker,
        }
    }

    /// Render a TextItem into a full-canvas RGBA layer at time `t`.
    pub fn draw_text(&self, item: &TextItem, t: f64, seed_extra: &str) -> Option<Layer> {
        let dur = item.end - item.start;
        if dur <= 0.0 || item.text.trim().is_empty() { return None; }
        let local = t - item.start;
        if local < -0.0001 || t > item.end { return None; }

        let font = self.font_for(item);
        let size_px = item.size * (self.canvas_h as f32 / 1440.0);
        let sf = font.font.as_scaled(PxScale::from(size_px));
        let shear = item.shear.unwrap_or(match item.style.as_str() {
            "italic" | "impact" => 0.20,
            _ => 0.0,
        });
        let tracking = item.tracking * size_px;

        let words: Vec<&str> = item.text.split_whitespace().collect();
        if words.is_empty() { return None; }
        let span = (item.end - item.start) as f32;
        let word_starts: Vec<f32> = if !item.word_starts.is_empty() {
            item.word_starts.iter().map(|&s| s as f32).collect()
        } else if let Some(tr) = item.type_reveal {
            let n = words.len() as f32;
            (0..words.len()).map(|i| tr as f32 * span * (i as f32 / n.max(1.0))).collect()
        } else {
            vec![0.0; words.len()]
        };
        let colors: Vec<[u8; 3]> = item.colors.iter().map(|c| hex_to_rgb(c)).collect();

        // Layout with wrapping at 92% canvas width
        let max_w = self.canvas_w as f32 * 0.92;
        let space_w = sf.h_advance(sf.glyph_id(' ')) + tracking;
        let mut lines: Vec<Vec<(usize, f32)>> = vec![Vec::new()]; // (word index, width)
        for (wi, w) in words.iter().enumerate() {
            let wpx = measure(&sf, w, tracking);
            let line_w: f32 = lines.last().unwrap().iter().map(|(_, pw)| *pw).sum::<f32>()
                + lines.last().unwrap().len() as f32 * space_w;
            if !lines.last().unwrap().is_empty() && line_w + space_w + wpx > max_w {
                lines.push(Vec::new());
            }
            lines.last_mut().unwrap().push((wi, wpx));
        }
        let line_h = size_px * 1.12;
        let total_h = lines.len() as f32 * line_h;

        let mut layer = Layer::new(self.canvas_w, self.canvas_h);
        if item.plate > 0.0 {
            let pw = (max_w.min(self.canvas_w as f32 * 0.95)) as i64;
            let ph = (total_h + size_px * 0.5) as i64;
            let x0 = (item.x * self.canvas_w as f32) as i64 - pw / 2;
            let y0 = (item.y * self.canvas_h as f32) as i64 - ph / 2;
            for yy in y0.max(0)..(y0 + ph).min(layer.h as i64) {
                for xx in x0.max(0)..(x0 + pw).min(layer.w as i64) {
                    let i = ((yy * layer.w as i64 + xx) * 4) as usize;
                    layer.data[i + 3] = (item.plate * 255.0) as u8;
                }
            }
        }

        let seed = hash_seed(&format!("{}{}", item.id, seed_extra));
        let mut rng_state = seed | 1;
        let mut rnd = move || {
            rng_state ^= rng_state << 13;
            rng_state ^= rng_state >> 7;
            rng_state ^= rng_state << 17;
            (rng_state >> 33) as f32 / (u32::MAX as f32) * 2.0 - 1.0
        };

        let mut pen_y = (item.y * self.canvas_h as f32) - total_h / 2.0 + size_px * 0.72;
        if std::env::var("SPLASH_DEBUG_FONTS").is_ok() {
            let lw0 = lines.first().map(|l| l.iter().map(|(_, pw)| *pw).sum::<f32>()).unwrap_or(0.0);
            eprintln!(
                "[layout:{}] lines={} total_h={total_h:.1} pen_y={pen_y:.1} line_w0={lw0:.1} size={size_px:.1} y={} t={t:.3}",
                item.id,
                lines.len(),
                item.y
            );
        }
        for line in &lines {
            let line_w: f32 = line.iter().map(|(_, pw)| *pw).sum::<f32>()
                + (line.len().saturating_sub(1)) as f32 * space_w;
            let mut pen_x = (item.x * self.canvas_w as f32) - line_w / 2.0;
            for (wi, wpx) in line {
                let ws = word_starts.get(*wi).copied().unwrap_or(0.0);
                if (local as f32) < ws {
                    pen_x += wpx + space_w;
                    continue;
                }
                let text = words[*wi];
                let color = colors[*wi % colors.len()];
                let mut gx = pen_x;
                for ch in text.chars() {
                    let gid = sf.glyph_id(ch);
                    if gid.0 == 0 && ch != ' ' { continue; }
                    let g = gid.with_scale_and_position(sf.scale, ab_glyph::point(gx, pen_y));
                    let jitter = item.rotate_jitter_deg * rnd();
                    if let Some(gb) = rasterize_glyph(&sf, &g, jitter, shear) {
                        stamp(&mut layer, &gb, color);
                    }
                    gx += sf.h_advance(gid) + tracking;
                }
                pen_x += wpx + space_w;
            }
            pen_y += line_h;
        }

        apply_effects(&mut layer, item, size_px);
        Some(layer)
    }
}

fn apply_effects(layer: &mut Layer, item: &TextItem, size_px: f32) {
    let w = layer.w as usize;
    let h = layer.h as usize;
    if w == 0 || h == 0 { return; }
    let alpha: Vec<u8> = (0..w * h).map(|i| layer.data[i * 4 + 3]).collect();
    // Nothing to draw?
    if alpha.iter().all(|&a| a == 0) { return; }
    let stroke_r = (item.stroke * size_px / 64.0).round().max(0.0) as usize;
    let fill = layer.data.clone();
    let mut composed = vec![0u8; w * h * 4];

    // Dual-layer glow (bottom-most): wide ambient glow + tight intense core
    if item.glow > 0.5 {
        let gc = hex_to_rgb(&item.glow_color);
        // 1. Wide soft ambient glow
        let mut g_wide = alpha.clone();
        let wide_r = (item.glow * 1.8).round().max(4.0) as usize;
        let wide_sig = item.glow * 0.75;
        gaussian_blur_u8(&mut g_wide, layer.w, layer.h, wide_r, wide_sig, 1);
        for i in 0..w * h {
            let a = g_wide[i];
            if a == 0 { continue; }
            let src_a = (a as f32 / 255.0 * 0.45).min(1.0);
            blend_under(&mut composed, i * 4, gc, (src_a * 255.0) as u8);
        }
        // 2. Tight intense core glow
        let mut g_tight = alpha.clone();
        let tight_r = (item.glow * 0.7).round().max(2.0) as usize;
        let tight_sig = item.glow * 0.28;
        gaussian_blur_u8(&mut g_tight, layer.w, layer.h, tight_r, tight_sig, 1);
        for i in 0..w * h {
            let a = g_tight[i];
            if a == 0 { continue; }
            let src_a = (a as f32 / 255.0 * 0.85).min(1.0);
            blend_under(&mut composed, i * 4, gc, (src_a * 255.0) as u8);
        }
    }

    // Drop shadow
    if let Some(sh) = &item.shadow {
        let mut s_alpha = alpha.clone();
        let blur_r = (sh.blur.max(1.0) * 2.0).round() as usize;
        gaussian_blur_u8(&mut s_alpha, layer.w, layer.h, blur_r.max(3), (sh.blur.max(0.5)) * 0.8, 1);
        let mut off = vec![0u8; w * h];
        let dx = sh.dx.round() as i64;
        let dy = sh.dy.round() as i64;
        for y in 0..h as i64 {
            for x in 0..w as i64 {
                let sx = x - dx;
                let sy = y - dy;
                if sx < 0 || sy < 0 || sx >= w as i64 || sy >= h as i64 { continue; }
                off[(y * w as i64 + x) as usize] = s_alpha[(sy * w as i64 + sx) as usize];
            }
        }
        for i in 0..w * h {
            let a = off[i];
            if a == 0 { continue; }
            let src_a = (a as f32 / 255.0 * sh.opacity).min(1.0);
            blend_under(&mut composed, i * 4, [0, 0, 0], (src_a * 255.0) as u8);
        }
    }

    // Outline (dilated minus fill)
    if stroke_r > 0 {
        let dil = dilate_alpha(layer, stroke_r);
        for i in 0..w * h {
            let a = dil[i].saturating_sub(alpha[i]);
            if a == 0 { continue; }
            blend_under(&mut composed, i * 4, [0, 0, 0], a);
        }
    }

    // Main fill on top
    for i in 0..w * h {
        let a = fill[i * 4 + 3];
        if a == 0 { continue; }
        let idx = i * 4;
        composed[idx] = fill[idx];
        composed[idx + 1] = fill[idx + 1];
        composed[idx + 2] = fill[idx + 2];
        composed[idx + 3] = a.max(composed[idx + 3]);
    }

    layer.data = composed;

    fn blend_under(dst: &mut [u8], idx: usize, color: [u8; 3], a: u8) {
        if a == 0 { return; }
        let existing_a = dst[idx + 3] as f32 / 255.0;
        if existing_a >= 1.0 { return; }
        let sa = a as f32 / 255.0;
        let out_a = existing_a + sa * (1.0 - existing_a);
        if out_a <= 0.0 { return; }
        for k in 0..3 {
            let existing_c = dst[idx + k] as f32 / 255.0 * existing_a;
            let new_c = color[k] as f32 / 255.0 * sa;
            let c = (existing_c + new_c * (1.0 - existing_a)) / out_a.max(0.0001);
            dst[idx + k] = (c.clamp(0.0, 1.0) * 255.0) as u8;
        }
        dst[idx + 3] = (out_a.clamp(0.0, 1.0) * 255.0) as u8;
    }
}

/// Draw a NameTag (bold oblique text + small arrow), returns canvas-sized layer.
pub fn draw_nametag(store: &FontStore, tag: &NameTag, t: f64, canvas_w: u32, canvas_h: u32) -> Option<Layer> {
    if t < tag.start || t > tag.end { return None; }
    let item = TextItem {
        id: format!("tag_{}_{}", tag.text, tag.x),
        style: "italic".into(),
        text: tag.text.clone(),
        colors: vec![tag.color.clone()],
        start: tag.start,
        end: tag.end,
        x: tag.x,
        y: tag.y,
        size: tag.size,
        type_reveal: None,
        word_starts: vec![],
        pop_dur: 0.0,
        wobble: None,
        rotate_jitter_deg: 0.0,
        tracking: 0.02,
        stroke: 4.0,
        shadow: Some(Shadow { dx: 3.0, dy: 4.0, blur: 3.0, opacity: 0.8 }),
        glow: 0.0,
        glow_color: "#000000".into(),
        shear: Some(0.18),
        font: None,
        plate: 0.0,
    };
    let draw = TextDraw { store, canvas_w, canvas_h };
    let mut l = draw.draw_text(&item, t, "")?;
    // Bob animation
    let phase = (t * 6.28318 * 1.4).sin() as f32;
    l.y_off += (tag.bob * phase).round() as i64;
    // Arrow: small filled triangle under the left edge of the tag
    if tag.arrow {
        let color = hex_to_rgb(&tag.color);
        let size_px = tag.size * (canvas_h as f32 / 1440.0);
        let ax = (tag.x * canvas_w as f32) as i64 - (tag.text.chars().count() as f32 * size_px * 0.30) as i64;
        let ay = (tag.y * canvas_h as f32) as i64 + (size_px * 0.85) as i64 + l.y_off;
        let s = (size_px * 0.36).max(6.0) as i64;
        for row in 0..s {
            let width = (s * (row + 1)) / s.max(1);
            for dx in -width..=width {
                let px = ax + dx;
                let py = ay + row;
                if px < 0 || py < 0 || px >= canvas_w as i64 || py >= canvas_h as i64 { continue; }
                let i = ((py * canvas_w as i64 + px) * 4) as usize;
                l.data[i] = color[0];
                l.data[i + 1] = color[1];
                l.data[i + 2] = color[2];
                l.data[i + 3] = 255;
            }
        }
    }
    Some(l)
}

/// Emoji rendered as white silhouette + glow from an outline emoji font.
pub fn draw_emoji(store: &FontStore, e: &Emoji, t: f64, canvas_w: u32, canvas_h: u32) -> Option<Layer> {
    if t < e.start || t > e.end { return None; }
    let ef = store.emoji.as_ref()?;
    let size_px = e.size * (canvas_h as f32 / 1440.0);
    let sf = ef.font.as_scaled(PxScale::from(size_px));
    let ch = e.char.chars().next()?;
    let gid = sf.glyph_id(ch);
    if gid.0 == 0 { return None; }
    let pos_x = e.x * canvas_w as f32 - size_px * 0.45;
    let pos_y = e.y * canvas_h as f32 + size_px * 0.35;
    let g = gid.with_scale_and_position(sf.scale, ab_glyph::point(pos_x, pos_y));
    let mut layer = Layer::new(canvas_w, canvas_h);
    let og = sf.outline_glyph(g)?;
    let bb = og.px_bounds();
    let bw = bb.width().ceil().max(1.0) as usize;
    let bh = bb.height().ceil().max(1.0) as usize;
    let mut raw = vec![0u8; bw * bh];
    og.draw(|x, y, c| {
        let xi = x as usize;
        let yi = y as usize;
        if xi < bw && yi < bh {
            let i = yi * bw + xi;
            raw[i] = (raw[i] as f32 + c * 255.0).min(255.0) as u8;
        }
    });
    for (i, a) in raw.iter().enumerate() {
        if *a > 0 {
            layer.data[i * 4] = 250;
            layer.data[i * 4 + 1] = 250;
            layer.data[i * 4 + 2] = 250;
            layer.data[i * 4 + 3] = *a;
        }
    }
    if e.glow > 0.5 {
        let alpha: Vec<u8> = (0..bw * bh).map(|i| layer.data[i * 4 + 3]).collect();
        let mut g_alpha = alpha.clone();
        gaussian_blur_u8(&mut g_alpha, layer.w, layer.h, (e.glow * 1.6).round().max(3.0) as usize, e.glow * 0.5, 1);
        for i in 0..bw * bh {
            let a = g_alpha[i];
            if a == 0 { continue; }
            let idx = i * 4;
            let ea = layer.data[idx + 3];
            if ea >= a { continue; }
            layer.data[idx] = layer.data[idx].max(235);
            layer.data[idx + 1] = layer.data[idx + 1].max(235);
            layer.data[idx + 2] = layer.data[idx + 2].max(235);
            layer.data[idx + 3] = a.max(ea);
        }
    }
    Some(layer)
}
