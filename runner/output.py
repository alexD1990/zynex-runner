import json
import sys
import uuid
from datetime import datetime, timezone

from zynex import check


def run_tables(tables: list[str]) -> dict:
    run_id = str(uuid.uuid4())
    run_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    table_results = []

    for table in tables:
        report = None
        try:
            report = check(source=table, render=False)
        except Exception as e:
            print(f"Error processing table '{table}': {type(e).__name__}: {e}", file=sys.stderr)

        if report is None:
            table_results.append({
                "table": table,
                "status": "failed",
                "rows": None,
                "columns": None,
                "column_names": None,
                "results": None,
            })
            continue

        # Derive top-level status from results
        statuses = [r.status for r in report.results]
        if "error" in statuses:
            top_status = "error"
        elif "warning" in statuses:
            top_status = "warning"
        else:
            top_status = "ok"

        table_results.append({
            "table": table,
            "status": top_status,
            "rows": report.rows,
            "columns": report.columns,
            "column_names": report.column_names,
            "results": [
                {
                    "name": r.name,
                    "status": r.status,
                    "message": r.message,
                    "metrics": r.metrics,
                }
                for r in report.results
            ],
        })

    return {
        "run_id": run_id,
        "run_timestamp": run_timestamp,
        "modules": ["core_quality"],
        "tables": table_results,
    }


def write_output(payload: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)