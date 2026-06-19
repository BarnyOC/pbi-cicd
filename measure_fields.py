import argparse
import re
import sys
from pathlib import Path

TABLE_COL_RE = re.compile(r"'([^']+)'\[([^\]]+)\]")
NAKED_COL_RE = re.compile(r"(\w+)\[([^\]]+)\]")
BARE_MEASURE_RE = re.compile(r"\[([^\]]+)\]")
OBJ_RE = re.compile(r"^(\t*)(\w+)\s+(.+?)(?:\s*=\s*(.*))?$")
PROP_RE = re.compile(r"^(\t*)(\w[\w.]*):\s*(.*)$")


def _table_for_file(tmdl_file: Path) -> str:
    with open(tmdl_file, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^(\t*)table\s+(.+)$", line)
            if m:
                return m.group(2).strip("'")
    return ""


def _collect_dax(lines: list[str], measure_indent: int) -> str:
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines):
        return ""
    if lines[i].strip() == "```":
        i += 1
    parts = []
    while i < len(lines):
        l = lines[i]
        stripped = l.strip()
        if stripped == "```":
            i += 1
            break
        if not stripped:
            i += 1
            continue
        m = OBJ_RE.match(l)
        if m and len(m.group(1)) <= measure_indent + 1:
            break
        m = PROP_RE.match(l)
        if m and len(m.group(1)) <= measure_indent + 1:
            break
        parts.append(l.rstrip("\n"))
        i += 1
    return " ".join(parts).strip()


def _build_type_map(model_dir: str) -> dict[str, str]:
    tables_dir = Path(model_dir) / "definition" / "tables"
    type_map = {}
    table = None
    field_name = None
    field_kind = None

    def flush():
        nonlocal field_name, field_kind
        if table is not None and field_name is not None:
            type_map[f"{table}.{field_name}"] = field_kind
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
                        field_name = name
                        field_kind = kind
                    else:
                        flush()
                    continue
                m = PROP_RE.match(line)
                if m and m.group(2) == "dataType" and field_kind == "column":
                    field_kind = m.group(3)
        flush()
    return type_map


def resolve(
    model_dir: str, measure_names: list[str], show_datatypes: bool = False
) -> list[str]:
    tables_dir = Path(model_dir) / "definition" / "tables"
    if not tables_dir.exists():
        raise FileNotFoundError(f"No tables directory found in {model_dir}")

    all_measures = {}
    measure_table = {}

    for tmdl_file in sorted(tables_dir.glob("*.tmdl")):
        with open(tmdl_file, encoding="utf-8") as f:
            content = f.read()

        for m in re.finditer(
            r"^(\t*)measure\s+(.+?)[ \t]*=[ \t]*([^\n]*)", content, re.MULTILINE
        ):
            indent = len(m.group(1))
            name = m.group(2).strip("'")
            table_name = _table_for_file(tmdl_file)
            inline_value = m.group(3).strip()

            dax = inline_value
            if not dax:
                pos = m.end()
                lines = content[pos:].split("\n")
                dax = _collect_dax(lines, indent)

            if dax:
                key = (table_name, name)
                all_measures[key] = dax
                measure_table[name] = table_name

    queue = []
    for mn in measure_names:
        if "." in mn:
            parts = mn.split(".", 1)
            key = (parts[0], parts[1])
            if key in all_measures:
                queue.append(key)
        else:
            for t, m in all_measures:
                if m == mn:
                    queue.append((t, m))
                    break

    deps = set()
    seen = set(queue)

    while queue:
        key = queue.pop()
        dax = all_measures.get(key)
        if not dax:
            continue

        for table, col in TABLE_COL_RE.findall(dax):
            deps.add(f"{table}.{col}")

        for table, col in NAKED_COL_RE.findall(dax):
            deps.add(f"{table}.{col}")

        for bare in BARE_MEASURE_RE.findall(dax):
            resolved = _resolve(bare, all_measures, key[0])
            if resolved and resolved not in seen:
                seen.add(resolved)
                deps.add(f"{resolved[0]}.{resolved[1]}")
                if resolved in all_measures:
                    queue.append(resolved)

    result = sorted(deps)
    if show_datatypes:
        type_map = _build_type_map(model_dir)
        result = sorted(f"{k}: {type_map.get(k, 'unknown')}" for k in deps)

    return result


def _resolve(bare_name: str, all_measures: dict, current_table: str) -> tuple | None:
    if bare_name in {m for _, m in all_measures.keys()}:
        for t, m in all_measures:
            if m == bare_name:
                return (t, m)
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Resolve transitive field dependencies of a measure"
    )
    parser.add_argument("model", help="Path to a .SemanticModel directory")
    parser.add_argument(
        "measures",
        nargs="+",
        help="Measure name(s) to resolve (qualified Table.Measure or bare name)",
    )
    parser.add_argument(
        "-d",
        "--datatypes",
        action="store_true",
        help="Include data types in output",
    )
    args = parser.parse_args()

    fields = resolve(args.model, args.measures, show_datatypes=args.datatypes)
    for f in fields:
        print(f)


if __name__ == "__main__":
    main()
