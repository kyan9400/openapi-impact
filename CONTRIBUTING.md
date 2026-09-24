# Contributing

Install the project in an isolated environment:

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
```

Before opening a pull request, run:

```bash
ruff check .
ruff format --check .
pytest
python -m build
```

Compatibility rules must include a focused test showing both the previous and new contract. Keep classifications deterministic and explain them from the perspective of an existing API consumer.

## Releasing

1. Update `version` in `pyproject.toml` and add the release notes to `CHANGELOG.md`.
2. Commit, then create and push a matching tag, for example `git tag v1.2.0 && git push origin v1.2.0`.

The [release workflow](.github/workflows/release.yml) checks that the tag matches the package version, builds the wheel and sdist, attaches them to the GitHub Release (creating it when it does not exist yet), and advances the major tag (`v1`) that `uses: kyan9400/openapi-impact@v1` resolves to.
