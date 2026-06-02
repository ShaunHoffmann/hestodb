# hestodb

[![Testing](https://github.com/nasa-hesto/hestodb/actions/workflows/testing.yml/badge.svg)](https://github.com/nasa-hesto/hestodb/actions/workflows/testing.yml)
[![Ruff Codestyle](https://github.com/nasa-hesto/hestodb/actions/workflows/codestyle.yml/badge.svg)](https://github.com/nasa-hesto/hestodb/actions/workflows/codestyle.yml)
[![pre-commit](https://github.com/nasa-hesto/hestodb/actions/workflows/precommit.yml/badge.svg)](https://github.com/nasa-hesto/hestodb/actions/workflows/precommit.yml)

This Python package is used by the NASA HESTO to parse and analyze reports provided by the Principal Investigators.

## Developer Setup

Install development dependencies and git hooks:

```bash
uv sync --dev
uv run pre-commit install
```

Run hooks manually across the repository:

```bash
uv run pre-commit run --all-files
```

## Database schema

The SQL schema source of truth is in `hesto/db/postgres_schema.sql`.

