# Zynex Runner MVP

Runs Zynex validation on a list of tables defined in a YAML file.

## Usage
```bash
python -m runner.main example/tables.yml output.json
```

Or after install:
```bash
zynex-runner example/tables.yml output.json
```

## Input format
```yaml
tables:
  - "catalog.schema.table_x"
  - "catalog.schema.table_y"
```

## Output

JSON file with run metadata and per-table validation results.