# pre-commit-ensure-uv

A [pre-commit](https://pre-commit.com/) hook that ensures [uv](https://github.com/astral-sh/uv) is installed and available.

Works with both [pre-commit](https://pre-commit.com/) and [prek](https://github.com/j178/prek).

## Usage

Add this to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/bitflight-devops/pre-commit-ensure-uv
    rev: v0.1.0
    hooks:
      - id: ensure-uv
```

Place it **first** in your repos list so uv is available for subsequent hooks.

## Behavior

| Condition                 | Action                                      |
| ------------------------- | ------------------------------------------- |
| uv in PATH                | Pass silently                               |
| uv installed, not in PATH | Re-run hooks with corrected PATH            |
| uv not installed          | Install uv, then re-run with corrected PATH |

When uv needs to be added to PATH, the hook automatically re-runs all hooks with the corrected environment. No shell restart required.

## Platform Support

- Linux
- macOS
- Windows

## Installation Method

Uses the official uv installer:

- **Unix**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Windows**: `powershell irm https://astral.sh/uv/install.ps1 | iex`

## License

MIT
