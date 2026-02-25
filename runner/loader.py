import yaml


def load_tables(path: str) -> list[str]:
    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "tables" not in data:
        raise ValueError("Missing required key: tables")

    tables = data["tables"]

    if not isinstance(tables, list) or len(tables) == 0:
        raise ValueError("tables must be a non-empty list")

    for item in tables:
        if not isinstance(item, str):
            raise ValueError(f"Each table must be a string, got: {type(item)}")

    return tables