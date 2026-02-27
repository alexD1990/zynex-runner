import yaml


def load_tables(path: str, ) -> tuple[list[dict], int | None]:
    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "tables" not in data:
        raise ValueError("Missing required key: tables")

    global_timeout = data.get("timeout_seconds", None)
    if global_timeout is not None and not isinstance(global_timeout, (int, float)):
        raise ValueError("timeout_seconds must be a number")

    fail_fast = data.get("fail_fast", False)
    if not isinstance(fail_fast, bool):
        raise ValueError("fail_fast must be a boolean")

    tables = data["tables"]

    if not isinstance(tables, list) or len(tables) == 0:
        raise ValueError("tables must be a non-empty list")

    result = []
    for item in tables:
        if isinstance(item, str):
            result.append({"name": item, "tags": {}, "timeout_seconds": global_timeout})
        elif isinstance(item, dict):
            if "name" not in item or not isinstance(item["name"], str):
                raise ValueError("Each table mapping must have a string 'name' key")
            tags = item.get("tags", {})
            if not isinstance(tags, dict):
                raise ValueError("tags must be a dict")
            timeout = item.get("timeout_seconds", global_timeout)
            if timeout is not None and not isinstance(timeout, (int, float)):
                raise ValueError("timeout_seconds must be a number")
            result.append({"name": item["name"], "tags": tags, "timeout_seconds": timeout})
        else:
            raise ValueError(f"Each table must be a string or mapping, got: {type(item)}")

    return result, fail_fast