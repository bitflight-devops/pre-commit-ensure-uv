# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A pre-commit hook that ensures [uv](https://github.com/astral-sh/uv) is installed and available. Works with both pre-commit and prek (a Rust-based pre-commit alternative).

## Build & Development Commands

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

The hook is a single-file Python package in `packages/ensure_uv/`:

- `main.py` - Core logic: checks if uv is in PATH, installs if needed, re-runs hooks with corrected PATH
- `version.py` - Dynamic version from hatch-vcs (development) or importlib.metadata (installed)
- `__init__.py` - Exports `main` and `__version__`

**Hook behavior flow:**

1. If running after a re-run (marker `_ENSURE_UV_RERUN` set) → pass if uv in PATH
2. If uv already in PATH → pass silently
3. If uv installed but not in PATH → re-run hooks with uv's bin dir prepended to PATH
4. If uv not installed → install via official installer, then re-run

**Entry point:** `ensure-uv` (defined in pyproject.toml `[project.scripts]`)

## Tooling Configuration

All configuration lives in `pyproject.toml`:

- **ruff**: Linting and formatting (targets Python 3.11, Google docstring style)
- **mypy**: Strict mode type checking
- **basedpyright**: Additional type checking
- **semantic_release**: Version management from conventional commits

Pre-commit configuration in `.pre-commit-config.yaml` uses prek-compatible hooks.
