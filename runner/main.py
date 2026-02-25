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
        sys.exit(1)

    payload = run_tables(tables)
    write_output(payload, args.output)
    print(f"Done. Results written to {args.output}")


if __name__ == "__main__":
    main()