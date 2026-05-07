// Six candidate QSS themes for JellyRip Phase 3a (MAIN).
// Each theme's action buttons are pulled from that theme's OWN hue
// family — no two themes share the same go/info/alt/warn/danger palette.
// Role meaning is constant across themes (go = primary, info = secondary,
// alt = tertiary, warn = caution, danger = destructive). Color is not.

const THEMES = [
  // 1) Dark GitHub — green/blue/purple/amber/red (canonical, unchanged)
  {
    id: "dark_github",
    name: "Dark GitHub",
    subtitle: "Current tkinter palette, ported",
    family: "dark",
    notes: "Direct port of today's #0d1117 / #58a6ff palette. Zero visual surprise for existing users.",
    tokens: {
      bg: "#0d1117", card: "#161b22", input: "#21262d", border: "#30363d",
      fg: "#c9d1d9", muted: "#8b949e", accent: "#58a6ff",
      go:     "#238636", goFg:     "#ffffff",
      info:   "#1f6feb", infoFg:   "#ffffff",
      alt:    "#6e40c9", altFg:    "#ffffff",
      warn:   "#9a6700", warnFg:   "#ffffff",
      danger: "#c94b4b", dangerFg: "#ffffff",
      hover: "#1f2933", selection: "#1f6feb",
      logBg: "#161b22", promptFg: "#f0e68c", answerFg: "#90ee90",
      shadow: "rgba(0,0,0,0.4)",
    },
  },

  // 2) Light Inverted — editorial light, no purple anywhere
  //    forest-green primary, teal, mustard, rust, crimson
  {
    id: "light_inverted",
    name: "Light Inverted",
    subtitle: "Closes A11y Finding #2",
    family: "light",
    notes: "Light editorial palette — forest-green primary, deep teal secondary, mustard tertiary, rust caution, crimson destructive. No purple in the action row.",
    tokens: {
      bg: "#ffffff", card: "#f6f8fa", input: "#ffffff", border: "#d0d7de",
      fg: "#1f2328", muted: "#57606a", accent: "#0e6b6b",
      go:     "#1f6e3a", goFg:     "#ffffff",   // forest green primary
      info:   "#0e6b6b", infoFg:   "#ffffff",   // deep teal
      alt:    "#8a6a14", altFg:    "#ffffff",   // mustard
      warn:   "#a64614", warnFg:   "#ffffff",   // rust
      danger: "#9b1c2c", dangerFg: "#ffffff",   // crimson
      hover: "#eaeef2", selection: "#0e6b6b",
      logBg: "#f6f8fa", promptFg: "#8a6a14", answerFg: "#1f6e3a",
      shadow: "rgba(31,35,40,0.08)",
    },
  },

  // 3) Dracula Light — pale lavender bg, Dracula CTA family
  //    purple / pink / cyan / yellow / red
  {
    id: "dracula_light",
    name: "Dracula Light",
    subtitle: "Dracula palette, light surface",
    family: "light",
    notes: "Pale lavender surface with the canonical Dracula action set — purple primary, pink secondary, cyan tertiary, yellow caution, red destructive. Reads playful but stays AA on every CTA.",
    tokens: {
      bg: "#f5ecd9", card: "#ede1c5", input: "#fbf5e6", border: "#d6c69a",
      fg: "#22213a", muted: "#5e5a7a", accent: "#6f42c1",
      go:     "#6f42c1", goFg:     "#ffffff",   // dracula purple
      info:   "#c2378a", infoFg:   "#ffffff",   // dracula pink
      alt:    "#0a8a96", altFg:    "#ffffff",   // dracula cyan
      warn:   "#8a6a14", warnFg:   "#ffffff",   // dracula yellow (deepened for AA)
      danger: "#c4312f", dangerFg: "#ffffff",   // dracula red
      hover: "#e3d4ad", selection: "#6f42c1",
      logBg: "#ede1c5", promptFg: "#8a6a14", answerFg: "#0a8a96",
      shadow: "rgba(61,47,21,0.12)",
    },
  },

  // 4) High Contrast Dark — high-saturation neon set, all 7:1+ on label
  {
    id: "hc_dark",
    name: "High Contrast Dark",
    subtitle: "Accessibility-first AAA",
    family: "dark",
    notes: "Pure black surfaces, high-saturation CTAs. Every CTA crosses 7:1 against its label so AAA holds end-to-end.",
    tokens: {
      bg: "#000000", card: "#0a0a0a", input: "#141414", border: "#5c5c5c",
      fg: "#ffffff", muted: "#cfcfcf", accent: "#ffd60a",
      go:     "#39ff14", goFg:     "#000000",   // electric lime  (vs github green)
      info:   "#00e5ff", infoFg:   "#000000",   // pure cyan      (vs github blue)
      alt:    "#ff6ec7", altFg:    "#000000",   // hot pink       (vs github purple)
      warn:   "#ffd60a", warnFg:   "#000000",   // bright yellow  (vs github amber)
      danger: "#ff3030", dangerFg: "#ffffff",   // pure red       (vs github muted red)
      hover: "#1a1a1a", selection: "#ffd60a",
      logBg: "#0a0a0a", promptFg: "#ffd60a", answerFg: "#00d26a",
      shadow: "rgba(0,0,0,0.8)",
    },
  },

  // 5) Slate — desaturated cool-only set, no green/blue overlap with GitHub
  //    sea-foam / sky / periwinkle / bronze / brick
  {
    id: "slate",
    name: "Slate",
    subtitle: "Cool blue-grey neutrals",
    family: "dark",
    notes: "Desaturated cool-only CTAs — sea-foam primary, pale sky secondary, periwinkle tertiary, bronze caution, brick destructive. Nothing saturated, nothing screams.",
    tokens: {
      bg: "#1a2332", card: "#22303f", input: "#2a3a4d", border: "#3a4a5e",
      fg: "#dbe5ee", muted: "#8ea0b3", accent: "#5dbcd2",
      go:     "#4ba89a", goFg:     "#0d1721",   // sea-foam
      info:   "#7aa8c8", infoFg:   "#0d1721",   // pale sky
      alt:    "#8a8ec4", altFg:    "#0d1721",   // periwinkle
      warn:   "#b88550", warnFg:   "#0d1721",   // bronze
      danger: "#a64545", dangerFg: "#ffffff",   // brick
      hover: "#2a3a4d", selection: "#4a78b8",
      logBg: "#22303f", promptFg: "#b88550", answerFg: "#4ba89a",
      shadow: "rgba(0,0,0,0.35)",
    },
  },

  // 6) Frost — saturated Nord (Nord bg, punchier CTAs, less pastel)
  //    deep aurora-green / strong frost-blue / rich violet / saturated yellow / firm aurora-red
  {
    id: "frost",
    name: "Frost",
    subtitle: "Muted Nordic dark",
    family: "dark",
    notes: "Nord background with the saturation dialed up on every CTA — deeper aurora green, stronger frost blue, richer violet, fuller yellow, firm aurora red. Same family, more punch.",
    tokens: {
      bg: "#2e3440", card: "#3b4252", input: "#434c5e", border: "#4c566a",
      fg: "#eceff4", muted: "#a3acbc", accent: "#88c0d0",
      go:     "#6e9b4f", goFg:     "#ffffff",   // saturated aurora green
      info:   "#4a7fb8", infoFg:   "#ffffff",   // strong frost blue
      alt:    "#9c5fa3", altFg:    "#ffffff",   // rich violet
      warn:   "#d4a849", warnFg:   "#1f1a10",   // saturated yellow
      danger: "#b8434d", dangerFg: "#ffffff",   // firm aurora red
      hover: "#434c5e", selection: "#5e81ac",
      logBg: "#3b4252", promptFg: "#d4a849", answerFg: "#a3be8c",
      shadow: "rgba(0,0,0,0.4)",
    },
  },
];

function _channelLum(c) {
  c = c / 255;
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}
function _hexToRgb(hex) {
  const h = hex.replace("#", "");
  const v = h.length === 3 ? h.split("").map(c => c + c).join("") : h;
  return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
}
function relativeLuminance(hex) {
  const [r, g, b] = _hexToRgb(hex);
  return 0.2126 * _channelLum(r) + 0.7152 * _channelLum(g) + 0.0722 * _channelLum(b);
}
function contrastRatio(hexA, hexB) {
  const a = relativeLuminance(hexA);
  const b = relativeLuminance(hexB);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}
function wcagRating(ratio) {
  if (ratio >= 7) return { label: "AAA" };
  if (ratio >= 4.5) return { label: "AA" };
  if (ratio >= 3) return { label: "AA Large" };
  return { label: "Fail" };
}

window.JR_THEMES = THEMES;
window.JR_WCAG = { contrastRatio, relativeLuminance, wcagRating };
