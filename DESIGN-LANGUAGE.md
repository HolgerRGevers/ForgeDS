# ForgeDS Design Language

> Single source of truth for visual identity, interaction patterns, and brand voice across all ForgeDS surfaces.

---

## 1. Brand Identity

### Name

**ForgeDS** -- always written as one word, capital F, capital DS. Never "Forge DS", "forge-ds", or "FDS".

### Tagline

*Shape code like metal.*

### Logo System

The ForgeDS mark is an **anvil with spark** -- a simplified blacksmith's anvil viewed from the front, with a single bright spark flying from the striking face. The anvil communicates craft, durability, and tooling; the spark communicates creation, energy, and the moment of transformation.

Source of truth: `web/src/brand/forgeds-logo-system.jsx` -- a single React + SVG file exporting six components:

| Component | Purpose | Typical use |
|---|---|---|
| `Logomark` | Anvil + spark only, no text | Favicons, small UI slots, loading spinners |
| `Wordmark` | "ForgeDS" typeset text only | Inline references, breadcrumbs |
| `Logo` | Logomark + Wordmark side-by-side | Headers, hero sections |
| `ProfilePic` | Square with rounded corners, dark bg, centred mark | GitHub avatar, npm avatar, social profiles |
| `SocialCard` | 1200 x 630 Open Graph image | Link previews (Twitter, Slack, Discord) |
| `GitHubBanner` | 1280 x 640 repository social preview | GitHub repo "About" image |

#### Construction rules

- The logomark sits on a **64 x 64 grid** with 4 px padding on all sides.
- All geometry is **orthogonal** -- axis-aligned rectangles and simple polygons only. No curves, no beziers, no radii on the anvil body.
- The spark is a **45-degree rotated square** (diamond). Trailing sparks are smaller diamonds on the same 45-degree axis.
- Minimum clear space around the mark equals 25 % of the mark's height on every side.
- Minimum reproduction size: 16 x 16 px (favicon), 24 x 24 px (UI).

#### Colour variants

| Variant | Anvil body | Spark | Text | Use when |
|---|---|---|---|---|
| `color` | Anvil Steel `#4a4d52` | Forge Ember `#c2662d` | Cool Linen `#f0f0ec` | Dark backgrounds (default) |
| `mono-dark` | Anvil Black `#2b2d30` | Anvil Black `#2b2d30` | Anvil Black `#2b2d30` | Light / print backgrounds |
| `mono-light` | Cool Linen `#f0f0ec` | Cool Linen `#f0f0ec` | Cool Linen `#f0f0ec` | Dark overlays, watermarks |

#### Do not

- Rebuild the mark inline -- always import from the source-of-truth file.
- Animate the anvil body. The spark may pulse or fade; the anvil is still.
- Place the mark on a background whose luminance is within 20 % of the anvil body fill.
- Stretch, rotate, or add effects (drop shadow, glow, outline) to the mark.
- Use the old `ForgeDS_IDE` text wordmark anywhere -- it is replaced by `<Logo />`.

---

## 2. Colour Palette -- Anvil Garden

All colours are named after the forge metaphor. Each has a semantic role; do not repurpose.

| Token | Hex | Role |
|---|---|---|
| Anvil Black | `#2b2d30` | Primary background (Workbench), deepest surface |
| Forge Floor | `#363839` | Raised surface, card background, sidebar |
| Anvil Steel | `#4a4d52` | Borders, dividers, inactive icons |
| Cool Tongs | `#6b7280` | Secondary text, placeholder text |
| Worn Metal | `#9ca3af` | Body text on dark surfaces |
| Forge Ember | `#c2662d` | Primary accent, interactive elements, spark |
| Heated Edge | `#e8956a` | Hover / focus state of ember elements |
| Cooling Metal | `#f5c4a1` | Active / pressed state, highlighted text on dark bg |
| Deep Forge | `#7a3d1e` | Ember shadow, dark accent for depth |
| Cool Linen | `#f0f0ec` | Primary text on dark bg, headings |
| Off-White | `#f5f5f2` | Page background (Anvil Garden surface) |

### Tailwind mapping

```js
colors: {
  anvil: { black: "#2b2d30", steel: "#4a4d52", floor: "#363839" },
  forge: { ember: "#c2662d", floor: "#363839", deep: "#7a3d1e" },
  ember: { DEFAULT: "#c2662d", heated: "#e8956a", cooling: "#f5c4a1" },
  linen: { DEFAULT: "#f0f0ec", off: "#f5f5f2", bench: "#e5e5e0" },
}
```

---

## 3. Typography

### Font stack

| Role | Family | Fallback | CSS custom property |
|---|---|---|---|
| Sans (UI, prose) | Geist | ui-sans-serif, system-ui, sans-serif | `--font-sans` |
| Mono (code, data) | Geist Mono | ui-monospace, SFMono-Regular, Menlo, Consolas, monospace | `--font-mono` |

Both fonts are sourced from [vercel/geist-font](https://github.com/vercel/geist-font) under the SIL Open Font License. Variable TTF files are served from `web/public/fonts/`.

### Type scale

| Name | Size | Weight | Line-height | Use |
|---|---|---|---|---|
| Display | 2rem / 32 px | 600 | 1.2 | Hero headings, landing page |
| Title | 1.25rem / 20 px | 600 | 1.3 | Page headings, card titles |
| Body | 0.875rem / 14 px | 400 | 1.5 | Default UI text |
| Caption | 0.75rem / 12 px | 400 | 1.4 | Labels, timestamps, metadata |
| Mono body | 0.8125rem / 13 px | 400 | 1.6 | Code editor, terminal output |

### Rules

- Never use font weights below 400 or above 700 in the IDE.
- Wordmark uses weight 500, letter-spacing `0.02em` for "Forge" and `0.04em` for "DS".
- Code blocks and the Monaco editor always use `--font-mono`.

---

## 4. Surface Modes

ForgeDS has two visual surfaces. Every screen belongs to exactly one.

### Workbench (IDE)

- Background: Anvil Black `#2b2d30`
- Raised panels: Forge Floor `#363839`
- Text: Cool Linen `#f0f0ec` (primary), Worn Metal `#9ca3af` (secondary)
- Accent: Forge Ember `#c2662d`
- Density: compact (4 px / 8 px spacing grid)
- Applies to: IDE editor, file tree, terminal, prompt panel, database viewer, API builder

### Anvil Garden (brand / docs)

- Background: Off-White `#f5f5f2`
- Cards: white `#ffffff` with 1 px Anvil Steel border
- Text: Anvil Black `#2b2d30` (primary), Cool Tongs `#6b7280` (secondary)
- Accent: Forge Ember `#c2662d`
- Density: generous (8 px / 16 px spacing grid)
- Applies to: landing page, documentation, GitHub Pages, README renders

### Switching rule

A component never mixes surfaces. If a Workbench component must appear inside an Anvil Garden page (e.g. an embedded code preview), it sits inside a contained panel with its own Anvil Black background.

---

## 5. Spacing and Layout

| Token | Value | Use |
|---|---|---|
| `space-1` | 4 px | Inline gaps, icon padding |
| `space-2` | 8 px | Between related elements |
| `space-3` | 12 px | Section padding (Workbench) |
| `space-4` | 16 px | Section padding (Anvil Garden) |
| `space-6` | 24 px | Card padding, panel margins |
| `space-8` | 32 px | Page-level spacing |

Border radius:
- Buttons, inputs: `4px` (`rounded`)
- Cards, panels: `8px` (`rounded-lg`)
- Pills, badges: `9999px` (`rounded-full`)
- Logomark containers: `18%` (squircle for profile pics)

---

## 6. Interactive Patterns

### Buttons

| Variant | Background | Text | Border | Use |
|---|---|---|---|---|
| Primary | Forge Ember | Cool Linen | none | Main CTA |
| Secondary | transparent | Worn Metal | 1 px Anvil Steel | Alternative actions |
| Ghost | transparent | Worn Metal | none | Toolbar actions, icon buttons |
| Danger | `#dc2626` | white | none | Destructive actions |

Hover: lighten background 10 %. Focus: 2 px ring in Forge Ember at 50 % opacity. Disabled: 40 % opacity, no pointer events.

### Bridge Pill

The connection status indicator in the IDE header. Three states:

| State | Dot | Label | Tooltip |
|---|---|---|---|
| Local | green | "Local" | "Bridge connected at localhost:9876 -- full write access" |
| Connecting | yellow, pulsing | "Connecting..." | "Attempting to reach local bridge..." |
| Offline | red | "Offline" | "No connection -- cached files only, changes queued locally" |

Container: `rounded-full bg-gray-700 px-2 py-0.5 text-xs`. Clickable when offline (retries bridge connection).

---

## 7. Voice and Tone

### Personality

ForgeDS speaks like a **senior colleague who respects your time** -- direct, precise, occasionally dry. It assumes competence and avoids hand-holding.

### Writing rules

- Use sentence case for headings and labels (not Title Case).
- Prefer active voice and imperative mood in UI copy ("Save changes", not "Your changes will be saved").
- Error messages state what happened, then what to do: "Bridge disconnected. Click to retry."
- Never use "please", "sorry", or exclamation marks in system UI text.
- Tooltips are one sentence, no trailing period.
- Use en-dashes for ranges (2--4 px), em-dashes for asides -- like this.

### Naming conventions

- Features are named after forge tools: Bridge (local connection), Anvil (editor), Crucible (build), Tongs (file operations).
- Avoid generic tech jargon ("dashboard", "hub", "portal") -- prefer the forge metaphor or plain description.

---

## 8. Iconography

- Primary icon set: [Lucide](https://lucide.dev/) at 16 px (Workbench) / 20 px (Anvil Garden).
- Stroke width: 1.5 px (Workbench), 2 px (Anvil Garden).
- Icon colour follows text colour of context (Cool Linen on dark, Anvil Black on light).
- Custom icons (anvil, spark, bridge) live alongside the logo system in `web/src/brand/`.

---

## 9. Motion

- Duration: 150 ms for micro-interactions, 300 ms for panel transitions.
- Easing: `cubic-bezier(0.4, 0, 0.2, 1)` (Tailwind `ease-in-out`).
- The spark in the logomark may animate (fade-in, pulse) on page load. The anvil body never animates.
- Skeleton loaders use a shimmer from Forge Floor to Anvil Steel.
- Prefer opacity transitions over layout shifts.

---

## 10. Accessibility

- All interactive elements must meet WCAG 2.1 AA contrast ratios (4.5:1 for text, 3:1 for large text and UI components).
- Forge Ember on Anvil Black = 4.8:1 (passes AA).
- Cool Linen on Anvil Black = 13.2:1 (passes AAA).
- Focus indicators: 2 px ring in Forge Ember at 50 % opacity, offset 2 px.
- All SVG icons carry `aria-hidden="true"`; accompanying text provides the label.
- The Bridge Pill includes `title` tooltips for screen readers.

---

## 11. File References

- Logo system (source of truth): `web/src/brand/forgeds-logo-system.jsx`
- Tailwind tokens: `web/tailwind.config.js`
- Font files: `web/public/fonts/` (Geist-Variable.ttf, GeistMono-Variable.ttf, OFL.txt)
- CSS custom properties: `web/src/index.css`
- Favicon: `web/public/favicon.svg`
- This document: `DESIGN-LANGUAGE.md`
