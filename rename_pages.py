import argparse
import json
import re
import sys
from pathlib import Path

GUID_RE = re.compile(r"^[0-9a-f]{20}$")


def _sanitize(name: str) -> str:
    name = name.replace("\0", "")
    name = name.replace("/", "_")
    name = name.replace("\\", "_")
    name = name.replace(" ", "_")
    name = name.strip("._ ")
    if len(name) > 120:
        name = name[:120].rstrip("_")
    return name or "unnamed"


def rename_pages(report_dir: str, dry_run: bool = False) -> list[tuple[str, str]]:
    report_path = Path(report_dir)
    pages_dir = report_path / "definition" / "pages"

    if not pages_dir.exists():
        raise FileNotFoundError(f"No pages directory found in {report_dir}")

    name_map: dict[str, str] = {}
    target_names: set[str] = set()
    actions: list[tuple[str, str]] = []

    for page_dir in sorted(pages_dir.iterdir()):
        if not page_dir.is_dir():
            continue
        page_json_file = page_dir / "page.json"
        if not page_json_file.exists():
            continue

        doc = json.loads(page_json_file.read_text(encoding="utf-8"))
        display_name = doc.get("displayName", "").strip()
        if not display_name:
            continue

        old_name = page_dir.name
        if not GUID_RE.match(old_name):
            continue

        new_name = _sanitize(display_name)
        final_name = new_name
        counter = 1
        while final_name in target_names or (
            not dry_run and (pages_dir / final_name).exists()
        ):
            final_name = f"{new_name}_{counter}"
            counter += 1

        target_names.add(final_name)
        name_map[old_name] = final_name
        actions.append((old_name, final_name))

    if not dry_run:
        for old_name, new_name in actions:
            old_dir = pages_dir / old_name
            new_dir = pages_dir / new_name
            old_dir.rename(new_dir)

            pf = new_dir / "page.json"
            doc = json.loads(pf.read_text(encoding="utf-8"))
            doc["name"] = new_name
            pf.write_text(json.dumps(doc, indent=2), encoding="utf-8")

        pm = pages_dir / "pages.json"
        if pm.exists():
            doc = json.loads(pm.read_text(encoding="utf-8"))
            doc["pageOrder"] = [name_map.get(p, p) for p in doc.get("pageOrder", [])]
            if doc.get("activePageName") in name_map:
                doc["activePageName"] = name_map[doc["activePageName"]]
            pm.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    return actions


def main():
    parser = argparse.ArgumentParser(
        description="Rename auto-generated PBIP page directories to their displayName"
    )
    parser.add_argument("report", help="Path to a .Report directory")
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Show what would be renamed without doing it",
    )
    args = parser.parse_args()

    actions = rename_pages(args.report, dry_run=args.dry_run)

    if not actions:
        print("No pages to rename.", file=sys.stderr)
        return

    print(
        f"{'Would rename' if args.dry_run else 'Renamed'} {len(actions)} page(s):",
        file=sys.stderr,
    )
    for old, new in actions:
        print(f"  {old}  ->  {new}", file=sys.stderr)

    print(json.dumps(dict(actions)))


if __name__ == "__main__":
    main()
