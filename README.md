# OpenAPI Impact

[![CI](https://github.com/kyan9400/openapi-impact/actions/workflows/ci.yml/badge.svg)](https://github.com/kyan9400/openapi-impact/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-111827.svg)](LICENSE)

Detect breaking changes before an API contract reaches production.

OpenAPI Impact is a small Python library, command-line tool, and reusable GitHub Action. It compares two OpenAPI 3.0 or 3.1 documents from the perspective of existing consumers and produces a report that explains every classification.

## Quick start

```bash
python -m pip install .
openapi-impact examples/orders-v1.yaml examples/orders-v2.yaml
```

Example output:

```text
OpenAPI Impact
7 breaking · 2 non-breaking

[BREAKING] operation.id_changed · paths./orders/{order_id}.get
  operationId changed from 'getOrder' to 'findOrder'.
[BREAKING] operation.security_added · paths./orders/{order_id}.get.security
  The operation now requires authentication.
[BREAKING] response.removed · paths./orders/{order_id}.get.responses.404
  Response '404' was removed.
```

The command exits with status `1` when it finds a breaking change and `2` when an input document is invalid. Use `--fail-on never` for report-only workflows.

## What it detects

| Area | Examples |
| --- | --- |
| Paths and operations | Removed endpoints, added endpoints, changed `operationId` |
| Requests | New required parameters, removed parameters, required request bodies |
| Responses | Removed status codes, media types, headers, and changed response schemas |
| Security | Authentication added or schemes and required scopes changed |
| Schemas | Type or format changes, removed properties, new required properties |
| Constraints | Narrowed enums, nullable removal, closed objects, patterns, and unique arrays |
| Serialization | Changed parameter `style` or `explode` behavior |

Additive changes are reported separately rather than hidden. Popularity, naming style, and documentation wording do not affect compatibility results.

## Reports

```bash
# Human-readable terminal output
openapi-impact old.yaml new.yaml

# Pull-request summary
openapi-impact old.yaml new.yaml --format markdown --output impact.md

# Machine-readable automation
openapi-impact old.json new.json --format json --output impact.json

# GitHub code-scanning compatible output
openapi-impact old.yaml new.yaml --format sarif --output impact.sarif

# Report without blocking the pipeline
openapi-impact old.yaml new.yaml --fail-on never
```

## GitHub Action

```yaml
name: API compatibility

on: pull_request

jobs:
  openapi:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v7
      - uses: kyan9400/openapi-impact@v1
        with:
          base: contracts/openapi.base.yaml
          head: contracts/openapi.yaml
```

The action adds a Markdown report to the workflow summary, creates annotations for individual changes, and fails on breaking changes by default. Its `report` output exposes the generated file to later artifact or SARIF upload steps.

## Python API

```python
from openapi_impact import compare_specs
from openapi_impact.loader import load_spec

result = compare_specs(load_spec("old.yaml"), load_spec("new.yaml"))

for change in result.breaking_changes:
    print(change.code, change.location, change.message)
```

## Design choices

- **Deterministic:** the same documents always produce the same ordered report.
- **Consumer-focused:** a change is breaking when an existing client may need to change.
- **Offline by default:** external references are not downloaded and specifications never leave the machine.
- **Small dependency surface:** runtime parsing depends only on PyYAML.

OpenAPI is a broad standard. Version 1 focuses on high-signal structural compatibility rules rather than claiming exhaustive coverage of every JSON Schema keyword. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to propose another rule.

## License

[MIT](LICENSE)
