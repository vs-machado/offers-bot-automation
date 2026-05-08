# Instructions for AI Agents

Always load the `caveman` skill before responding — use the skill tool with name "caveman" for every response, with intensity level "full".

# Development Workflow

To ensure code quality and consistency, please follow this workflow before every commit:

## 1. Code Formatting & Linting
Always run **Ruff** to format and lint the code:

```bash
# Format code
ruff format .

# Lint and fix common issues
ruff check --fix .
```

## 2. Running Tests
After formatting, run the test suite to ensure everything is still working correctly:

```bash
# Run all tests
python -m unittest discover tests
```

## 3. Handling Test Failures
**IMPORTANT:** If a test that was previously working begins to fail:
- **Analyze:** Check if the failure was caused by a recent code change or a change in external API behavior.
- **Do not modify tests silently:** If you believe the test itself needs to be updated to match new requirements, **always ask the user/developer for confirmation** before changing any existing test logic.
- **Fix Code First:** Priority should always be given to fixing the code to satisfy the existing tests before considering a change to the test itself.
