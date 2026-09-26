use rayon::prelude::*;

/// RGB24 frame buffer.
#[derive(Clone)]
pub struct Frame {
    pub w: u32,
    pub h: u32,
    pub data: Vec<u8>,
}

impl Frame {
    pub fn new(w: u32, h: u32) -> Self {
        Frame { w, h, data: vec![0u8; (w * h * 3) as usize] }
    }

    #[inline]
    fn px(&self, x: i64, y: i64) -> [f32; 3] {
        let x = x.clamp(0, self.w as i64 - 1) as usize;
        let y = y.clamp(0, self.h as i64 - 1) as usize;
        let i = (y * self.w as usize + x) * 3;
        [self.data[i] as f32, self.data[i + 1] as f32, self.data[i + 2] as f32]
    }

    /// Bilinear sample in normalized source coords.
    #[inline]
    fn sample(&self, fx: f32, fy: f32) -> [f32; 3] {
        let x = (fx * self.w as f32 - 0.5).max(-1.0);
        let y = (fy * self.h as f32 - 0.5).max(-1.0);
        let x0 = x.floor() as i64;
        let y0 = y.floor() as i64;
        let tx = x - x0 as f32;
        let ty = y - y0 as f32;
        let a = self.px(x0, y0);
        let b = self.px(x0 + 1, y0);
        let c = self.px(x0, y0 + 1);
        let d = self.px(x0 + 1, y0 + 1);
        let mut out = [0f32; 3];
        for k in 0..3 {
            let top = a[k] * (1.0 - tx) + b[k] * tx;
            let bot = c[k] * (1.0 - tx) + d[k] * tx;
            out[k] = top * (1.0 - ty) + bot * ty;
        }
        out
    }

    /// Motion crop+scale: sample a `zoom`-cropped window (anchored at ax, ay) into a new canvas-size frame.
    pub fn motion_resample(&self, zoom: f32, ax: f32, ay: f32, out_w: u32, out_h: u32) -> Frame {
        let mut out = Frame::new(out_w, out_h);
        // Crop window size in source pixels (window aspect follows output aspect)
        let win_w = self.w as f32 / zoom;
        let win_h = win_w * (out_h as f32 / out_w as f32);
        let win_h = if win_h > self.h as f32 {
            self.h as f32
        } else {
            win_h
        };
        let win_w = if win_h * (out_w as f32 / out_h as f32) < win_w && win_h < self.h as f32 {
            win_h * (out_w as f32 / out_h as f32)
        } else {
            win_w
        };
        let x0 = (self.w as f32 - win_w) * ax.clamp(0.0, 1.0);
        let y0 = (self.h as f32 - win_h) * ay.clamp(0.0, 1.0);
        let rows = out_h as usize;
        let ow = out_w as f32;
        let oh = out_h as f32;
        out.data
            .par_chunks_exact_mut((out_w * 3) as usize)
            .enumerate()
            .for_each(|(cy, row)| {
                let fy = (cy as f32 + 0.5) / oh;
                for cx in 0..out_w as usize {
                    let fx = (cx as f32 + 0.5) / ow;
                    let sx = (x0 + fx * win_w) / self.w as f32;
                    let sy = (y0 + fy * win_h) / self.h as f32;
                    let p = self.sample(sx, sy);
                    row[cx * 3] = p[0].clamp(0.0, 255.0) as u8;
                    row[cx * 3 + 1] = p[1].clamp(0.0, 255.0) as u8;
                    row[cx * 3 + 2] = p[2].clamp(0.0, 255.0) as u8;
                }
            });
        let _ = rows;
        out
    }

    /// Zoom-burst: blend several zoomed copies around the anchor (cheap radial motion blur).
    pub fn zoom_burst(&self, zoom: f32, ax: f32, ay: f32, steps: u32, out_w: u32, out_h: u32) -> Frame {
        let mut acc = vec![0f32; (out_w * out_h * 3) as usize];
        let n = steps.max(2);
        let mut weights = 0f32;
        for s in 0..n {
            let z = zoom * (1.0 + 0.028 * s as f32);
            let f = 1.0 - s as f32 / n as f32;
            weights += f;
            let fr = self.motion_resample(z, ax, ay, out_w, out_h);
            for (a, v) in acc.iter_mut().zip(fr.data.iter()) {
                *a += *v as f32 * f;
            }
        }
        let mut out = Frame::new(out_w, out_h);
        for (o, a) in out.data.iter_mut().zip(acc.iter()) {
            *o = (*a / weights).clamp(0.0, 255.0) as u8;
        }
        out
    }

    pub fn chromatic_shift(&mut self, px: f32) {
        if px.abs() < 0.05 { return; }
        let d = px.round() as i64;
        if d == 0 { return; }
        let (w, h) = (self.w as i64, self.h as i64);
        let wu = self.w as usize;
        let src = self.data.clone();
        let shifted: Vec<u8> = (0..h as usize)
            .into_par_iter()
            .flat_map_iter(|y| {
                let mut row = vec![0u8; wu * 3];
                for x in 0..wu as i64 {
                    let i = x as usize * 3;
                    let xr = (x - d).clamp(0, w - 1) as usize;
                    let xb = (x + d).clamp(0, w - 1) as usize;
                    row[i] = src[(y * wu + xr) * 3];
                    row[i + 1] = src[(y * wu + x as usize) * 3 + 1];
                    row[i + 2] = src[(y * wu + xb) * 3 + 2];
                }
                row
            })
            .collect();
        let _ = wu;
        self.data = shifted;
    }

    /// Unsharp mask (radius ~1px gaussian).
    pub fn unsharp(&mut self, amount: f32) {
        if amount <= 0.001 { return; }
        let mut blur = self.data.clone();
        gaussian_blur_u8(&mut blur, self.w, self.h, 3, 0.9, 3);
        for (p, b) in self.data.iter_mut().zip(blur.iter()) {
            let v = *p as f32 + amount * (*p as f32 - *b as f32);
            *p = v.clamp(0.0, 255.0) as u8;
        }
    }

    pub fn grade(&mut self, contrast: f32, saturation: f32, tint: &str) {
        let c = contrast;
        let s = saturation;
        let tint = tint.to_ascii_lowercase();
        self.data.par_chunks_exact_mut(3).for_each(|px| {
            let mut r = px[0] as f32 / 255.0;
            let mut g = px[1] as f32 / 255.0;
            let mut b = px[2] as f32 / 255.0;
            // contrast around mid grey
            r = (r - 0.5) * c + 0.5;
            g = (g - 0.5) * c + 0.5;
            b = (b - 0.5) * c + 0.5;
            // saturation around luma
            let l = 0.2126 * r + 0.7152 * g + 0.0722 * b;
            r = l + (r - l) * s;
            g = l + (g - l) * s;
            b = l + (b - l) * s;
            match tint.as_str() {
                "orange" => {
                    // teal shadows / orange highlights
                    let hi = l.clamp(0.0, 1.0);
                    let lo = 1.0 - hi;
                    r = r * (1.0 + 0.16 * hi) + 0.05 * lo * 0.4;
                    g = g * (1.0 + 0.02 * hi);
                    b = b * (1.0 - 0.10 * hi) + 0.06 * lo;
                }
                "red_dark" => {
                    r = r * 1.06 + 0.02;
                    g = g * 0.52;
                    b = b * 0.52;
                }
                "bleach" => {
                    r = r * 0.92 + 0.10;
                    g = g * 0.92 + 0.10;
                    b = b * 0.94 + 0.08;
                }
                _ => {}
            }
            px[0] = (r.clamp(0.0, 1.0) * 255.0) as u8;
            px[1] = (g.clamp(0.0, 1.0) * 255.0) as u8;
            px[2] = (b.clamp(0.0, 1.0) * 255.0) as u8;
        });
    }

    pub fn vignette(&mut self, strength: f32) {
        if strength <= 0.001 { return; }
        let (w, h) = (self.w as f32, self.h as f32);
        let cx = w * 0.5;
        let cy = h * 0.5;
        let maxr = (cx * cx + cy * cy).sqrt();
        let s = strength;
        let wu = self.w as usize;
        self.data
            .par_chunks_exact_mut(wu * 3)
            .enumerate()
            .for_each(|(y, row)| {
                let dy = y as f32 - cy;
                for x in 0..wu {
                    let dx = x as f32 - cx;
                    let r = (dx * dx + dy * dy).sqrt() / maxr;
                    let f = 1.0 - s * r.powf(1.6);
                    let i = x * 3;
                    row[i] = (row[i] as f32 * f) as u8;
                    row[i + 1] = (row[i + 1] as f32 * f) as u8;
                    row[i + 2] = (row[i + 2] as f32 * f) as u8;
                }
            });
    }

    /// Blur + darken the whole frame (used behind the ending card).
    pub fn blur_darken(&mut self, blur_px: f32, darken: f32) {
        gaussian_blur_u8(&mut self.data, self.w, self.h, (blur_px * 2.0).round().max(3.0) as usize, blur_px * 0.6, 3);
        for p in self.data.iter_mut() {
            *p = (*p as f32 * (1.0 - darken)) as u8;
        }
    }

    /// Alpha-blend an RGBA layer over this frame.
    pub fn blend_layer(&mut self, layer: &Layer) {
        let lw = layer.w as usize;
        for y in 0..self.h as usize {
            let fy = y as i64 + layer.y_off as i64;
            if fy < 0 || fy >= self.h as i64 { continue; }
            for x in 0..lw {
                let fx = x as i64 + layer.x_off as i64;
                if fx < 0 || fx >= self.w as i64 { continue; }
                let li = (y * lw + x) * 4;
                let a = layer.data[li + 3] as f32 / 255.0;
                if a <= 0.0 { continue; }
                let fi = (fy as usize * self.w as usize + fx as usize) * 3;
                for k in 0..3 {
                    let dst = self.data[fi + k] as f32;
                    let src = layer.data[li + k] as f32;
                    self.data[fi + k] = (src * a + dst * (1.0 - a)).round() as u8;
                }
            }
        }
    }

    /// Alpha-blend a layer scaled by `scale` around pivot (cx, cy) in frame coords,
    /// plus integer offset (dx, dy). Uses bounding-box clipping and bilinear filtering
    /// for smooth subpixel scaling without jagged nearest-neighbor artifacts.
    pub fn blend_layer_scaled(&mut self, layer: &Layer, scale: f32, cx: f32, cy: f32, dx: i64, dy: i64) {
        if (scale - 1.0).abs() < 0.002 {
            let shifted = Layer {
                w: layer.w,
                h: layer.h,
                x_off: layer.x_off + dx,
                y_off: layer.y_off + dy,
                data: layer.data.clone(),
            };
            self.blend_layer(&shifted);
            return;
        }
        if scale <= 0.001 || layer.w == 0 || layer.h == 0 {
            return;
        }
        let inv = 1.0 / scale;
        let lw = layer.w as f32;
        let lh = layer.h as f32;

        let l_min_x = layer.x_off as f32 + dx as f32;
        let l_max_x = l_min_x + lw;
        let l_min_y = layer.y_off as f32 + dy as f32;
        let l_max_y = l_min_y + lh;

        let dst_min_x = (((l_min_x - cx) * scale + cx).floor() as i64).clamp(0, self.w as i64 - 1);
        let dst_max_x = (((l_max_x - cx) * scale + cx).ceil() as i64).clamp(0, self.w as i64 - 1);
        let dst_min_y = (((l_min_y - cy) * scale + cy).floor() as i64).clamp(0, self.h as i64 - 1);
        let dst_max_y = (((l_max_y - cy) * scale + cy).ceil() as i64).clamp(0, self.h as i64 - 1);

        let l_stride = layer.w as usize;
        let d_stride = self.w as usize;

        for fy in dst_min_y..=dst_max_y {
            let fyd = fy as f32 + 0.5;
            let src_y = (fyd - cy) * inv + cy - l_min_y - 0.5;
            if src_y < -0.5 || src_y >= lh - 0.5 {
                continue;
            }
            let y0 = src_y.floor() as i64;
            let y1 = y0 + 1;
            let fy_frac = src_y - y0 as f32;
            let cy0 = y0.clamp(0, layer.h as i64 - 1) as usize;
            let cy1 = y1.clamp(0, layer.h as i64 - 1) as usize;

            for fx in dst_min_x..=dst_max_x {
                let fxd = fx as f32 + 0.5;
                let src_x = (fxd - cx) * inv + cx - l_min_x - 0.5;
                if src_x < -0.5 || src_x >= lw - 0.5 {
                    continue;
                }
                let x0 = src_x.floor() as i64;
                let x1 = x0 + 1;
                let fx_frac = src_x - x0 as f32;
                let cx0 = x0.clamp(0, layer.w as i64 - 1) as usize;
                let cx1 = x1.clamp(0, layer.w as i64 - 1) as usize;

                let idx00 = (cy0 * l_stride + cx0) * 4;
                let idx10 = (cy0 * l_stride + cx1) * 4;
                let idx01 = (cy1 * l_stride + cx0) * 4;
                let idx11 = (cy1 * l_stride + cx1) * 4;

                let a00 = layer.data[idx00 + 3] as f32;
                let a10 = layer.data[idx10 + 3] as f32;
                let a01 = layer.data[idx01 + 3] as f32;
                let a11 = layer.data[idx11 + 3] as f32;

                let w00 = (1.0 - fx_frac) * (1.0 - fy_frac);
                let w10 = fx_frac * (1.0 - fy_frac);
                let w01 = (1.0 - fx_frac) * fy_frac;
                let w11 = fx_frac * fy_frac;

                let a = (a00 * w00 + a10 * w10 + a01 * w01 + a11 * w11) / 255.0;
                if a <= 0.002 {
                    continue;
                }

                let fi = (fy as usize * d_stride + fx as usize) * 3;
                let inv_a = 1.0 - a;

                for k in 0..3 {
                    let c00 = layer.data[idx00 + k] as f32;
                    let c10 = layer.data[idx10 + k] as f32;
                    let c01 = layer.data[idx01 + k] as f32;
                    let c11 = layer.data[idx11 + k] as f32;
                    let src_col = c00 * w00 + c10 * w10 + c01 * w01 + c11 * w11;
                    let dst_col = self.data[fi + k] as f32;
                    self.data[fi + k] = (src_col * a + dst_col * inv_a).round().clamp(0.0, 255.0) as u8;
                }
            }
        }
    }

    /// Solid color overlay with alpha.
    pub fn overlay_solid(&mut self, color: [u8; 3], alpha: f32) {
        if alpha <= 0.0 { return; }
        for p in self.data.chunks_exact_mut(3) {
            for k in 0..3 {
                p[k] = (color[k] as f32 * alpha + p[k] as f32 * (1.0 - alpha)).round() as u8;
            }
        }
    }
}

/// Float RGBA layer for text/graphics compositing.
pub struct Layer {
    pub w: u32,
    pub h: u32,
    pub x_off: i64,
    pub y_off: i64,
    pub data: Vec<u8>, // RGBA8
}

impl Layer {
    pub fn new(w: u32, h: u32) -> Self {
        Layer { w, h, x_off: 0, y_off: 0, data: vec![0u8; (w * h * 4) as usize] }
    }
    pub fn clear(&mut self) { self.data.fill(0); }
    #[inline]
    pub fn alpha_at(&self, x: usize, y: usize) -> u8 { self.data[(y * self.w as usize + x) * 4 + 3] }
    #[inline]
    pub fn set(&mut self, x: usize, y: usize, color: [u8; 3], a: u8) {
        if x >= self.w as usize || y >= self.h as usize { return; }
        let i = (y * self.w as usize + x) * 4;
        self.data[i] = color[0];
        self.data[i + 1] = color[1];
        self.data[i + 2] = color[2];
        self.data[i + 3] = a;
    }
}

/// Separable gaussian blur over interleaved u8 data with arbitrary channel count.
pub fn gaussian_blur_u8(data: &mut [u8], w: u32, h: u32, radius: usize, sigma: f32, channels: usize) {
    if radius < 1 || sigma <= 0.01 || channels == 0 { return; }
    if data.len() < (w as usize) * (h as usize) * channels { return; }
    let r = radius as i64;
    let mut kernel = Vec::with_capacity((2 * r + 1) as usize);
    let mut sum = 0f32;
    for i in -r..=r {
        let v = (-(*&i as f32).powi(2) / (2.0 * sigma * sigma)).exp();
        kernel.push(v);
        sum += v;
    }
    for k in kernel.iter_mut() { *k /= sum; }
    let (wu, hu) = (w as usize, h as usize);
    let mut tmp = vec![0u8; data.len()];
    // horizontal
    tmp.par_chunks_exact_mut(wu * channels).enumerate().for_each(|(y, row)| {
        let src = &data[y * wu * channels..(y + 1) * wu * channels];
        for x in 0..wu {
            for c in 0..channels {
                let mut acc = 0f32;
                for (ki, k) in kernel.iter().enumerate() {
                    let sx = (x as i64 + ki as i64 - r).clamp(0, wu as i64 - 1) as usize;
                    acc += src[sx * channels + c] as f32 * k;
                }
                row[x * channels + c] = acc.clamp(0.0, 255.0) as u8;
            }
        }
    });
    // vertical
    data.par_chunks_exact_mut(wu * channels).enumerate().for_each(|(y, row)| {
        for x in 0..wu {
            for c in 0..channels {
                let mut acc = 0f32;
                for (ki, k) in kernel.iter().enumerate() {
                    let sy = (y as i64 + ki as i64 - r).clamp(0, hu as i64 - 1) as usize;
                    acc += tmp[sy * wu * channels + x * channels + c] as f32 * k;
                }
                row[x * channels + c] = acc.clamp(0.0, 255.0) as u8;
            }
        }
    });
}

/// Euclidean circular dilation over alpha channel stored in an RGBA layer (stride 4, ch 3).
/// Eliminates square box corners and gives smooth, rounded strokes.
pub fn dilate_alpha(layer: &Layer, radius: usize) -> Vec<u8> {
    let wu = layer.w as usize;
    let hu = layer.h as usize;
    let mut out = vec![0u8; wu * hu];
    if radius == 0 || wu == 0 || hu == 0 {
        return (0..wu * hu).map(|i| layer.data[i * 4 + 3]).collect();
    }
    let alpha: Vec<u8> = (0..wu * hu).map(|i| layer.data[i * 4 + 3]).collect();
    let r = radius as i64;
    let r2 = r * r;

    // Precompute circle offsets (dx, dy)
    let mut offsets = Vec::new();
    for dy in -r..=r {
        for dx in -r..=r {
            if dx * dx + dy * dy <= r2 {
                offsets.push((dx, dy));
            }
        }
    }

    out.par_chunks_exact_mut(wu).enumerate().for_each(|(y, row)| {
        for x in 0..wu {
            let mut m = 0u8;
            for &(dx, dy) in &offsets {
                let sy = (y as i64 + dy).clamp(0, hu as i64 - 1) as usize;
                let sx = (x as i64 + dx).clamp(0, wu as i64 - 1) as usize;
                let val = alpha[sy * wu + sx];
                if val > m {
                    m = val;
                    if m == 255 { break; }
                }
            }
            row[x] = m;
        }
    });
    out
}
