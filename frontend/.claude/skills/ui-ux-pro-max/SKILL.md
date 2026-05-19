---
name: ui-ux-pro-max
description: "UI/UX design intelligence for web and mobile. Includes 50+ styles, 161 color palettes, 57 font pairings, 161 product types, 99 UX guidelines, and 25 chart types across 10 stacks (React, Next.js, Vue, Svelte, SwiftUI, React Native, Flutter, Tailwind, shadcn/ui, and HTML/CSS). Actions: plan, build, create, design, implement, review, fix, improve, optimize, enhance, refactor, and check UI/UX code. Projects: website, landing page, dashboard, admin panel, e-commerce, SaaS, portfolio, blog, and mobile app. Elements: button, modal, navbar, sidebar, card, table, form, and chart. Styles: glassmorphism, claymorphism, minimalism, brutalism, neumorphism, bento grid, dark mode, responsive, skeuomorphism, and flat design. Topics: color systems, accessibility, animation, layout, typography, font pairing, spacing, interaction states, shadow, and gradient."
---

## Overview

Comprehensive design guidance covering 50+ UI styles, 161 color palettes, 57 font pairings, 161 product type classifications, 99 UX best practices, and 25 chart type recommendations. The framework spans 10 technology stacks including React, Next.js, Vue, Svelte, SwiftUI, React Native, Flutter, Tailwind CSS, shadcn/ui, and HTML/CSS.

## When to Apply

Invoke this skill for tasks involving UI structure, visual design decisions, interaction patterns, or user experience quality control. Apply particularly when:

- Designing new pages or screens
- Creating or refactoring UI components
- Selecting color schemes, typography, spacing, or layout systems
- Reviewing UI code for accessibility and consistency
- Implementing navigation, animations, or responsive behavior
- Making product-level design decisions
- Improving interface quality and usability

**Decision criterion**: If the task will change how a feature looks, feels, moves, or is interacted with, apply this skill.

---

## Priority-Based Rule Categories

| Priority | Category | Impact | Key Checks |
|----------|----------|--------|-----------|
| 1 | Accessibility | CRITICAL | 4.5:1 contrast, alt text, keyboard navigation, ARIA labels |
| 2 | Touch & Interaction | CRITICAL | 44×44px minimum, 8px spacing, loading feedback |
| 3 | Performance | HIGH | WebP/AVIF images, lazy loading, CLS < 0.1 |
| 4 | Style Selection | HIGH | Product type match, consistency, SVG icons |
| 5 | Layout & Responsive | HIGH | Mobile-first, breakpoints, no horizontal scroll |
| 6 | Typography & Color | MEDIUM | 16px base, 1.5 line-height, semantic tokens |
| 7 | Animation | MEDIUM | 150–300ms duration, motion conveys meaning |
| 8 | Forms & Feedback | MEDIUM | Visible labels, error placement, helper text |
| 9 | Navigation Patterns | HIGH | Predictable back, limited nav items, deep linking |
| 10 | Charts & Data | LOW | Legends, tooltips, accessible color usage |

---

## Accessibility Rules (CRITICAL)

- **Color contrast**: Maintain minimum 4.5:1 ratio for normal text, 3:1 for large text
- **Focus states**: Visible focus rings (2–4px) on all interactive elements
- **Alt text**: Descriptive alternatives for meaningful images
- **ARIA labels**: Required for icon-only buttons; use accessibilityLabel in native apps
- **Keyboard navigation**: Tab order matches visual flow; complete keyboard support
- **Form labels**: Persistent labels; avoid placeholder-only patterns
- **Skip links**: Provide skip-to-main-content for keyboard users
- **Heading hierarchy**: Sequential h1–h6 without skipping levels
- **Color independence**: Information must not rely on color alone
- **Dynamic type support**: Support system text scaling without truncation
- **Motion preferences**: Respect prefers-reduced-motion; disable animations when requested
- **Screen reader support**: Meaningful labels and logical reading order for VoiceOver/screen readers

---

## Touch & Interaction (CRITICAL)

- **Touch target size**: Minimum 44×44pt (Apple) or 48×48dp (Material Design)
- **Touch spacing**: Minimum 8px gap between targets
- **Hover vs. tap**: Use click/tap for primary interactions; don't rely on hover
- **Loading feedback**: Disable during async operations; show spinner or progress
- **Error feedback**: Clear messages positioned near the problem
- **Cursor indication**: Add cursor-pointer to clickable elements
- **Gesture consistency**: Use platform-standard gestures consistently
- **Press feedback**: Visual response on press (ripple/highlight within 80–150ms)
- **Haptic feedback**: Use for confirmations without overuse
- **Safe area awareness**: Keep primary targets away from notches and gesture areas
- **Swipe clarity**: Show affordance or hint for swipe actions
- **Drag threshold**: Require movement threshold before initiating drag

---

## Performance (HIGH)

- **Image optimization**: Use WebP/AVIF, responsive images, lazy loading
- **Dimension declaration**: Declare width/height or aspect-ratio to prevent layout shift
- **Font loading**: Use font-display: swap; reserve space to reduce CLS
- **Critical CSS**: Prioritize above-the-fold styles
- **Code splitting**: Split by route/feature to reduce initial load
- **Third-party scripts**: Load async/defer; remove unnecessary vendors
- **Layout reflows**: Batch DOM reads then writes
- **Content jumping**: Reserve space for async content
- **List virtualization**: Virtualize lists with 50+ items
- **Main thread budget**: Keep per-frame work under 16ms for 60fps
- **Input latency**: Maintain <100ms response time for taps/scrolls
- **Debounce/throttle**: Use for high-frequency events (scroll, resize, input)

---

## Style Selection (HIGH)

- **Style matching**: Align with product type (e.g., minimalism for SaaS, playfulness for entertainment)
- **Consistency**: Apply same style across all pages
- **Icon approach**: Use SVG icons (Heroicons, Lucide); avoid emoji
- **Color palettes**: Choose from product/industry context
- **Effect alignment**: Shadows, blur, radius matched to style (glass/flat/clay)
- **Platform respect**: Follow iOS HIG vs Material Design idioms
- **State clarity**: Make hover/pressed/disabled states visually distinct
- **Elevation system**: Use consistent shadow scale for cards, sheets, modals
- **Dark mode pairing**: Design light/dark variants together
- **Icon consistency**: Use one visual language across the product
- **Primary action**: One clear CTA per screen; secondary actions subordinate
- **Blur purpose**: Use for background dismissal (modals), not decoration

---

## Layout & Responsive (HIGH)

- **Viewport meta**: width=device-width, initial-scale=1; never disable zoom
- **Mobile-first approach**: Design mobile first, then scale up
- **Systematic breakpoints**: Use consistent breakpoints (375 / 768 / 1024 / 1440)
- **Readable font size**: Minimum 16px body text on mobile
- **Line length control**: 35–60 chars mobile, 60–75 chars desktop
- **Horizontal scroll prevention**: No horizontal scroll on mobile
- **Spacing scale**: Incremental 4pt/8dp spacing system
- **Touch density**: Keep comfortable spacing; avoid cramping
- **Container width**: Consistent max-width on desktop
- **Z-index management**: Define layered z-index scale
- **Fixed element offset**: Reserve padding for underlying content
- **Viewport units**: Prefer min-h-dvh over 100vh on mobile
- **Orientation support**: Readable and operable in landscape
- **Content priority**: Show core content first on mobile

---

## Typography & Color (MEDIUM)

- **Line height**: 1.5–1.75 for body text
- **Line length**: 65–75 characters per line
- **Font pairing**: Match heading and body font personalities
- **Type scale**: Consistent incremental scale (12 / 14 / 16 / 18 / 24 / 32)
- **Contrast readability**: Darker text on light backgrounds
- **Semantic tokens**: Define primary, secondary, error, surface color roles
- **Dark mode variants**: Use desaturated/lighter tones; verify contrast separately
- **Accessible pairs**: Foreground/background combinations meeting WCAG standards
- **Functional color**: Error red and success green should include icon/text
- **Truncation strategy**: Prefer wrapping; use ellipsis with tooltip when needed
- **Letter spacing**: Respect platform defaults; avoid tight tracking on body
- **Tabular figures**: Use monospaced figures for data columns and prices
- **Whitespace balance**: Use intentionally to group and separate sections

---

## Animation (MEDIUM)

- **Timing**: 150–300ms for micro-interactions; complex transitions ≤400ms
- **Performance**: Use transform/opacity only; avoid animating width/height
- **Loading states**: Show skeleton or progress when >300ms
- **Motion meaning**: Animations must express cause-effect relationships
- **State transitions**: Smooth animation for hover/active/expanded states
- **Spatial continuity**: Maintain continuity across page/screen transitions
- **Easing curves**: Ease-out for entering, ease-in for exiting
- **Spring physics**: Prefer spring/physics curves for natural feel
- **Exit speed**: Exit animations 60–70% of enter duration
- **Stagger sequences**: Offset list item entrances by 30–50ms
- **Reduced motion**: Respect system preference; disable when requested
- **Interruptible**: Animations must be cancellable by user action

---

## Forms & Feedback (MEDIUM)

- **Input labels**: Visible label per input; avoid placeholder-only
- **Error placement**: Show error below related field
- **Submit feedback**: Loading state, then success/error
- **Required indicators**: Mark required fields (e.g., asterisk)
- **Empty states**: Helpful message and action when no content
- **Toast dismissal**: Auto-dismiss in 3–5 seconds
- **Confirmations**: Confirm before destructive actions
- **Helper text**: Persistent text for complex inputs
- **Disabled styling**: Reduced opacity (0.38–0.5) with cursor change
- **Progressive disclosure**: Reveal complex options progressively
- **Inline validation**: Validate on blur, not keystroke
- **Input type**: Use semantic types (email, tel, number) for correct keyboard
- **Password toggle**: Provide show/hide for password fields
- **Autofill support**: Use autocomplete/textContentType attributes
- **Error recovery**: Include clear path to fix (retry, edit, help)
- **Multi-step progress**: Show step indicator or progress bar
- **Auto-save**: Save drafts in long forms
- **Destruction confirmation**: Confirm before dismissing sheets with unsaved changes

---

## Navigation Patterns (HIGH)

- **Bottom nav limit**: Maximum 5 items with labels and icons
- **Drawer usage**: For secondary navigation, not primary actions
- **Back consistency**: Predictable, preserves scroll and state
- **Deep linking**: All key screens reachable via URL
- **Tab bar (iOS)**: Bottom Tab Bar for top-level navigation
- **Top App Bar (Android)**: With navigation icon for primary structure
- **Nav labels**: Both icon and text; icon-only harms discoverability
- **Active state**: Highlight current location visually
- **Hierarchy clarity**: Separate primary (tabs/bottom bar) from secondary (drawer)
- **Modal escape**: Offer clear close affordance; swipe-down to dismiss on mobile
- **Search accessibility**: Easy access to search; provide suggestions
- **Breadcrumbs**: Use for 3+ level hierarchies on web
- **State preservation**: Restore scroll position and filter state when navigating back
- **Gesture support**: Support system gestures without conflict
- **Nav consistency**: Keep placement same across all pages
- **Avoid mixing patterns**: Don't combine Tab + Sidebar + Bottom Nav at same level
- **Modal constraint**: Don't use for primary navigation flows

---

## Charts & Data (LOW)

- **Chart type match**: Trend → line, comparison → bar, proportion → pie/donut
- **Accessible colors**: Avoid red/green-only pairs; use patterns/textures
- **Table alternative**: Provide table for screen readers; charts alone insufficient
- **Legend visibility**: Always show legend near chart
- **Tooltips**: Provide on hover (web) or tap (mobile) with exact values
- **Axis labels**: Label with units and readable scale
- **Responsive charts**: Reflow or simplify on small screens
- **Empty state**: Meaningful message when no data exists
- **Loading placeholder**: Show skeleton while data loads
- **Number formatting**: Use locale-aware formatting
- **Interactive legends**: Clickable to toggle series visibility
- **Contrast minimum**: Data lines/bars vs background ≥3:1
- **Avoid pie overuse**: Switch to bar chart for >5 categories
- **Focusable elements**: Interactive points/segments ≥44pt tap area
- **Screen reader summary**: Provide text summary of key insight

---

## Common Professional UI Standards

### Icons & Visual Elements

- **No emoji as structural icons** — use SVG (Lucide, Heroicons, @expo/vector-icons)
- **Vector-only assets** — SVG or platform vectors for scalability and theming
- **Stable interaction states** — color/opacity transitions without layout shift
- **Correct brand assets** — official logos with proper spacing and proportions
- **Consistent icon sizing** — define as tokens (icon-sm, icon-md, icon-lg)
- **Stroke consistency** — uniform stroke width (1.5px or 2px)
- **Filled vs outline discipline** — one style per hierarchy level
- **Touch target minimum** — 44×44pt interactive area with expanded hitSlop
- **Icon alignment** — baseline-aligned with consistent padding
- **Icon contrast** — 4.5:1 for small elements, 3:1 minimum for larger UI glyphs

### Interaction (App)

- **Tap feedback** — clear pressed response (ripple/opacity/elevation) within 80–150ms
- **Animation timing** — 150–300ms with platform-native easing
- **Accessibility focus** — focus order matches visual order; descriptive labels
- **Disabled clarity** — disabled semantics, reduced emphasis, no tap action
- **Touch target minimum** — ≥44×44pt (iOS) or ≥48×48dp (Android)
- **Gesture prevention** — one primary gesture per region; avoid conflicts
- **Semantic controls** — native primitives (Button, Pressable) with proper roles

### Light/Dark Mode Contrast

- **Surface readability (light)** — cards clearly separated from background
- **Text contrast (light)** — body text ≥4.5:1
- **Text contrast (dark)** — primary ≥4.5:1, secondary ≥3:1
- **Border visibility** — separators visible in both themes
- **State parity** — interaction states equally distinguishable in both modes
- **Token-driven theming** — semantic tokens mapped per theme
- **Modal legibility** — scrim strong enough (40–60% black) to isolate content

### Layout & Spacing

- **Safe-area compliance** — respect top/bottom safe areas for fixed headers
- **System bar clearance** — avoid collision with OS chrome
- **Consistent content width** — predictable width per device class
- **8dp spacing rhythm** — consistent incremental spacing
- **Readable measure** — long-form text remains readable on large devices
- **Section hierarchy** — clear vertical rhythm (16 / 24 / 32 / 48)
- **Adaptive gutters** — increase horizontal insets on larger widths
- **Coexistence** — scroll content not hidden behind fixed bars

---

## Pre-Delivery Checklist

### Visual Quality
- [ ] No emoji icons (use SVG)
- [ ] Consistent icon family and style
- [ ] Official brand assets with correct proportions
- [ ] Pressed states don't shift layout
- [ ] Semantic theme tokens used consistently

### Interaction
- [ ] Tap feedback within 80–150ms (ripple/opacity/elevation)
- [ ] Touch targets ≥44×44pt (iOS) or ≥48×48dp (Android)
- [ ] Micro-interactions 150–300ms with native easing
- [ ] Disabled states visually clear and non-interactive
- [ ] Focus order matches visual order; descriptive labels
- [ ] No conflicting gestures (tap/drag/back-swipe)

### Light/Dark Mode
- [ ] Primary text ≥4.5:1 contrast in both modes
- [ ] Secondary text ≥3:1 in both modes
- [ ] Dividers/borders visible in both themes
- [ ] Modal scrim 40–60% opacity
- [ ] Both themes tested before delivery

### Layout
- [ ] Safe areas respected for headers, tab bars, CTA bars
- [ ] Scroll content not hidden behind fixed bars
- [ ] Tested on small phone, large phone, tablet (portrait + landscape)
- [ ] Gutters adapt by device size and orientation
- [ ] 4/8dp spacing rhythm maintained
- [ ] Long-form text readable on larger devices

### Accessibility
- [ ] Meaningful images/icons have accessibility labels
- [ ] Form fields have labels, hints, error messages
- [ ] Color not the only indicator
- [ ] Reduced motion and dynamic text size supported
- [ ] Accessibility traits/roles/states announced correctly
