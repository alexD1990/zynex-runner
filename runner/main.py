import argparse
import sys

from runner.loader import load_tables
from runner.output import run_tables, write_output


def main():
    parser = argparse.ArgumentParser(description="Zynex Runner MVP")
    parser.add_argument("input", help="Path to YAML file with tables")
    parser.add_argument("output", help="Path to output JSON file")
    args = parser.parse_args()

    try:
        tables = load_tables(args.input)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    payload = run_tables(tables)
    write_output(payload, args.output)
    print(f"Done. Results written to {args.output}")

    has_error_or_failed = any(
        t["status"] in ("error", "failed") for t in payload["tables"]
    )
    sys.exit(1 if has_error_or_failed else 0)

if __name__ == "__main__":
    main()