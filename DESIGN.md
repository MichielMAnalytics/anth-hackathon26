# SafeThread — Design tokens

Visual language for the **NGO Hub** web app. Source of truth lives in
[`web/tailwind.config.js`](./web/tailwind.config.js) and
[`web/src/styles.css`](./web/src/styles.css). This file is the
human-readable summary so designers / mobile / partner teams stay aligned.

## Aesthetic direction

> **Civic editorial calm**, adapted to **War Child Netherlands** branding.

We're an operator console for case workers triaging civilian messages from
warzones. The screen is on someone's desk for hours. It must read as
**calm, professional, humanitarian** — not tactical, not military, not
alarmist. Severity colors are informational, not screaming. White surfaces.
Generous negative space. One vivid accent (War Child red) reserved for
primary actions and brand moments.

Key rules:
- One primary action per surface. The red CTA appears once per pane.
- Severity is signal, not decoration — never tint a whole surface in `sev-*`.
- Keep mono font for IDs, timestamps, counts. Sans for everything else.

## Color tokens

### Brand — War Child red

Primary action color. Use sparingly: nav active state, primary buttons,
operator outbound chat bubbles, key callouts.

| Token         | Hex       | Usage                                             |
|---------------|-----------|---------------------------------------------------|
| `brand-50`    | `#fff1f1` | Tinted hover/selection backgrounds.               |
| `brand-100`   | `#ffdfdf` | Subtle badges.                                    |
| `brand-200`   | `#ffc4c4` | Border on hover for brand-tinted controls.        |
| `brand-300`   | `#ff9b9b` |                                                   |
| `brand-400`   | `#fa6464` |                                                   |
| `brand-500`   | `#ee3535` |                                                   |
| **`brand-600`** | **`#e62e2e`** | **Primary brand red. Default CTA bg.**          |
| `brand-700`   | `#c11f1f` | Hover state for primary CTA. Also `sev-critical`. |
| `brand-800`   | `#9d1d1d` |                                                   |
| `brand-900`   | `#811d1d` |                                                   |

### Surface — neutral whites + slate

Backgrounds, panels, dividers, borders. White-first.

| Token            | Hex       | Usage                                          |
|------------------|-----------|------------------------------------------------|
| `surface` / `surface-50` | `#ffffff` | Cards, modals, primary content surfaces. |
| `surface-100`    | `#f8fafc` | App background, alternate row hover.           |
| `surface-200`    | `#eef2f6` | Dividers between sections.                     |
| `surface-300`    | `#e2e8f0` | Borders on inputs, cards, dropdowns.           |
| `surface-400`    | `#cbd5e1` | Hairline emphasis.                             |
| `surface-500–900`| `#94a3b8 → #1e293b` | Use the `ink-*` scale for text instead.        |

### Ink — text + dark accents

Same hex range as `surface-500–900` but used for **text** and dark UI
chrome. Aliased separately so the role is explicit at the call site.

| Token       | Hex       | Usage                            |
|-------------|-----------|----------------------------------|
| `ink-400`   | `#94a3b8` | Disabled text, placeholders.     |
| `ink-500`   | `#64748b` | Meta labels (uppercase tracking).|
| `ink-600`   | `#475569` | Secondary body, link hover idle. |
| `ink-700`   | `#334155` | Strong secondary text.           |
| `ink-800`   | `#1e293b` | Headings on muted surfaces.      |
| **`ink-900`** | **`#0f172a`** | **Primary body text, headings on white.** |
| `ink-950`   | `#0a0f1d` | Maximum contrast — rarely needed.|

### Severity — informational, not alarming

Triage tones. **Only used on chips, badges, mini-icons, and 1px borders.**
Never tint a whole card or modal surface with `sev-*`.

| Token           | Hex       | Used for                                    |
|-----------------|-----------|---------------------------------------------|
| `sev-critical`  | `#c11f1f` | Critical-severity case chip. Distress flag. |
| `sev-high`      | `#b07636` | High-severity. Anomaly banner. Burnt amber. |
| `sev-medium`    | `#a17e2e` | Medium-severity. Ochre.                     |
| `sev-low`       | `#3f7d4f` | Low. Operator status dot. Forest green.     |

## Typography

Loaded from Google Fonts:

```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

| Family       | Stack                                            | Used for                                              |
|--------------|--------------------------------------------------|-------------------------------------------------------|
| `font-sans`  | `Inter, system-ui, sans-serif`                   | All UI body, buttons, inputs.                         |
| `font-display` | `Inter, system-ui, sans-serif` (heavier weights) | Headings, region names, brand wordmark.            |
| `font-mono`  | `JetBrains Mono, ui-monospace, monospace`        | Phone numbers, timestamps, numeric stats, IDs, keyboard hints. |

Type scale follows Tailwind defaults plus one custom token:

| Class       | Size / line-height                          | Usage                              |
|-------------|---------------------------------------------|------------------------------------|
| `text-meta` | `11px / 16px`, letter-spacing `0.04em`      | UPPERCASE LABELS, chip text, footnotes. |
| `text-xs`   | `12px / 16px`                               | Captions, helper text.             |
| `text-sm`   | `14px / 20px`                               | Default body, button labels.       |
| `text-base` | `16px / 24px`                               | Comfortable reading body.          |
| `text-lg`   | `18px / 28px`                               | Card titles.                       |
| `text-xl`   | `20px / 28px`                               | Section headings.                  |
| `text-2xl`  | `24px / 32px`                               | Page titles ("Where to act first").|

Headings use `font-display font-semibold` (weight 600) or `font-bold` (700)
for top-level brand moments only.

## Radii

| Token          | Value | Usage                                |
|----------------|-------|--------------------------------------|
| `rounded-sm`   | `4px` | Small chips, inline tags.            |
| `rounded`      | `6px` | Buttons, inputs (default).           |
| `rounded-md`   | `8px` | Cards, panels.                       |
| `rounded-lg`   | `12px`| Larger cards, modal panels.          |
| `rounded-xl`   | `16px`| Hero cards (rare).                   |
| `rounded-full` | `9999px` | Avatars, pills, severity chips.   |

## Shadows

Restrained, no glow. All shadows use `rgba(15, 23, 42, …)` (ink-900 base).

| Token          | Value                                  | Usage                |
|----------------|----------------------------------------|----------------------|
| `shadow-soft`  | `0 1px 2px rgba(15,23,42,0.04)`        | Buttons, subtle lift.|
| `shadow-card`  | `0 2px 8px rgba(15,23,42,0.06)`        | Cards, dropdowns.    |
| `shadow-modal` | `0 16px 40px rgba(15,23,42,0.16)`      | Modal dialogs.       |

## Spacing & layout

- Base spacing follows Tailwind's 4-px scale.
- Page padding: `px-6 py-6` desktop, `px-4 py-5` mobile.
- Section vertical rhythm: `space-y-4` (16px) inside cards, `space-y-5` (20px) between major sections.
- Border weight is **always 1px**. We don't use thicker borders.
- Dividers use `border-surface-200` (very subtle) or `border-surface-300` (visible).

## Severity color decision tree

```
case has missing_person + open  → severity=critical (sev-critical / brand-700 chip)
case has high distress signal   → severity=high     (sev-high)
case has multiple reporters     → severity=medium   (sev-medium)
otherwise                       → severity=low      (sev-low)
```

Only the **chip**, an **icon**, or a **1px left bar** carries the
severity tone. The card body itself stays on `surface-50` (white).

## Outbound vs inbound messages

- **Inbound** (civilian via Bitchat / SMS): `bg-surface-100`, `border-surface-200`, `text-ink-900`. Avatar uses last 2 digits of phone.
- **Outbound** (operator): `bg-brand-600`, `text-white`, `rounded-tr-sm` for chat tail. Avatar shows "WC" on `bg-brand-600`.
- Distress / location / needs tags appear under inbound bubbles only.

## Z-index ladder

| Layer                 | z-index   |
|-----------------------|-----------|
| Default page chrome   | auto      |
| Sticky header / FilterBar | 10    |
| Leaflet map controls  | 200–700 (Leaflet defaults) |
| Modals (`SendModal`)  | 50        |
| Header dropdowns (Operator switcher, mobile burger) | **1000** (must beat Leaflet) |

## Mobile breakpoints

| Width   | Tailwind | Behavior                                                                 |
|---------|----------|--------------------------------------------------------------------------|
| < 768   | (default)| Single-pane mobile flow. Burger nav. Cases collapses to list → thread → profile sheet. Map at 55vh + scrollable region panel below. |
| ≥ 768   | `md:`    | Tablet/iPad. Cases 3-pane (240/1fr/280). Dashboard 2-col grid.          |
| ≥ 1024  | `lg:`    | Desktop. Cases 3-pane widens to 300/1fr/360.                             |

## Out-of-scope (intentionally not specified)

- **Dark mode.** We're explicitly light-only — the operator UI is on a desk during long shifts; dark mode reads as ominous for this domain.
- **Marketing/donor surfaces.** This file covers the operator console only. Donor pages should align with `warchild.nl` proper.
