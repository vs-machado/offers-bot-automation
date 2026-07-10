<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## TypeScript / TSX Warnings
When editing `.ts` or `.tsx` files, always run:
```bash
npm run lint
```

Fix all warnings and errors reported for touched `.ts` and `.tsx` files before finishing. Do not leave unused imports, unused variables, missing hook dependencies, type errors, or ESLint warnings. If a warning cannot be fixed safely, explain the blocker in the final response.

## Frontend Architecture

Keep the frontend feature-based and vertically layered (VLA). Each feature owns
the code needed to deliver one user-facing capability, so changes remain local
and dependencies stay explicit.

### Directory Ownership

```text
app/                         # Next.js routes: compose, redirect, render feature entry points
features/<feature>/          # Feature-owned vertical slice
  <Feature>.tsx              # Public feature entry point / route-facing composition
  components/                # Feature-private UI pieces
  hooks/                     # Feature-private client state and interaction logic
  api/                       # Feature-specific request and server data functions
  lib/                       # Pure feature helpers, constants, transformations
  types.ts                   # Types used only by this feature
shared/contracts/            # Cross-feature API/domain contracts only
components/ui/               # Reusable design-system primitives
components/                  # Reusable cross-feature presentation components/providers
lib/                         # Reusable framework-agnostic helpers
```

### Decoupling Rules

- Keep `app/` thin. Route files select and render a feature; feature behavior
  belongs in `features/`.
- Keep feature code inside its feature unless two or more features genuinely
  need it. Do not create generic shared modules preemptively.
- Cross-feature imports may target only public feature entry points or
  deliberately shared contracts/utilities. Do not import another feature's
  `components/`, `hooks/`, `api/`, or `lib/` internals.
- Put browser requests in `<feature>/api/*-client.ts`; mark server-only data
  access with `import "server-only"` in `<feature>/api/*-server.ts`.
- Components render and delegate. Move stateful orchestration, effects, and
  interaction handlers into a `use-*.ts` hook when it makes a component easier
  to read or reuse.
- Keep `lib/` helpers deterministic and side-effect free. Keep fetches, React
  state, and Next.js navigation out of them.
- Promote API/domain shapes to `shared/contracts/` only when they are used by
  more than one feature. Otherwise, keep them in the owning feature's
  `types.ts`.

### Naming

- React components: PascalCase files and exports, e.g. `SetupDialog.tsx` and
  `SetupDialog`.
- Hooks: kebab-case `use-*.ts` files with camelCase `use*` exports, e.g.
  `use-source-group-previews.ts` and `useSourceGroupPreviews`.
- API modules: descriptive kebab-case names with explicit runtime suffixes,
  e.g. `setup-client.ts` and `dashboard-server.ts`.
- Types: PascalCase singular nouns; use `type` for object shapes and union
  types unless an interface's extension semantics are specifically needed.
- Functions and values: camelCase, action-oriented verbs for mutations
  (`saveDestination`, `toggleSourceChat`) and `get`/`load` for reads.
- Booleans: start with `is`, `has`, `can`, `should`, or `did`. Collections use
  plural nouns.
- Match backend wire names only at API boundaries. Internals may use project
  conventions; preserve required snake_case payload fields when calling APIs.

### VLA Change Checklist

For a new capability, add or extend one feature slice first. Add only layers
the capability needs: UI in the feature root or `components/`, interaction
logic in `hooks/`, transport in `api/`, pure transformations in `lib/`, and
types in local `types.ts` or `shared/contracts/` when truly shared. Keep import
direction toward shared code and feature internals; never make a feature depend
on another feature's private layer.
