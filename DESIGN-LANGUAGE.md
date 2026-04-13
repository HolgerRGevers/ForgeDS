# ForgeDS Design Language

A formal design system for ForgeDS tools, the ForgeDS IDE, and Zoho Creator applications built with ForgeDS.

---

## Principles

1. **Dark-first IDE aesthetic** -- optimized for extended screen time, reduces eye strain
2. **Information density over whitespace** -- every pixel earns its place; no decorative padding
3. **Blue accent for interactivity** -- interactive elements use the blue spectrum; static content uses gray
4. **Semantic color coding** -- green = success/connected, yellow = warning/pending, red = error/destructive
5. **Subtle depth hierarchy** -- backgrounds darken as you go deeper (950 > 900 > 800)
6. **Monospace for code, sans-serif for UI** -- never mix fonts within a context
7. **Touch-ready targets** -- minimum 32px hit targets on mobile, 28px on desktop
8. **Responsive collapse** -- panels fold gracefully from desktop multi-column to mobile single-column

---

## Color Tokens

### Backgrounds
| Token | Hex | Usage |
|-------|-----|-------|
| `bg-primary` | `#030712` (gray-950) | Page background, main content |
| `bg-secondary` | `#111827` (gray-900) | Sidebars, cards, panels |
| `bg-elevated` | `#1f2937` (gray-800) | Header, toolbar, elevated surfaces |
| `bg-surface` | `#374151` (gray-700) | Inputs, dropdowns, hover states |
| `bg-editor` | `#0a0a0f` | Monaco editor background |

### Text
| Token | Hex | Usage |
|-------|-----|-------|
| `text-primary` | `#f3f4f6` (gray-100) | Headings, active labels |
| `text-secondary` | `#d1d5db` (gray-300) | Body text, descriptions |
| `text-tertiary` | `#9ca3af` (gray-400) | Placeholder, inactive labels |
| `text-muted` | `#6b7280` (gray-500) | Disabled text, hints |
| `text-faint` | `#4b5563` (gray-600) | Separators, subtle borders |

### Accents
| Token | Hex | Usage |
|-------|-----|-------|
| `accent-primary` | `#2563eb` (blue-600) | Primary buttons, active tabs |
| `accent-hover` | `#3b82f6` (blue-500) | Button hover |
| `accent-light` | `#60a5fa` (blue-400) | Links, active indicators |
| `accent-subtle` | `#1e3a5f` | Active tab backgrounds |

### Semantic
| Token | Hex | Usage |
|-------|-----|-------|
| `success` | `#34d399` (green-400) | Connected, saved, valid |
| `warning` | `#fbbf24` (yellow-400) | Dirty indicator, pending |
| `error` | `#f87171` (red-400) | Errors, failed, destructive |
| `info` | `#60a5fa` (blue-400) | Informational messages |

---

## Typography

| Element | Size | Weight | Color |
|---------|------|--------|-------|
| Page heading | `text-lg` (18px) | Bold | text-primary |
| Section heading | `text-sm` (14px) | Semibold | text-primary |
| Body text | `text-sm` (14px) | Regular | text-secondary |
| Button label | `text-xs` (12px) | Medium | Varies |
| Caption / badge | `text-[10px]` | Medium | text-tertiary |
| Monospace / code | `text-sm font-mono` | Regular | text-secondary |

---

## Spacing Scale

Based on Tailwind's 4px base unit:
- `gap-1` (4px) -- between inline badge elements
- `gap-2` (8px) -- between toolbar items, form controls
- `gap-3` (12px) -- between card sections
- `px-2 py-1` -- compact controls (toolbar buttons, badges)
- `px-3 py-2` -- standard controls (inputs, list items)
- `px-4 py-3` -- card padding, larger sections

---

## Component Patterns

### Buttons
- **Primary**: `bg-blue-600 hover:bg-blue-500 text-white rounded px-3 py-1.5 text-xs font-medium`
- **Secondary**: `border border-gray-600 bg-transparent text-gray-300 hover:border-gray-400 rounded px-3 py-1.5 text-xs font-medium`
- **Toolbar toggle**: `rounded px-2 py-0.5 text-xs font-medium` with active state `bg-blue-600 text-white`
- **Disabled**: Add `disabled:opacity-50 disabled:cursor-not-allowed`

### Cards / Panels
- Border: `border border-gray-700 rounded-lg`
- Background: `bg-gray-900`
- Padding: `px-4 py-3`

### Inputs
- `bg-gray-800 border-gray-700 text-gray-200 placeholder-gray-500`
- Focus: `focus:outline-none focus:ring-1 focus:ring-blue-500`
- Border radius: `rounded`

### Tab Bars
- Active: `border-b-2 border-blue-400 text-blue-300`
- Inactive: `border-transparent text-gray-500 hover:text-gray-300`

### Status Indicators
- Connected: `bg-green-500` (solid dot)
- Connecting: `bg-yellow-400 animate-pulse`
- Disconnected: `bg-red-500`
- Dirty/modified: `bg-orange-400` (small dot)

---

## Responsive Breakpoints

| Breakpoint | Width | Layout |
|------------|-------|--------|
| Mobile | < 640px | Single column, hamburger nav, panels as overlays |
| Tablet | 640px -- 1023px | Two columns max, collapsible sidebars |
| Desktop | >= 1024px | Full multi-panel layout |

### Collapse Rules
- **Explorer panel**: Hidden on mobile, toggleable on tablet, visible on desktop
- **Inspector panel**: Hidden on mobile/tablet by default, toggleable
- **Console panel**: Collapsed by default on mobile, short on tablet
- **Navigation**: Hamburger menu on mobile, horizontal on tablet+

---

## Monaco Editor Theme

Name: `deluge-dark` (extends `vs-dark`)

| Token | Color | Style |
|-------|-------|-------|
| Keywords | `#569CD6` | Bold |
| Strings | `#CE9178` | -- |
| Numbers / dates | `#B5CEA8` | -- |
| Comments | `#6A9955` | Italic |
| Zoho variables | `#C586C0` | -- |
| Builtin functions | `#DCDCAA` | -- |
| Builtin tasks | `#D7BA7D` | Bold |
| Types | `#4EC9B0` | -- |
| Identifiers | `#9CDCFE` | -- |
| Operators | `#D4D4D4` | -- |

---

## Zoho Creator Design Guidance

When generating Zoho Creator applications, apply these design conventions where the platform allows:

### Form Design
- **Field order**: Key identifier fields first, then data fields, then audit fields (Added_User, Modified_Time) last
- **Section naming**: Use title case, max 3 words (e.g., "Claim Details", "Approval Status")
- **Field display names**: Title Case with spaces (e.g., "Amount ZAR", "GL Account")
- **Field link names**: snake_case matching the display name (e.g., `Amount_ZAR`, `GL_Account`)

### Report Design
- **Default sort**: Most recent first (descending by Added_Time or relevant date)
- **Column widths**: Auto, with key fields wider
- **Summary rows**: Use SUM for currency fields, COUNT for record counts

### Workflow Conventions
- **Naming**: `form_name.trigger_event.dg` (e.g., `expense_claim.on_validate.dg`)
- **Script header**: Comment block with form name, trigger, and one-line purpose
- **Null guards**: Always wrap lookups with `if (result != null && result.count() > 0)`
- **Audit fields**: Set `Added_User = zoho.loginuser` on create, never trust user input

### Dashboard Layout
- **Top row**: KPI cards (3-4 across), showing key metrics
- **Middle**: Primary chart or data table
- **Bottom**: Secondary charts, recent activity, or status summary

### Color in Zoho (where customizable)
- Use the Zoho Creator theme editor to set primary brand color to `#2563eb` (accent-primary)
- Status field colors: Draft = gray, Pending = yellow, Approved = green, Rejected = red
- Highlight overdue items in red, upcoming in yellow
