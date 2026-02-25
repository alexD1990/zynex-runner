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


def make_report(rows=100, columns=2, column_names=None, results=None):
    """Lager en minimal ValidationReport-lookalike."""
    report = MagicMock()
    report.rows = rows
    report.columns = columns
    report.column_names = column_names or ["id", "name"]
    report.results = results or []
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

    def test_valid_yaml(self):
        path = self._write_yaml("tables:\n  - catalog.schema.a\n  - catalog.schema.b\n")
        result = load_tables(path)
        self.assertEqual(result, ["catalog.schema.a", "catalog.schema.b"])

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

    def test_non_string_element(self):
        path = self._write_yaml("tables:\n  - 42\n")
        with self.assertRaises(ValueError) as ctx:
            load_tables(path)
        self.assertIn("Each table must be a string", str(ctx.exception))


class TestRunTables(unittest.TestCase):

    def test_successful_table(self):
        result = make_result("null_ratio", "warning", "Nulls found", {"total_nulls": 5})
        report = make_report(results=[result])

        with patch("runner.output.check", return_value=report):
            payload = run_tables(["catalog.schema.table_x"])

        t = payload["tables"][0]
        self.assertEqual(t["table"], "catalog.schema.table_x")
        self.assertEqual(t["status"], "warning")
        self.assertEqual(t["rows"], 100)
        self.assertEqual(t["results"][0]["name"], "null_ratio")
        self.assertEqual(t["results"][0]["metrics"], {"total_nulls": 5})

    def test_none_return_marks_failed(self):
        with patch("runner.output.check", return_value=None):
            payload = run_tables(["catalog.schema.missing"])

        t = payload["tables"][0]
        self.assertEqual(t["status"], "failed")
        self.assertIsNone(t["rows"])
        self.assertIsNone(t["results"])

    def test_valueerror_marks_failed(self):
        with patch("runner.output.check", side_effect=ValueError("bad input")):
            payload = run_tables(["not_a_valid_table"])

        self.assertEqual(payload["tables"][0]["status"], "failed")

    def test_multiple_tables_continues_on_failure(self):
        ok_result = make_result("duplicate_rows", "ok", "No dupes")
        ok_report = make_report(results=[ok_result])

        with patch("runner.output.check", side_effect=[None, ok_report]):
            payload = run_tables(["bad.table", "good.table"])

        self.assertEqual(payload["tables"][0]["status"], "failed")
        self.assertEqual(payload["tables"][1]["status"], "ok")

    def test_status_aggregation_error_wins(self):
        results = [
            make_result("null_ratio", "warning"),
            make_result("duplicate_rows", "error"),
        ]
        report = make_report(results=results)

        with patch("runner.output.check", return_value=report):
            payload = run_tables(["catalog.schema.t"])

        self.assertEqual(payload["tables"][0]["status"], "error")

    def test_run_id_and_timestamp_present(self):
        with patch("runner.output.check", return_value=make_report()):
            payload = run_tables(["catalog.schema.t"])

        self.assertIn("run_id", payload)
        self.assertIn("run_timestamp", payload)
        self.assertRegex(payload["run_timestamp"], r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


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