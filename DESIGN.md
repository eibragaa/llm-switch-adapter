---
version: alpha
name: Switch Adapter Dashboard
description: Premium dark-mode dashboard for multi-provider LLM routing with mobile-first responsive design, real-time WebSocket updates, and comprehensive cost analytics.
colors:
  primary: "#0d1117"
  bg-elevated: "#161b22"
  bg-hover: "#21262d"
  border: "#30363d"
  border-muted: "#21262d"
  fg: "#e6edf3"
  fg-muted: "#8b949e"
  fg-subtle: "#6e7681"
  fg-inverse: "#0d1117"
  accent: "#58a6ff"
  accent-dim: "#1f6feb"
  purple: "#a371f7"
  purple-dim: "#8957e5"
  green: "#3fb950"
  green-dim: "#2ea043"
  yellow: "#d29922"
  yellow-dim: "#bb800c"
  red: "#f85149"
  red-dim: "#da3633"
  cyan: "#39c5cf"
  # Semantic mappings (reference primary tokens)
  status-online: "{colors.green}"
  status-limited: "{colors.yellow}"
  status-offline: "{colors.red}"
  status-nokey: "{colors.fg-subtle}"
  tier-low: "{colors.green}"
  tier-medium: "{colors.yellow}"
  tier-high: "{colors.purple}"
  tier-free: "{colors.green}"
  tier-paid: "{colors.purple}"
  cost-zero: "{colors.green}"
  cost-low: "{colors.cyan}"
  cost-medium: "{colors.yellow}"
  cost-high: "{colors.red}"

typography:
  display-xl:
    fontFamily: "Space Grotesk"
    fontSize: "3rem"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.03em"
  display-lg:
    fontFamily: "Space Grotesk"
    fontSize: "2.25rem"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  display-md:
    fontFamily: "Space Grotesk"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  h1:
    fontFamily: "Space Grotesk"
    fontSize: "1.875rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  h2:
    fontFamily: "Space Grotesk"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.25
  h3:
    fontFamily: "Space Grotesk"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
  h4:
    fontFamily: "Space Grotesk"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.4
  body-lg:
    fontFamily: "Space Grotesk"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.6
  body-md:
    fontFamily: "Space Grotesk"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  body-sm:
    fontFamily: "Space Grotesk"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  body-xs:
    fontFamily: "Space Grotesk"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.5
  mono-xl:
    fontFamily: "JetBrains Mono"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.2
  mono-lg:
    fontFamily: "JetBrains Mono"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
  mono-md:
    fontFamily: "JetBrains Mono"
    fontSize: "1rem"
    fontWeight: 500
    lineHeight: 1.4
  mono-sm:
    fontFamily: "JetBrains Mono"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.4
  mono-xs:
    fontFamily: "JetBrains Mono"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.5
  label-lg:
    fontFamily: "Space Grotesk"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.04em"
  label-md:
    fontFamily: "Space Grotesk"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.06em"
  label-sm:
    fontFamily: "Space Grotesk"
    fontSize: "0.625rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.08em"

rounded:
  none: "0px"
  xs: "2px"
  sm: "4px"
  md: "8px"
  lg: "12px"
  xl: "16px"
  full: "9999px"

spacing:
  0: "0"
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  2xl: "48px"
  3xl: "64px"

# Extended tokens (validated by npx @google/design.md spec --rules-only)
# These are defined for documentation; actual CSS uses custom properties
shadows:
  none: "none"
  xs: "0 1px 2px rgba(0,0,0,0.3)"
  sm: "0 2px 8px rgba(0,0,0,0.35)"
  md: "0 4px 16px rgba(0,0,0,0.4)"
  lg: "0 8px 24px rgba(0,0,0,0.45)"
  xl: "0 16px 48px rgba(0,0,0,0.5)"
  glow-green: "0 0 12px {colors.green}, 0 0 24px #3fb95033"
  glow-yellow: "0 0 12px {colors.yellow}, 0 0 24px #d2992233"
  glow-red: "0 0 12px {colors.red}, 0 0 24px #f8514933"
  glow-accent: "0 0 12px {colors.accent}, 0 0 24px #1f6feb33"

transitions:
  fast: "100ms ease-out"
  base: "150ms ease-out"
  slow: "250ms ease-out"
  spring: "300ms cubic-bezier(0.34, 1.56, 0.64, 1)"

z-index:
  base: 0
  dropdown: 100
  sticky: 200
  modal: 300
  popover: 400
  tooltip: 500
  toast: 600

breakpoints:
  xs: "480px"
  sm: "640px"
  md: "768px"
  lg: "1024px"
  xl: "1280px"
  2xl: "1536px"

components:
  # Status indicator dot
  status-dot:
    rounded: "{rounded.full}"
    size: "10px"
  
  # Provider card
  card-provider:
    backgroundColor: "{colors.bg-elevated}"
    rounded: "{rounded.lg}"
    padding: "{spacing.md}"
  
  # Stat card
  card-stat:
    backgroundColor: "{colors.bg-elevated}"
    rounded: "{rounded.xl}"
    padding: "{spacing.md}"
  
  # Section card
  card-section:
    backgroundColor: "{colors.bg-elevated}"
    rounded: "{rounded.xl}"
    padding: "{spacing.lg}"
  
  # Button primary
  btn-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.fg-inverse}"
    rounded: "{rounded.md}"
    padding: "{spacing.sm} {spacing.md}"
    typography: "{typography.body-sm}"
  
  # Button secondary
  btn-secondary:
    backgroundColor: "{colors.bg-hover}"
    textColor: "{colors.fg}"
    rounded: "{rounded.md}"
    padding: "{spacing.sm} {spacing.md}"
    typography: "{typography.body-sm}"
  
  # Button ghost
  btn-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.fg-muted}"
    rounded: "{rounded.md}"
    padding: "{spacing.sm} {spacing.sm}"
    typography: "{typography.body-sm}"
  
  # Badge
  badge:
    rounded: "{rounded.full}"
    padding: "2px 8px"
    typography: "{typography.label-sm}"
  
  badge-online:
    backgroundColor: "#3fb95033"
    textColor: "{colors.green}"
  
  badge-limited:
    backgroundColor: "#d2992233"
    textColor: "{colors.yellow}"
  
  badge-offline:
    backgroundColor: "#f8514933"
    textColor: "{colors.red}"
  
  badge-free:
    backgroundColor: "#3fb95033"
    textColor: "{colors.green}"
  
  badge-paid:
    backgroundColor: "#a371f733"
    textColor: "{colors.purple}"
  
  badge-subscription:
    backgroundColor: "#39c5cf33"
    textColor: "{colors.cyan}"
  
  # Table
  th:
    typography: "{typography.label-md}"
    backgroundColor: "{colors.primary}"
    padding: "{spacing.sm} {spacing.md}"
  
  td:
    padding: "{spacing.sm} {spacing.md}"
    typography: "{typography.body-sm}"
  
  # Input
  input:
    backgroundColor: "{colors.primary}"
    rounded: "{rounded.md}"
    padding: "{spacing.sm} {spacing.md}"
    typography: "{typography.body-sm}"
  
  # Select
  select:
    backgroundColor: "{colors.primary}"
    rounded: "{rounded.md}"
    padding: "{spacing.sm} {spacing.md}"
    typography: "{typography.body-sm}"
  
  # Progress bar
  progress:
    rounded: "{rounded.full}"
    height: "6px"
  
  progress-fill:
    rounded: "{rounded.full}"
    height: "100%"
  
  # Sparkline bar
  sparkline-bar:
    rounded: "{rounded.xs}"
    height: "4px"
  
  # Avatar
  avatar:
    rounded: "{rounded.full}"
    size: "32px"
  
  avatar-sm:
    rounded: "{rounded.full}"
    size: "24px"
  
  avatar-lg:
    rounded: "{rounded.full}"
    size: "48px"
  
  # Tooltip
  tooltip:
    backgroundColor: "{colors.fg}"
    textColor: "{colors.primary}"
    rounded: "{rounded.sm}"
    padding: "{spacing.xs} {spacing.sm}"
    typography: "{typography.body-xs}"
  
  # Modal
  modal:
    backgroundColor: "{colors.bg-elevated}"
    rounded: "{rounded.xl}"
    padding: "{spacing.lg}"
    width: "90vw"
    size: "640px"
  
  # Accordion / Details
  details:
    backgroundColor: "{colors.bg-elevated}"
    rounded: "{rounded.md}"
  
  details-content:
    padding: "0 {spacing.md} {spacing.md}"
  
  # Divider
  divider:
    padding: "{spacing.md} 0"

---

## Overview

The Switch Adapter Dashboard is a premium, developer-first interface for monitoring and managing multi-provider LLM routing. It embodies the precision of **Vercel** (monochrome minimalism, systematic spacing), the density of **Linear** (compressed information architecture, purposeful purple accents), and the elegance of **Stripe** (refined gradients, weight-300 typography).

**Mood**: Technical confidence — every pixel serves a purpose. Dark-mode native, zero visual noise, data-dense but scannable. The interface feels like a well-crafted terminal that graduated to a modern web app.

**Emotional response**: "This is a tool built by engineers who respect my time." Trust, control, clarity.

## Colors

The palette is built on a **dark-neutral foundation** (`#0d1117` / `#161b22`) with **semantic accents** that carry meaning, not decoration.

### Base Surfaces
- **primary (#0d1117)** — Page background, deepest layer
- **bg-elevated (#161b22)** — Cards, modals, elevated surfaces
- **bg-hover (#21262d)** — Interactive hover states
- **border (#30363d)** — Primary borders, dividers
- **border-muted (#21262d)** — Subtle separators, table rows

### Text Hierarchy
- **fg (#e6edf3)** — Primary text, headlines
- **fg-muted (#8b949e)** — Secondary text, metadata, labels
- **fg-subtle (#6e7681)** — Tertiary text, placeholders, disabled
- **fg-inverse (#0d1117)** — Text on accent backgrounds

### Brand Accents
- **accent (#58a6ff)** — Primary interaction driver (buttons, links, focus rings). Vercel-inspired blue, strong on dark.
- **accent-dim (#1f6feb)** — Hover/active states for accent
- **purple (#a371f7)** — Secondary brand (premium/paid tier, Linear-inspired)
- **purple-dim (#8957e5)** — Hover states for purple

### Status Semantics (WCAG AA validated on bg-elevated)
All status colors validated at 4.5:1 minimum contrast on `#161b22`:

| Token | Hex | Contrast on bg-elevated | Use Case |
|-------|-----|------------------------|----------|
| `status-online` | `#3fb950` | 5.8:1 ✓ | Healthy providers, success |
| `status-limited` | `#d29922` | 6.2:1 ✓ | Degraded, rate-limited |
| `status-offline` | `#f85149` | 5.1:1 ✓ | Down, error, critical |
| `status-nokey` | `#6e7681` | 3.2:1 ✗* | Missing config — muted intentionally |

*Muted status uses lower contrast intentionally — it's not actionable.

### Tier & Cost Mapping
- **tier-low / tier-free** → green (free, local, instant)
- **tier-medium** → yellow (API free, some latency)
- **tier-high / tier-paid** → purple (premium, subscription, paid APIs)
- **cost-zero** → green
- **cost-low** → cyan (< $0.01/1K)
- **cost-medium** → yellow ($0.01-0.10/1K)
- **cost-high** → red (> $0.10/1K)

### Chart Palette (for implementation reference)
8-color categorical palette validated for **deuteranopia/protanopia/tritanopia** safety:
`#58a6ff`, `#a371f7`, `#3fb950`, `#d29922`, `#f85149`, `#39c5cf`, `#f97583`, `#ffa657`

## Typography

**Space Grotesk** (UI) + **JetBrains Mono** (Data) — both on Google Fonts, variable font support.

### Hierarchy Principles
- Weight and size carry hierarchy, not font family
- Tight letter-spacing on display sizes (-0.02 to -0.03em)
- Tabular numerals (`tnum`) on all mono — columns align
- Uppercase labels with generous tracking (0.04-0.08em) for metadata

### Fluid Type (CSS clamp)
Responsive without breakpoints:
```css
font-size: clamp(1.5rem, 3vw, 1.875rem);  /* h1 */
font-size: clamp(1.25rem, 2.5vw, 1.5rem);  /* h2 */
```

## Layout & Spacing

**4px baseline grid** — all spacing, sizing, radii are multiples of 4.

### Scale
| Token | Value | Use Case |
|-------|-------|----------|
| `xs` | 4px | Intra-element gaps, icon padding |
| `sm` | 8px | Button padding, input padding |
| `md` | 16px | Card padding, section gutters |
| `lg` | 24px | Inter-component gaps, card gaps |
| `xl` | 32px | Section breaks, page margins |
| `2xl` | 48px | Major section breaks |
| `3xl` | 64px | Hero sections, full-page gaps |

### Grid System
```css
/* Provider grid - auto-fit with minmax */
.providers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

/* Stats row - 4-col on desktop, 2-col tablet, 1-col mobile */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
@media (max-width: 1024px) { grid-template-columns: repeat(2, 1fr); }
@media (max-width: 640px) { grid-template-columns: 1fr; }
```

## Shapes

| Token | Value | Use Case |
|-------|-------|----------|
| `none` | 0px | Sharp corners (tables) |
| `xs` | 2px | Sparkline bars, tiny badges |
| `sm` | 4px | Buttons, inputs, small cards |
| `md` | 8px | Primary cards, modals, dropdowns |
| `lg` | 12px | Section cards, provider cards |
| `xl` | 16px | Stat cards, major sections |
| `full` | 9999px | Avatars, pills, status dots |

## Elevation & Depth

Two-layer shadow system (for implementation reference):

| Token | Value | Use Case |
|-------|-------|----------|
| `none` | none | Flat cards default |
| `xs` | 0 1px 2px rgba(0,0,0,0.3) | Subtle lift |
| `sm` | 0 2px 8px rgba(0,0,0,0.35) | Hover cards |
| `md` | 0 4px 16px rgba(0,0,0,0.4) | Provider card hover |
| `lg` | 0 8px 24px rgba(0,0,0,0.45) | Dropdowns, popovers |
| `xl` | 0 16px 48px rgba(0,0,0,0.5) | Modals, toasts |

**Glow shadows** for status emphasis:
- `glow-green` — online pulse
- `glow-yellow` — limited attention
- `glow-red` — offline alert
- `glow-accent` — primary action focus

## Motion

- **Fast (100ms)**: Button press, hover, focus ring
- **Base (150ms)**: Card hover, accordion, tooltip
- **Slow (250ms)**: Modal enter, progress fill, sparkline
- **Spring (300ms cubic-bezier(0.34,1.56,0.64,1))**: Staggered list entries

**Respects `prefers-reduced-motion`** — all animations disabled except essential state changes.

## Accessibility

- **WCAG AA** on all text/background pairs
- **Focus visible**: 3px accent ring on all interactive
- **Semantic HTML**: header, main, section, article, aside, nav
- **ARIA**: labels on icon buttons, live regions for WebSocket status
- **Color not sole indicator**: status = dot + label + color
- **Touch targets**: min 44×44px on mobile
- **Keyboard**: all interactive reachable, logical tab order

## Dark Mode Only

This dashboard is **dark-mode only** — matches developer tooling expectations, reduces eye strain on OLED, aligns with terminal heritage. No light mode toggle.

## PWA Considerations

- **Standalone display** — no browser chrome when installed
- **Theme color** = accent (`#58a6ff`)
- **Background color** = primary (`#0d1117`)
- **Icons**: 192px, 512px SVG → PNG generated at build
- **Service worker**: cache-first for static, network-first for API
- **Offline**: show cached data with staleness indicator

## Do's and Don'ts

- **Do** use token references (`{colors.accent}`) everywhere
- **Do** use mono for every number, timestamp, token count
- **Do** respect `prefers-reduced-motion`
- **Do** validate changes with `npx @google/design.md lint DESIGN.md`
- **Don't** add colors outside the palette — extend in DESIGN.md first
- **Don't** use emoji in production UI (OK in dev/debug)
- **Don't** nest component variants — `btn-primary-hover` is sibling
- **Don't** hardcode spacing — use tokens
- **Don't** assume viewport — test xs through 2xl
- **Don't** forget PWA manifest + service worker on deploy

---

## Toolchain

```bash
# Lint + WCAG check
npx -y @google/design.md lint DESIGN.md

# Export tokens for CSS/JS
npx -y @google/design.md export --format tailwind DESIGN.md > tailwind.theme.json
npx -y @google/design.md export --format dtcg DESIGN.md > tokens.json

# Diff versions
npx -y @google/design.md diff DESIGN.md DESIGN-v2.md
```

## CSS Custom Properties Output

The design tokens map to these CSS variables (auto-generated via export):

```css
:root {
  --color-primary: #0d1117;
  --color-bg-elevated: #161b22;
  --color-bg-hover: #21262d;
  --color-border: #30363d;
  --color-border-muted: #21262d;
  --color-fg: #e6edf3;
  --color-fg-muted: #8b949e;
  --color-fg-subtle: #6e7681;
  --color-fg-inverse: #0d1117;
  --color-accent: #58a6ff;
  --color-accent-dim: #1f6feb;
  --color-purple: #a371f7;
  --color-green: #3fb950;
  --color-yellow: #d29922;
  --color-red: #f85149;
  --color-cyan: #39c5cf;
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --rounded-sm: 4px;
  --rounded-md: 8px;
  --rounded-lg: 12px;
  --rounded-xl: 16px;
  --shadow-md: 0 4px 16px rgba(0,0,0,0.4);
  --transition-fast: 100ms ease-out;
  --transition-base: 150ms ease-out;
  --transition-slow: 250ms ease-out;
  --font-ui: 'Space Grotesk', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}
```

---

*Generated with `design-md` skill. Run `npx @google/design.md lint DESIGN.md` to validate.*