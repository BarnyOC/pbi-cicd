import argparse
import json
import re
import sys
from pathlib import Path

GUID_RE = re.compile(r"^[0-9a-f]{20}$")


def _get_custom_title(vc: dict) -> str | None:
    vco = vc.get("visualContainerObjects")
    if not vco:
        return None
    title = vco.get("title", [])
    if not title:
        return None
    props = title[0].get("properties", {})
    text = props.get("text")
    if text and isinstance(text, str) and text.strip():
        return text.strip()
    return None


def _extract_field_ref(field: dict) -> str | None:
    for kind in ("Column", "Measure"):
        entry = field.get(kind)
        if not entry:
            continue
        entity = entry.get("Expression", {}).get("SourceRef", {}).get("Entity")
        prop = entry.get("Property")
        if entity and prop:
            return f"{entity}.{prop}"
    return None


def _sanitize(name: str) -> str:
    name = name.replace("\0", "")
    name = name.replace("/", "_")
    name = name.replace("\\", "_")
    name = name.replace(" ", "_")
    name = name.strip("._ ")
    if len(name) > 120:
        name = name[:120].rstrip("_")
    return name or "unnamed"


def derive_name(visual: dict) -> str | None:
    vc = visual.get("visual", {})
    visual_type = vc.get("visualType", "")

    title = _get_custom_title(vc)
    if title:
        return _sanitize(title)

    if not visual_type:
        return None

    parts = [visual_type]
    query_state = vc.get("query", {}).get("queryState", {})
    if query_state:
        for role in sorted(query_state.keys()):
            projections = query_state[role].get("projections", [])
            role_fields = []
            for proj in projections:
                ref = _extract_field_ref(proj.get("field", {}))
                if ref:
                    role_fields.append(ref)
            if role_fields:
                parts.append("+".join(role_fields))

    name = "~".join(parts)
    return _sanitize(name)


def find_visuals(report_dir: str) -> list[tuple[Path, dict]]:
    results = []
    for vjson in sorted(Path(report_dir).rglob("visuals/*/visual.json")):
        try:
            doc = json.loads(vjson.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            continue
        results.append((vjson, doc))
    return results


def rename_visuals(
    report_dir: str, dry_run: bool = False
) -> list[tuple[str, str, str]]:
    actions = []
    target_names = set()

    for vjson_path, doc in find_visuals(report_dir):
        visual_dir = vjson_path.parent
        old_name = visual_dir.name

        if not GUID_RE.match(old_name):
            continue

        new_name = derive_name(doc)
        if not new_name:
            continue

        vc = doc.get("visual", {})
        if _get_custom_title(vc):
            source = "title"
        else:
            source = vc.get("visualType", "?")

        final_name = new_name
        counter = 1
        while final_name in target_names or (
            not dry_run and (visual_dir.parent / final_name).exists()
        ):
            final_name = f"{new_name}_{counter}"
            counter += 1

        target_names.add(final_name)
        actions.append((old_name, final_name, source))

        if not dry_run:
            visual_dir.rename(visual_dir.parent / final_name)

    return actions


def main():
    parser = argparse.ArgumentParser(
        description="Rename auto-generated PBIP visual directories to human-readable names"
    )
    parser.add_argument("report", help="Path to a .Report directory")
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Show what would be renamed without doing it",
    )
    args = parser.parse_args()

    actions = rename_visuals(args.report, dry_run=args.dry_run)

    if not actions:
        print("No visuals to rename.")
        return

    print(f"{'Would rename' if args.dry_run else 'Renamed'} {len(actions)} visual(s):")
    for old, new, source in actions:
        print(f"  {old}  ->  {new}  ({source})")


if __name__ == "__main__":
    main()
