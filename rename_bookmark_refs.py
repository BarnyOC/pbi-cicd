import argparse
import json
import sys
from pathlib import Path


def update_bookmarks(
    report_dir: str, name_map: dict[str, str], dry_run: bool
) -> list[str]:
    bookmarks_dir = Path(report_dir) / "definition" / "bookmarks"
    changes: list[str] = []

    if not bookmarks_dir.exists():
        return changes

    for bm_file in sorted(bookmarks_dir.glob("*.bookmark.json")):
        try:
            doc = json.loads(bm_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            continue

        file_changes: list[str] = []
        es = doc.get("explorationState", {})

        old_active = es.get("activeSection", "")
        if old_active in name_map:
            es["activeSection"] = name_map[old_active]
            file_changes.append(
                f"  activeSection: {old_active} -> {name_map[old_active]}"
            )

        sections = es.get("sections", {})
        for old_key in list(sections.keys()):
            if old_key in name_map:
                new_key = name_map[old_key]
                sections[new_key] = sections.pop(old_key)
                file_changes.append(f"  sections.{old_key} -> {new_key}")

        if file_changes:
            changes.append(f"{bm_file.name}:")
            changes.extend(file_changes)
            if not dry_run:
                bm_file.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    return changes


def main():
    parser = argparse.ArgumentParser(
        description="Update bookmark page references after page rename"
    )
    parser.add_argument("report", help="Path to a .Report directory")
    parser.add_argument(
        "name_map",
        type=argparse.FileType("r"),
        help="Path to JSON file with old->new page name mapping",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Show what would be updated without doing it",
    )
    args = parser.parse_args()

    name_map = json.load(args.name_map)
    changes = update_bookmarks(args.report, name_map, dry_run=args.dry_run)

    if not changes:
        print("No bookmark references to update.")
        return

    verb = "Would update" if args.dry_run else "Updated"
    print(f"{verb} {len([c for c in changes if c.endswith(':')])} bookmark file(s):")
    for line in changes:
        print(line)


if __name__ == "__main__":
    main()
