# Dashboard design notes

Based on the [make-it-look-good design guidance](https://github.com/jdeworks/make-it-look-good).

## Direction

- Clean, compact workspace for monitoring offer deliveries.
- Retain the existing shadcn `base-luma` theme: zinc neutrals, green primary,
  Inter typography, rounded components, and the existing theme toggle.
- Use existing semantic color tokens rather than a separate dashboard palette.

## Audit and changes

- The old offer list repeated title/status, destination/date, reason, and
  stage/attempt metadata vertically. Collapsed rows now show one aligned line
  on desktop. Native disclosure reveals the full title, reason, destination,
  store, stage, attempts, and timestamps without losing information.
- Large metric cards and decorative artwork pushed useful data below the fold.
  Four metrics now share a compact, divided card beneath a short page heading.
- Nonfunctional navigation buttons added noise. Desktop and mobile now share
  four working destinations, with administrator navigation shown by role.
- The mobile drawer now uses Base UI Dialog for focus containment, Escape,
  backdrop dismissal, scroll locking, and focus restoration.
- Setup uses three actionable requirements: destination, affiliate credentials,
  and source selection. The configured/unconfigured eligibility checks remain
  equivalent to the previous five-step display.

## Layout and behavior

- Sidebar: 240px, visible from 1024px. Main content: maximum 1440px.
- Spacing: 4px base; 16px mobile page padding and 24–32px on larger screens.
- Typography: 24–30px page heading; 14px dense data; 12px metadata. Native select
  uses 16px text on mobile to avoid input zoom.
- Rows: 56px on desktop, 64px on mobile. Below 768px, title and store/date use
  two compact lines. Destination and other metadata remain in expanded details.
- Store column appears from 1280px; intermediate layouts prioritize the title,
  destination, status, and date. Long values truncate; full values are available
  in the disclosure panel.
- Each disclosure starts closed and opens independently. Entire summary is
  keyboard-operable, with a visible focus outline and state chevron.
- Retain API-backed status filtering, 20-record pagination, manual refresh,
  and 30-second polling. Metrics describe the entire history, not today's data.
- No invented charts, activity claims, trend deltas, or production sample data.
- Icons and text accompany status colors. Motion is limited to interaction
  feedback and active refresh, respecting reduced-motion preferences.

## Validation

Actual dashboard shell and history components were rendered with temporary
fixtures, with history requests intercepted rather than sent to production.

- Browser checks at 320, 375, 768, 1024, and 1440px: no horizontal overflow.
- Light and dark mode verified at desktop and mobile sizes.
- Expanded failure information, keyboard disclosure, status-filter reset,
  empty/error states, mobile focus containment, Escape, and focus return checked.
- Representative rendered text contrast: minimum 4.59:1 in light mode and
  6.20:1 in dark mode, sampled over composited backgrounds. This is not a claim
  of a complete accessibility audit.

## References

- `CONSULT.md`: existing-code audit and design review workflow.
- `docs/presets/dashboard/clean.html`: dashboard shell, metric, and row structure,
  adapted to the project's existing theme rather than the preset's colors.
- `components/tables-and-lists.md`: aligned rows, progressive mobile disclosure.
- `components/navigation.md`: concise working navigation and drawer behavior.
- `layout/grid-systems.md` and `layout/spacing-system.md`: content bounds,
  responsive columns, and spacing rhythm.
- `workflows/quick-reference.md` and `workflows/component-decision-points.md`:
  control sizes, pagination, disclosure, and explicitly chosen behaviors.
- `heuristics/llm-design-gotchas.md`: contrast, motion, placeholder, and hierarchy
  self-audit.
