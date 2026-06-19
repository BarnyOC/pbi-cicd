import re
import sys
from pathlib import Path

OBJ_RE = re.compile(r"^(\t*)(\w+)\s+(.+?)(?:\s*=\s*(.*))?$")
PROP_RE = re.compile(r"^(\t*)(\w[\w.]*):\s*(.*)$")
BOOL_PROP_RE = re.compile(r"^(\t*)(\w[\w.]*)$")


def parse_model(model_dir: str) -> list[tuple[str, str, str]]:
    tables_dir = Path(model_dir) / "definition" / "tables"
    if not tables_dir.exists():
        raise FileNotFoundError(f"No tables directory found in {model_dir}")

    entries = []
    table = None
    field_name = None
    field_kind = None

    def flush():
        nonlocal field_name, field_kind
        if table is not None and field_name is not None:
            entries.append((table, field_name, field_kind))
        field_name = None
        field_kind = None

    for tmdl_file in sorted(tables_dir.glob("*.tmdl")):
        with open(tmdl_file, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                stripped = line.strip()
                if not stripped or stripped.startswith("//"):
                    continue

                m = OBJ_RE.match(line)
                if m:
                    kind = m.group(2)
                    name = m.group(3).strip("'")

                    if kind == "table":
                        flush()
                        table = name
                    elif kind in ("column", "measure"):
                        flush()
                        if table is not None:
                            field_name = name
                            field_kind = kind
                    else:
                        flush()
                    continue

                m = PROP_RE.match(line)
                if m and m.group(2) == "dataType" and field_kind == "column":
                    field_kind = m.group(3)

        flush()

    return entries


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="List fields in a semantic model")
    parser.add_argument("model", help="Path to a .SemanticModel directory")
    parser.add_argument(
        "-d", "--datatypes", action="store_true", help="Include data types in output"
    )
    parser.add_argument(
        "-m", "--measures", action="store_true", help="Only list measures"
    )
    args = parser.parse_args()

    entries = parse_model(args.model)

    filtered = tuple(
        (t, n, k) for t, n, k in entries if not args.measures or k == "measure"
    )

    lines = tuple(
        f"{t}.{n}: {k}" if args.datatypes else f"{t}.{n}" for t, n, k in filtered
    )

    for f in sorted(lines):
        print(f)
