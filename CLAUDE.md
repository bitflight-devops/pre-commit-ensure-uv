# pre-commit-ensure-uv

Pre-commit hook ensuring [uv](https://github.com/astral-sh/uv) installation and PATH availability. Compatible with pre-commit and prek (Rust-based pre-commit alternative).

## Development Commands

```bash
# Install dependencies
uv sync

# Run linting
uv run ruff check .
uv run ruff format --check .

# Run type checking
uv run mypy packages/
uv run basedpyright

# Run pre-commit hooks (uses prek if available)
prek run --all-files
# or
pre-commit run --all-files

# Build package
uv build

# Test hook in Docker container
docker build -t ensure-uv-test -f test/Dockerfile .
docker run --rm ensure-uv-test
```

## Architecture

Single-file Python package in `packages/ensure_uv/`:

- `main.py` — Core logic: checks uv in PATH, installs if needed, re-runs hooks with corrected PATH
- `version.py` — Dynamic version from hatch-vcs (development) or importlib.metadata (installed)
- `__init__.py` — Exports `main` and `__version__`

**Entry point:** `ensure-uv` (defined in `pyproject.toml` `[project.scripts]`)

### Hook Execution Flow

1. After re-run (marker `_ENSURE_UV_RERUN` set) → pass if uv in PATH
2. uv in PATH → pass silently
3. uv installed, not in PATH → re-run hooks with uv's bin dir prepended to PATH
4. uv not installed → install via official installer, re-run hooks

## Configuration

All configuration in `pyproject.toml`:

- **ruff** — Linting and formatting (targets Python 3.11, Google docstring style)
- **mypy** — Strict mode type checking
- **basedpyright** — Additional type checking
- **semantic_release** — Version management from conventional commits

Pre-commit configuration in `.pre-commit-config.yaml` (prek-compatible hooks).
