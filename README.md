# zynex-runner

Batch validation runner for [zynex](https://pypi.org/project/zynex/).

Reads a YAML file with a list of tables, runs `zynex.check()` on each,
and writes a structured JSON report.

Designed to run as a **Databricks Job** — not interactively.

---

## Installation

`zynex-runner` is not published to PyPI. Install directly from GitHub:
```bash
pip install git+https://github.com/<your-org>/zynex-runner.git
```

`zynex` is automatically installed as a dependency.

---

## Usage
```bash
zynex-runner input.yml output.json
```

Or:
```bash
python -m runner.main input.yml output.json
```

| Argument | Description |
|---|---|
| `input.yml` | YAML file listing tables to validate |
| `output.json` | Path where JSON results will be written |

---

## Input Format
```yaml
tables:
  - "catalog.schema.table_a"
  - "catalog.schema.table_b"
```


---

## Output Format
```json
{
  "run_id": "...",
  "run_timestamp": "2026-02-27T10:00:00Z",
  "modules": ["core_quality"],
  "tables": [
    {
      "table": "catalog.schema.table_a",
      "status": "ok | warning | error | failed",
      "rows": 240000,
      "columns": 10,
      "column_names": ["id", "name"],
      "results": [
        {
          "name": "duplicate_rows",
          "status": "warning",
          "message": "...",
          "metrics": {}
        }
      ]
    }
  ]
}
```


---

## How It Works

1. Reads and validates the YAML input file
2. Calls `zynex.check(source=table, render=False)` for each table
3. A single table failure never stops remaining tables from running
4. Writes all results to a single JSON file

---

## I/O Contracts

All frozen contracts live in [`zynex-system`]

| Contract | What it covers |
|---|---|
| `runner-input.md` | YAML input schema |
| `runner-output.md` | JSON output schema |
| `integration.md` | How runner calls zynex |
| `zynex-api.md` | zynex public API |

---

## Requirements

- Python 3.10+
- Databricks / Spark environment
- `zynex>=1.0.0` (installed automatically)