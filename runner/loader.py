import yaml


def load_tables(path: str) -> list[dict]:
    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "tables" not in data:
        raise ValueError("Missing required key: tables")

    tables = data["tables"]

    if not isinstance(tables, list) or len(tables) == 0:
        raise ValueError("tables must be a non-empty list")

    result = []
    for item in tables:
        if isinstance(item, str):
            result.append({"name": item, "tags": {}})
        elif isinstance(item, dict):
            if "name" not in item or not isinstance(item["name"], str):
                raise ValueError(f"Each table mapping must have a string 'name' key")
            tags = item.get("tags", {})
            if not isinstance(tags, dict):
                raise ValueError(f"tags must be a dict")
            result.append({"name": item["name"], "tags": tags})
        else:
            raise ValueError(f"Each table must be a string or mapping, got: {type(item)}")

    return result