import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

sys.modules["zynex"] = MagicMock()
sys.modules["pyspark"] = MagicMock()
sys.modules["pyspark.sql"] = MagicMock()

from runner.loader import load_tables
from runner.output import run_tables, write_output


def make_report(rows=100, columns=2, column_names=None, results=None, modules=None):
    report = MagicMock()
    report.rows = rows
    report.columns = columns
    report.column_names = column_names or ["id", "name"]
    report.results = results or []
    report.modules = modules or ["core_quality"]
    return report


def make_result(name="null_ratio", status="ok", message="All good", metrics=None):
    r = MagicMock()
    r.name = name
    r.status = status
    r.message = message
    r.metrics = metrics or {}
    return r


class TestLoader(unittest.TestCase):

    def _write_yaml(self, content: str) -> str:
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
        f.write(content)
        f.close()
        return f.name

    def test_simple_string_syntax(self):
        path = self._write_yaml("tables:\n  - catalog.schema.a\n  - catalog.schema.b\n")
        tables, fail_fast = load_tables(path)
        self.assertEqual(len(tables), 2)
        self.assertEqual(tables[0], {"name": "catalog.schema.a", "tags": {}, "timeout_seconds": None})
        self.assertEqual(tables[1], {"name": "catalog.schema.b", "tags": {}, "timeout_seconds": None})
        self.assertFalse(fail_fast)

    def test_mapping_syntax_with_tags(self):
        path = self._write_yaml(
            "tables:\n"
            "  - name: catalog.schema.a\n"
            "    tags:\n"
            "      team: finance\n"
            "      criticality: high\n"
        )
        tables, _ = load_tables(path)
        self.assertEqual(tables[0]["tags"], {"team": "finance", "criticality": "high"})

    def test_mixed_syntax(self):
        path = self._write_yaml(
            "tables:\n"
            "  - catalog.schema.a\n"
            "  - name: catalog.schema.b\n"
            "    tags:\n"
            "      team: finance\n"
        )
        tables, _ = load_tables(path)
        self.assertEqual(tables[0]["tags"], {})
        self.assertEqual(tables[1]["tags"], {"team": "finance"})

    def test_global_timeout_inherited(self):
        path = self._write_yaml(
            "timeout_seconds: 300\n"
            "tables:\n"
            "  - catalog.schema.a\n"
        )
        tables, _ = load_tables(path)
        self.assertEqual(tables[0]["timeout_seconds"], 300)

    def test_per_table_timeout_overrides_global(self):
        path = self._write_yaml(
            "timeout_seconds: 300\n"
            "tables:\n"
            "  - name: catalog.schema.a\n"
            "    timeout_seconds: 60\n"
        )
        tables, _ = load_tables(path)
        self.assertEqual(tables[0]["timeout_seconds"], 60)

    def test_fail_fast_true(self):
        path = self._write_yaml(
            "fail_fast: true\n"
            "tables:\n"
            "  - catalog.schema.a\n"
        )
        _, fail_fast = load_tables(path)
        self.assertTrue(fail_fast)

    def test_fail_fast_default_false(self):
        path = self._write_yaml("tables:\n  - catalog.schema.a\n")
        _, fail_fast = load_tables(path)
        self.assertFalse(fail_fast)

    def test_missing_tables_key(self):
        path = self._write_yaml("other_key:\n  - something\n")
        with self.assertRaises(ValueError) as ctx:
            load_tables(path)
        self.assertIn("Missing required key: tables", str(ctx.exception))

    def test_empty_tables_list(self):
        path = self._write_yaml("tables: []\n")
        with self.assertRaises(ValueError) as ctx:
            load_tables(path)
        self.assertIn("non-empty list", str(ctx.exception))

    def test_invalid_tags_type(self):
        path = self._write_yaml(
            "tables:\n"
            "  - name: catalog.schema.a\n"
            "    tags: not_a_dict\n"
        )
        with self.assertRaises(ValueError) as ctx:
            load_tables(path)
        self.assertIn("tags must be a dict", str(ctx.exception))

    def test_invalid_timeout_type(self):
        path = self._write_yaml(
            "timeout_seconds: not_a_number\n"
            "tables:\n"
            "  - catalog.schema.a\n"
        )
        with self.assertRaises(ValueError) as ctx:
            load_tables(path)
        self.assertIn("timeout_seconds must be a number", str(ctx.exception))

    def test_invalid_fail_fast_type(self):
        path = self._write_yaml(
            "fail_fast: maybe\n"
            "tables:\n"
            "  - catalog.schema.a\n"
        )
        with self.assertRaises(ValueError) as ctx:
            load_tables(path)
        self.assertIn("fail_fast must be a boolean", str(ctx.exception))


class TestRunTables(unittest.TestCase):

    def _make_entries(self, names):
        return [{"name": n, "tags": {}, "timeout_seconds": None} for n in names]

    def test_successful_table(self):
        result = make_result("null_ratio", "warning", "Nulls found", {"total_nulls": 5})
        report = make_report(results=[result])

        with patch("runner.output.check", return_value=report):
            payload = run_tables(self._make_entries(["catalog.schema.table_x"]))

        t = payload["tables"][0]
        self.assertEqual(t["table"], "catalog.schema.table_x")
        self.assertEqual(t["status"], "warning")
        self.assertEqual(t["rows"], 100)
        self.assertEqual(t["results"][0]["name"], "null_ratio")
        self.assertEqual(t["results"][0]["metrics"], {"total_nulls": 5})

    def test_none_return_marks_failed(self):
        with patch("runner.output.check", return_value=None):
            payload = run_tables(self._make_entries(["catalog.schema.missing"]))

        t = payload["tables"][0]
        self.assertEqual(t["status"], "failed")
        self.assertIsNone(t["rows"])
        self.assertIsNone(t["results"])

    def test_exception_marks_failed(self):
        with patch("runner.output.check", side_effect=ValueError("bad input")):
            payload = run_tables(self._make_entries(["not_a_valid_table"]))

        self.assertEqual(payload["tables"][0]["status"], "failed")

    def test_multiple_tables_continues_on_failure(self):
        ok_result = make_result("duplicate_rows", "ok", "No dupes")
        ok_report = make_report(results=[ok_result])

        with patch("runner.output.check", side_effect=[None, ok_report]):
            payload = run_tables(self._make_entries(["bad.table", "good.table"]))

        self.assertEqual(payload["tables"][0]["status"], "failed")
        self.assertEqual(payload["tables"][1]["status"], "ok")

    def test_status_aggregation_error_wins(self):
        results = [
            make_result("null_ratio", "warning"),
            make_result("duplicate_rows", "error"),
        ]
        report = make_report(results=results)

        with patch("runner.output.check", return_value=report):
            payload = run_tables(self._make_entries(["catalog.schema.t"]))

        self.assertEqual(payload["tables"][0]["status"], "error")

    def test_run_id_and_timestamp_present(self):
        with patch("runner.output.check", return_value=make_report()):
            payload = run_tables(self._make_entries(["catalog.schema.t"]))

        self.assertIn("run_id", payload)
        self.assertIn("run_timestamp", payload)
        self.assertRegex(payload["run_timestamp"], r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

    def test_metadata_present(self):
        with patch("runner.output.check", return_value=make_report()):
            payload = run_tables(self._make_entries(["catalog.schema.t"]))

        self.assertIn("metadata", payload)
        self.assertIn("zynex_version", payload["metadata"])
        self.assertIn("runner_version", payload["metadata"])

    def test_summary_counts(self):
        ok_report = make_report(results=[make_result("r", "ok")])
        err_report = make_report(results=[make_result("r", "error")])

        with patch("runner.output.check", side_effect=[ok_report, None, err_report]):
            payload = run_tables(self._make_entries(["t.a", "t.b", "t.c"]))

        s = payload["summary"]
        self.assertEqual(s["total_tables"], 3)
        self.assertEqual(s["ok"], 1)
        self.assertEqual(s["failed"], 1)
        self.assertEqual(s["error"], 1)
        self.assertEqual(s["warning"], 0)

    def test_duration_seconds_present(self):
        with patch("runner.output.check", return_value=make_report()):
            payload = run_tables(self._make_entries(["catalog.schema.t"]))

        self.assertIn("duration_seconds", payload["tables"][0])
        self.assertIsInstance(payload["tables"][0]["duration_seconds"], float)

    def test_tags_passed_through(self):
        entries = [{"name": "catalog.schema.t", "tags": {"team": "finance"}, "timeout_seconds": None}]

        with patch("runner.output.check", return_value=make_report()):
            payload = run_tables(entries)

        self.assertEqual(payload["tables"][0]["tags"], {"team": "finance"})

    def test_empty_tags_default(self):
        with patch("runner.output.check", return_value=make_report()):
            payload = run_tables(self._make_entries(["catalog.schema.t"]))

        self.assertEqual(payload["tables"][0]["tags"], {})

    def test_fail_fast_stops_on_error(self):
        ok_report = make_report(results=[make_result("r", "ok")])
        err_report = make_report(results=[make_result("r", "error")])
        ok_report2 = make_report(results=[make_result("r", "ok")])

        with patch("runner.output.check", side_effect=[ok_report, err_report, ok_report2]):
            payload = run_tables(
                self._make_entries(["t.a", "t.b", "t.c"]),
                fail_fast=True
            )

        self.assertEqual(len(payload["tables"]), 2)
        self.assertEqual(payload["tables"][1]["status"], "error")

    def test_fail_fast_false_continues(self):
        err_report = make_report(results=[make_result("r", "error")])
        ok_report = make_report(results=[make_result("r", "ok")])

        with patch("runner.output.check", side_effect=[err_report, ok_report]):
            payload = run_tables(
                self._make_entries(["t.a", "t.b"]),
                fail_fast=False
            )

        self.assertEqual(len(payload["tables"]), 2)

    def test_fail_fast_does_not_stop_on_failed(self):
        with patch("runner.output.check", side_effect=[None, make_report()]):
            payload = run_tables(
                self._make_entries(["t.a", "t.b"]),
                fail_fast=True
            )

        self.assertEqual(len(payload["tables"]), 2)


class TestWriteOutput(unittest.TestCase):

    def test_writes_valid_json(self):
        payload = {"run_id": "abc", "tables": []}
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        write_output(payload, path)

        with open(path) as f:
            loaded = json.load(f)

        self.assertEqual(loaded["run_id"], "abc")


if __name__ == "__main__":
    unittest.main(verbosity=2)