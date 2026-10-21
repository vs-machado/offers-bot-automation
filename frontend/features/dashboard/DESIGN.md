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

- Publication history groups by persisted offer identity (`dedup_key`), with
  delivery ID fallback for legacy rows. Never infer identity from product titles.
- Pagination counts offers and fetches every recorded destination outcome for
  each selected offer. Status filters select offers with at least one matching
  outcome, keeping the other outcomes visible for context.
- Collapsed offer rows show destination count, confirmed sends, aggregate result,
  and latest delivery registration. Expand to see destination names and individual
  results; expand a destination to inspect its reason, attempts, and timestamps.
- Advertised product price appears beneath the offer title on all screen sizes.
  Preserve source price text, including payment conditions. Legacy deliveries
  without stored prices display “Preço não registrado”; never infer a price from
  the product title or deduplication hash.
- Expanded offers include a button to copy the exact generated affiliate link,
  with accessible success feedback and a selectable fallback if clipboard access
  fails. Links are retained per delivery; legacy rows without a stored link show
  “Link comissionado indisponível”. Never substitute the original source URL.
- Keep “Abrir oferta” beside the copy action inside the expanded offer details.
  Open the stored affiliate link in a new tab; no additional dropdown is needed.
- Summary metrics still count individual sends across the entire history. Only
  recorded delivery attempts appear; absent destinations are not labeled as sent
  or failed.

- Sidebar: 240px, visible from 1024px. Main content: maximum 1440px.
- Spacing: 4px base; 16px mobile page padding and 24–32px on larger screens.
- Typography: 24–30px page heading; 14px dense data; 12px metadata. Base UI Select
  uses 16px text on mobile to avoid input zoom.
- Rows: 56px on desktop, 64px on mobile. Below 768px, title and store/date use
  two compact lines. Destination and other metadata remain in expanded details.
- Store column appears from 1280px; intermediate layouts prioritize the title,
  destination, status, and date. Long values truncate; full values are available
  in the disclosure panel.
- Each disclosure starts closed and opens independently. Entire summary is
  keyboard-operable, with a visible focus outline and state chevron.
- Retain API-backed status filtering, 20-offer pagination, manual refresh,
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

## Shared workspace redesign

### Audit

- Settings and administration previously rendered standalone page wrappers,
  making navigation disappear outside the dashboard.
- Navigation marked the dashboard active regardless of location.
- Twenty offer rows scrolled the entire document; native selects bypassed the
  component system.

### Decisions

- Put authenticated pages under the `(workspace)` route group without changing
  URLs. A shared Next.js layout preserves sidebar state between pages.
- Promote shell, navigation, mobile dialog, and logout presentation to
  `components/workspace`; features own their content and data access.
- Keep the 240px desktop sidebar and 64px header stationary in a `100dvh` frame.
  Settings/admin scroll inside `main`. The dashboard scrolls only its publication
  list, with filters, summary metrics and pagination remaining visible.
- At short phone sizes, metrics use one compact four-column row to preserve
  usable list height. An incomplete setup scrolls inside its own card.
- Use a shared themed Base UI Select for history status and Telegram destination
  type, including keyboard selection, focus return, and portaled menus.
- Use route-aware navigation and hash-aware section links. Administration stays
  role-gated; its API continues checking the current role on each request.
- Settings use anchored sections, 16–24px card padding, 44px controls, one-column
  form fields, and a separate destination list/form at wide sizes. Source choices
  are selectable rows; affiliate forms share the same heading/body structure.
- Admin uses a responsive list and a 360px editing panel on wide screens; at
  smaller sizes these stack vertically. All content uses existing theme tokens.
- Resolve missing destination names through Telegram `getChat`, persisting
  successful lookups to avoid repeat calls during history polling. Preserve custom
  aliases, tenant ownership, and ID fallback when the API is unavailable.

### Validation

Actual shell, settings editor, admin catalog and publication history rendered
with temporary fixtures; backend browser requests were intercepted.

- All three pages checked at 1440×900, 1024×768, 768×1024, 375×812 and 320×568.
- Light/dark checked at 1440px and 375px; no horizontal/document-height overflow.
- Confirmed sidebar DOM survives client-side navigation, route/section active
  states update, and anchors scroll the content area.
- Confirmed dashboard list has its own usable scroll area even at 320×568;
  header stays fixed during list and settings/admin scrolling.
- Confirmed mobile drawer Escape/focus restoration, library select interaction,
  history filter/reset requests, and no browser runtime errors.
- Targeted backend tests cover Telegram name lookup, API/JSON/timeout fallbacks,
  cached aliases, platform/tenant isolation, and missing-token behavior.

Additional references: `docs/presets/project/clean.html` (persistent multi-page
shell and grouped forms), `components/forms.md` (labels, widths and field rhythm),
and `components/navigation.md` (consistent location and current-page indication).
