import json
import sys
import uuid
from datetime import datetime, timezone
from importlib.metadata import version, PackageNotFoundError
import time
import threading

from zynex import check

def run_tables(tables: list[dict], fail_fast: bool = False) -> dict:
    run_id = str(uuid.uuid4())
    run_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    table_results = []
    modules_used: list[str] = []

    for entry in tables:
        table = entry["name"]
        tags = entry["tags"]
        timeout = entry.get("timeout_seconds")
        report = None
        error: Exception | None = None
        t_start = time.monotonic()

        def _run():
            nonlocal report, error
            try:
                report = check(source=table, render=False)
            except Exception as e:
                error = e

        thread = threading.Thread(target=_run)
        thread.start()
        thread.join(timeout=timeout)
        duration = round(time.monotonic() - t_start, 3)

        if thread.is_alive():
            print(f"Timeout processing table '{table}' after {timeout}s", file=sys.stderr)
            report = None
        elif error is not None:
            print(f"Error processing table '{table}': {type(error).__name__}: {error}", file=sys.stderr)
            report = None

        if report is not None:
            for m in report.modules:
                if m not in modules_used:
                    modules_used.append(m)

        if report is None:
            table_results.append({
                "table": table,
                "status": "failed",
                "duration_seconds": duration,
                "tags": tags,
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
            "duration_seconds": duration,
            "tags": tags,
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
        
        if fail_fast and top_status == "error":
            break
    try:
        zynex_version = version("zynex")
    except PackageNotFoundError:
        zynex_version = "unknown"

    try:
        runner_version = version("zynex-runner")
    except PackageNotFoundError:
        runner_version = "unknown"

    status_counts = {"ok": 0, "warning": 0, "error": 0, "failed": 0}
    for t in table_results:
        if t["status"] in status_counts:
            status_counts[t["status"]] += 1

    return {
        "run_id": run_id,
        "run_timestamp": run_timestamp,
        "modules": modules_used,
        "metadata": {
            "zynex_version": zynex_version,
            "runner_version": runner_version,
        },
        "summary": {
            "total_tables": len(table_results),
            **status_counts,
        },
        "tables": table_results,
    }

def write_output(payload: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)