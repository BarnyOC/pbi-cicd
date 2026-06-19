import argparse
import json
import sys
from pathlib import Path


def extract_report_fields(report_dir: str, measures_only: bool = False) -> list[str]:
    report_path = Path(report_dir)
    visuals_dir = report_path / "definition" / "pages"

    if not visuals_dir.exists():
        return []

    fields = []
    for visual_json in sorted(visuals_dir.rglob("visuals/*/visual.json")):
        fields.extend(_extract_from_visual(visual_json, measures_only))

    return sorted(set(fields))


def _extract_from_visual(visual_json: Path, measures_only: bool = False) -> list[str]:
    try:
        doc = json.loads(visual_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return []

    query_state = doc.get("visual", {}).get("query", {}).get("queryState", {})
    if not query_state:
        return []

    parsed = tuple(
        _parse_field(proj.get("field", {}))
        for group in query_state.values()
        for proj in group.get("projections", [])
    )

    refs = tuple(r for r in parsed if r)

    return [name for name, kind in refs if not measures_only or kind == "Measure"]


def _parse_field(field: dict) -> tuple | None:
    for kind in ("Column", "Measure"):
        entry = field.get(kind)
        if not entry:
            continue
        entity = entry.get("Expression", {}).get("SourceRef", {}).get("Entity")
        prop = entry.get("Property")
        if entity and prop:
            return (f"{entity}.{prop}", kind)
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Extract field references from report visuals"
    )
    parser.add_argument("report", help="Path to a .Report directory")
    parser.add_argument(
        "-m", "--measures", action="store_true", help="Only list measures"
    )
    args = parser.parse_args()

    fields = extract_report_fields(args.report, measures_only=args.measures)
    print("\n".join(fields))


if __name__ == "__main__":
    main()
