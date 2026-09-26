use serde::Deserialize;
use std::path::{Path, PathBuf};

#[derive(Deserialize, Clone, Debug)]
pub struct Canvas {
    #[serde(default = "d_width")]
    pub width: u32,
    #[serde(default = "d_height")]
    pub height: u32,
    #[serde(default = "d_fps")]
    pub fps: f64,
}
fn d_width() -> u32 { 1080 }
fn d_height() -> u32 { 1920 }
fn d_fps() -> f64 { 60.0 }
impl Default for Canvas {
    fn default() -> Self { Canvas { width: d_width(), height: d_height(), fps: d_fps() } }
}

#[derive(Deserialize, Clone, Debug)]
pub struct Output {
    #[serde(default = "d_crf")]
    pub crf: u8,
    #[serde(default = "d_preset")]
    pub preset: String,
    #[serde(default = "d_abitrate")]
    pub audio_bitrate: String,
}
fn d_crf() -> u8 { 16 }
fn d_preset() -> String { "slow".into() }
fn d_abitrate() -> String { "192k".into() }
impl Default for Output {
    fn default() -> Self { Output { crf: d_crf(), preset: d_preset(), audio_bitrate: d_abitrate() } }
}

/// Global look: applied to every clip frame before overlays.
#[derive(Deserialize, Clone, Debug)]
pub struct Grade {
    #[serde(default = "d_one")]
    pub contrast: f32,
    #[serde(default = "d_one")]
    pub saturation: f32,
    /// Unsharp-mask amount, 0..1.5
    #[serde(default)]
    pub sharpen: f32,
    /// Vignette strength 0..1
    #[serde(default)]
    pub vignette: f32,
    /// Horizontal chromatic aberration in px (R left, B right)
    #[serde(default)]
    pub ca_px: f32,
    /// Preset color tint: none | orange | red_dark | bleach
    #[serde(default)]
    pub tint: String,
}
fn d_one() -> f32 { 1.0 }
impl Default for Grade {
    fn default() -> Self {
        Grade { contrast: 1.0, saturation: 1.0, sharpen: 0.0, vignette: 0.0, ca_px: 0.0, tint: "none".into() }
    }
}

#[derive(Deserialize, Clone, Debug)]
pub struct Watermark {
    pub text: String,
    #[serde(default = "d_wm_size")]
    pub size: f32,
    #[serde(default = "d_wm_y")]
    pub y: f32,
    #[serde(default = "d_wm_color")]
    pub color: String,
    #[serde(default = "d_wm_opacity")]
    pub opacity: f32,
    #[serde(default = "d_wm_outline")]
    pub outline: f32,
    #[serde(default = "d_true")]
    pub shadow: bool,
    #[serde(default = "d_wm_font")]
    pub font: Option<PathBuf>,
}
fn d_wm_size() -> f32 { 34.0 }
fn d_wm_y() -> f32 { 0.845 }
fn d_wm_color() -> String { "#FFFFFF".into() }
fn d_wm_opacity() -> f32 { 0.92 }
fn d_wm_outline() -> f32 { 3.0 }
fn d_true() -> bool { true }
fn d_wm_font() -> Option<PathBuf> { None }

#[derive(Deserialize, Clone, Debug)]
pub struct Clip {
    pub src: PathBuf,
    /// Start time inside the source file (seconds)
    #[serde(rename = "in", default)]
    pub src_in: f64,
    /// Duration on the timeline (seconds)
    pub dur: f64,
    #[serde(default = "d_z1")]
    pub zoom_from: f32,
    #[serde(default = "d_z1")]
    pub zoom_to: f32,
    /// Anchor of the motion crop, fractions of the frame
    #[serde(default = "d_center")]
    pub anchor: [f32; 2],
    /// Per-clip tint override (empty = global tint)
    #[serde(default)]
    pub tint: Option<String>,
    /// Chromatic aberration multiplier for this clip
    #[serde(default = "d_ca1")]
    pub ca_mult: f32,
    /// Zoom-burst (radial blur) frames at clip start
    #[serde(default)]
    pub burst: u32,
    /// Blur + darken the background (ending card look); value = darken 0..1
    #[serde(default)]
    pub blur_darken: Option<f32>,
}
fn d_z1() -> f32 { 1.0 }
fn d_center() -> [f32; 2] { [0.5, 0.5] }
fn d_ca1() -> f32 { 1.0 }

/// Word-level reveal times (seconds relative to `start`). Empty = whole text pops at once.
#[derive(Deserialize, Clone, Debug)]
pub struct TextItem {
    pub id: String,
    /// marker (hand caps, per-letter jitter) | italic (bold oblique + tracking) | impact (heavy glow headline)
    #[serde(default = "d_marker")]
    pub style: String,
    pub text: String,
    /// One color per word (cycles if shorter)
    #[serde(default = "d_colors")]
    pub colors: Vec<String>,
    pub start: f64,
    pub end: f64,
    #[serde(default = "d_half")]
    pub x: f32,
    #[serde(default = "d_half")]
    pub y: f32,
    /// Font size in px at 1080x1440; scales with canvas height
    #[serde(default = "d_text_size")]
    pub size: f32,
    /// Relative word reveal offsets (fraction of (end-start)); ignored if word_starts given
    #[serde(default)]
    pub type_reveal: Option<f64>,
    /// Absolute word reveal offsets in seconds from `start`
    #[serde(default)]
    pub word_starts: Vec<f64>,
    #[serde(default = "d_pop_dur")]
    pub pop_dur: f64,
    #[serde(default)]
    pub wobble: Option<Wobble>,
    /// Per-letter rotation jitter amplitude in degrees (marker style)
    #[serde(default = "d_jitter")]
    pub rotate_jitter_deg: f32,
    /// Letter tracking as a fraction of font size
    #[serde(default)]
    pub tracking: f32,
    /// Outline thickness px
    #[serde(default = "d_stroke")]
    pub stroke: f32,
    #[serde(default)]
    pub shadow: Option<Shadow>,
    /// Glow radius px; 0 = off
    #[serde(default)]
    pub glow: f32,
    /// Glow color
    #[serde(default = "d_glow_color")]
    pub glow_color: String,
    /// Fake italic shear (0..0.35). Default depends on style.
    #[serde(default)]
    pub shear: Option<f32>,
    #[serde(default)]
    pub font: Option<PathBuf>,
    /// Optional solid dark backing plate opacity (0..1)
    #[serde(default)]
    pub plate: f32,
}
fn d_marker() -> String { "marker".into() }
fn d_colors() -> Vec<String> { vec!["#FFFFFF".into()] }
fn d_half() -> f32 { 0.5 }
fn d_text_size() -> f32 { 64.0 }
fn d_pop_dur() -> f64 { 0.26 }
fn d_jitter() -> f32 { 0.0 }
fn d_stroke() -> f32 { 5.0 }
fn d_glow_color() -> String { "#FFFFFF".into() }

#[derive(Deserialize, Clone, Debug)]
pub struct Wobble {
    #[serde(default = "d_amp")]
    pub amp: f32,
    #[serde(default = "d_freq")]
    pub freq: f32,
}
fn d_amp() -> f32 { 4.0 }
fn d_freq() -> f32 { 7.0 }

#[derive(Deserialize, Clone, Debug)]
pub struct Shadow {
    pub dx: f32,
    pub dy: f32,
    pub blur: f32,
    #[serde(default = "d_sh_op")]
    pub opacity: f32,
}
fn d_sh_op() -> f32 { 0.85 }

#[derive(Deserialize, Clone, Debug)]
pub struct NameTag {
    pub text: String,
    pub color: String,
    pub x: f32,
    pub y: f32,
    pub start: f64,
    pub end: f64,
    #[serde(default = "d_true")]
    pub arrow: bool,
    #[serde(default = "d_tag_size")]
    pub size: f32,
    /// Bob animation amplitude px
    #[serde(default = "d_tag_bob")]
    pub bob: f32,
}
fn d_tag_size() -> f32 { 30.0 }
fn d_tag_bob() -> f32 { 3.0 }

#[derive(Deserialize, Clone, Debug)]
pub struct Flash {
    /// red | black | white
    pub kind: String,
    pub start: f64,
    #[serde(default = "d_flash_dur")]
    pub dur: f64,
    /// Peak opacity 0..1 (red/white)
    #[serde(default = "d_flash_peak")]
    pub peak: f32,
}
fn d_flash_dur() -> f64 { 0.3 }
fn d_flash_peak() -> f32 { 0.95 }

#[derive(Deserialize, Clone, Debug)]
pub struct Emoji {
    /// Single-character emoji, e.g. "💀"
    pub char: String,
    pub start: f64,
    pub end: f64,
    #[serde(default = "d_half")]
    pub x: f32,
    #[serde(default = "d_half")]
    pub y: f32,
    #[serde(default = "d_emoji_size")]
    pub size: f32,
    #[serde(default = "d_emoji_glow")]
    pub glow: f32,
    #[serde(default = "d_emoji_font")]
    pub font: Option<PathBuf>,
}
fn d_emoji_size() -> f32 { 140.0 }
fn d_emoji_glow() -> f32 { 16.0 }
fn d_emoji_font() -> Option<PathBuf> { None }

#[derive(Deserialize, Clone, Debug)]
pub struct Audio {
    pub src: PathBuf,
    /// Offset into the audio file (seconds)
    #[serde(default)]
    pub offset: f64,
}

#[derive(Deserialize, Clone, Debug)]
pub struct Template {
    #[serde(default)]
    pub canvas: Canvas,
    #[serde(default)]
    pub output: Output,
    #[serde(default)]
    pub grade: Grade,
    #[serde(default)]
    pub watermark: Option<Watermark>,
    #[serde(default)]
    pub fonts: Fonts,
    #[serde(default)]
    pub clips: Vec<Clip>,
    #[serde(default)]
    pub texts: Vec<TextItem>,
    #[serde(default)]
    pub nametags: Vec<NameTag>,
    #[serde(default)]
    pub flashes: Vec<Flash>,
    #[serde(default)]
    pub emojis: Vec<Emoji>,
    #[serde(default)]
    pub audio: Option<Audio>,
}

#[derive(Deserialize, Clone, Debug, Default)]
pub struct Fonts {
    /// Hand-drawn caps font (Bangers etc.)
    pub marker: Option<PathBuf>,
    /// Bold grotesque for italic/impact (variable Montserrat ok)
    pub sans: Option<PathBuf>,
    /// Emoji outline font (Segoe UI Emoji)
    pub emoji: Option<PathBuf>,
}

impl Template {
    pub fn load(path: &Path) -> anyhow::Result<Template> {
        let raw = std::fs::read_to_string(path)?;
        let mut tpl: Template = serde_json::from_str(&raw)?;
        // Resolve relative paths against the template file location
        let base = path.parent().unwrap_or(Path::new("."));
        let fix = |p: &mut PathBuf| { if p.is_relative() { *p = base.join(&*p); } };
        for c in &mut tpl.clips { fix(&mut c.src); }
        if let Some(a) = &mut tpl.audio { fix(&mut a.src); }
        let f = &mut tpl.fonts;
        if let Some(p) = &mut f.marker { fix(p); }
        if let Some(p) = &mut f.sans { fix(p); }
        if let Some(p) = &mut f.emoji { fix(p); }
        if let Some(w) = &mut tpl.watermark { if let Some(p) = &mut w.font { fix(p); } }
        for t in &mut tpl.texts { if let Some(p) = &mut t.font { fix(p); } }
        for e in &mut tpl.emojis { if let Some(p) = &mut e.font { fix(p); } }
        Ok(tpl)
    }

    pub fn duration(&self) -> f64 {
        self.clips.iter().map(|c| c.dur).sum()
    }
}
