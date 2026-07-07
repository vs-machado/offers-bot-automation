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
