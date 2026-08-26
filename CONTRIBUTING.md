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
