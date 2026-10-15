# Instructions for AI Agents

Always load the `caveman` skill before responding — use the skill tool with name "caveman" for every response, with intensity level "full".

## Python Virtual Environment
Project venv is at `C:\Web Projects\offers_bot_automation\venv`. Activate before running Python commands:
```powershell
.\venv\Scripts\activate
```
Or use full paths: `.\venv\Scripts\python.exe`, `.\venv\Scripts\ruff.exe`, etc.

# Development Workflow

Commits must not trigger repository-wide checks or the test suite locally.
Automated quality checks run when pull requests targeting `master` are opened,
updated, or reopened, through `.github/workflows/pr-quality.yml`.
The required `quality` check must pass before merging. New PR updates cancel
outdated CI runs. Keep local commits free of hooks and full-suite checks.

## 1. Code Formatting & Linting
Do not install Git pre-commit hooks. Run targeted formatting and linting for
files changed during development when relevant, not as a commit prerequisite.
Fix diagnostic causes; do not add `noqa`, `eslint-disable`, or broad rule
exclusions to make checks pass. Manual Python commands (replace paths with
the changed files):

```bash
# Format code
ruff format path/to/changed.py

# Lint and fix common issues
ruff check --fix --ignore-noqa path/to/changed.py
```

## 2. Running Tests
Run the full test suite in PR CI, not before local commits.
Targeted tests may be run while developing or diagnosing a failure; run the
full suite locally only when explicitly requested. CI command:

```bash
# Run all tests
python -m unittest discover tests
```

## 3. Git Commits
When committing, use `git add -A` to stage all changes. Use conventional commits format:
```
<type>: <short description>
```
Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.

## 4. Handling Test Failures
**IMPORTANT:** If a test that was previously working begins to fail:
- **Analyze:** Check if the failure was caused by a recent code change or a change in external API behavior.
- **Do not modify tests silently:** If you believe the test itself needs to be updated to match new requirements, **always ask the user/developer for confirmation** before changing any existing test logic.
- **Fix Code First:** Priority should always be given to fixing the code to satisfy the existing tests before considering a change to the test itself.

## Documentation
Document crucial functions or methods when behavior is not obvious. Add concise docstrings to:

- public FastAPI route handlers and authentication dependencies;
- security, database, migration, and lifecycle functions;
- worker, posting, deduplication, and persistence methods;
- core parsing, source-fetching, and provider-facing APIs.

Docstrings should state purpose, important side effects, and relevant failure behavior. Do not add parameter-by-parameter comments or docstrings for obvious inputs, outputs, trivial private helpers, simple CRUD wrappers, model fields, or framework overrides.

## TypeScript / TSX Warnings
When editing `.ts` or `.tsx` files in `frontend`, always run:
```bash
npm run lint
```

Fix all warnings and errors reported for touched `.ts` and `.tsx` files before finishing. Do not leave unused imports, unused variables, missing hook dependencies, type errors, or ESLint warnings. If a warning cannot be fixed safely, explain the blocker in the final response.
