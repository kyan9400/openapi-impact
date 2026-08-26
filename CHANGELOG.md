# Changelog

All notable changes to this project are documented here.

## 1.1.0 — 2026-08-26

- Add SARIF 2.1.0 output for code-scanning integrations.
- Detect removed media types and response headers.
- Detect parameter serialization and authentication-scope changes.
- Detect nullable removal, closed object schemas, changed patterns, and unique-array constraints.
- Expose the generated report path from the reusable GitHub Action.

## 1.0.0 — 2026-08-26

- Detect breaking path, operation, parameter, response, authentication, and schema changes.
- Support OpenAPI 3.0 and 3.1 documents in JSON or YAML.
- Add text, Markdown, JSON, and GitHub Actions reporting.
- Publish a reusable composite GitHub Action.
