# Development

[Documentation index](README.md)

## Environment

Containers and CI use Python 3.12; CI uses Node.js 22. The simplest way to run
the entire platform is [Docker Compose](local-setup.md), whose override mounts
the frontend and runs `next dev`.

For local Python tools, create/activate a virtual environment and install
dependencies. In PowerShell, following the project's convention:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
npm --prefix frontend ci
```

On Linux/macOS, use `python3.12 -m venv .venv` and `source .venv/bin/activate`.
The `python` and `ruff` commands below assume that environment is active.

The host uses `DATABASE_URL`/`AUTH_DATABASE_URL` with `localhost:5434`.
For Next.js outside Docker, put the required variables in `frontend/.env.local`,
with `API_BASE_URL=http://localhost:8000`. Start the backend and frontend with:

```bash
python -m uvicorn backend.app.main:app --env-file .env --reload --port 8000
npm --prefix frontend run dev
```

These are separate processes. The database and secrets must still be available.
Start the reader with `python -m backend.worker`, with infrastructure variables
loaded into the process environment; this entry point does not load `.env`
automatically. Publishing also requires Redis reachable at `REDIS_URL` and a
Celery consumer.
Compose does not expose Redis to the host; publish its port in your own local
configuration or keep worker/posting in containers.

On Windows, prefer Docker for Celery. `--pool=solo` avoids the process pool
for local experiments, but Celery does not officially support Windows.

## Structure and responsibilities

The [Architecture guide](architecture.md) describes backend, worker, and libraries.
The frontend is organized by feature:

```text
frontend/
  app/                    routes and composition
  features/<feature>/     feature, components, hooks, API, and helpers
  shared/contracts/       contracts shared by multiple features
  components/ui/          design-system primitives
  components/             reusable presentation
  lib/                    shared helpers
```

Keep routes thin and behavior inside the feature. Browser requests belong in
`api/*-client.ts`; server-only access belongs in `api/*-server.ts`.
Avoid importing another feature's private internals. Follow applicable
`AGENTS.md` files and the installed Next.js version's documentation.

## Targeted local checks

Local commits must not trigger repository-wide checks or the full test suite.
Do not install pre-commit hooks. During development, validate changed files:

```bash
ruff format path/to/changed.py
ruff check --fix --ignore-noqa path/to/changed.py
python -m unittest tests.test_amazon
```

When editing frontend TypeScript/TSX, run:

```bash
npm --prefix frontend run lint
```

Fix diagnostic causes without `noqa`, `eslint-disable`, or broad exclusions.
Ruff checks suppressions with `RUF100`; CI uses `--ignore-noqa`. ESLint requires
zero warnings and validates canonical Tailwind 4 classes using `app/globals.css`.

If an existing test starts failing, investigate code and dependencies before
changing its logic. Changes to existing test logic require confirmation under
the repository instructions.

## WhatsApp tests

Mocked WAHA tests do not connect accounts or create real groups:

```bash
python -m unittest tests.test_whatsapp_management tests.test_whatsapp tests.test_destination_categories
```

For policies and multiple connections:

```bash
python -m unittest tests.test_whatsapp_connections tests.test_whatsapp_delivery_policy tests.test_integration_health
```

Set `WAHA_POLICY_TEST_DATABASE_URL` to a disposable PostgreSQL database to include
migration/concurrency tests. Each test creates and removes its own schema; never
use production. CI provides a database automatically. Real QR, text, and image
validation remains necessary after deployment; see the
[WhatsApp specification](whatsapp-implementation.md).

## Awin / KaBuM tests

Targeted checks mock Awin responses and do not generate real account links:

```bash
python -m unittest tests.test_awin tests.test_backend_affiliate_validation tests.test_backend_worker tests.test_delivery_history tests.test_parser
```

Validating a real account requires its publisher ID, API token, and approval
for the KaBuM program. See [Integrations](integrations.md).

## CI and pull requests

The [PR quality](../.github/workflows/pr-quality.yml) workflow runs when PRs
targeting `master` are opened, updated, or reopened. New updates cancel older
runs. Pushes without a PR do not trigger the workflow.

The `quality` job installs dependencies, checks Ruff, ESLint, Next.js/TypeScript
types, and runs `python -m unittest discover tests`. The default checkout tests
the PR's merge result against its base. Checks do not modify files.

Protection for `master` must require a PR, an up-to-date branch, and a passing
`quality` check, including for administrators. The workflow does not configure
those rules by itself. There is no automatic merge or deployment; additional
approval from another reviewer is not required by the documented policy.

Use Conventional Commits (`fix:`, `feat:`, `docs:`, etc.). Commit, PR, and GitHub
collaboration text must be in English.

In clones with an older hook installed, remove it once using the environment
where `pre_commit` is installed:

```bash
python -m pre_commit uninstall
```
