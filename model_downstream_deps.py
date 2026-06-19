import argparse
import json
import sys
from pathlib import Path


def cmd_report_deps(args):
    model_path = Path(args.model).resolve()
    root = Path(args.root).resolve()

    found = []
    for pbir in sorted(root.rglob("definition.pbir")):
        ref = _read_bypath(pbir)
        if ref is None:
            continue
        report_root = pbir.parent
        target = (report_root / ref).resolve()
        if target == model_path:
            found.append(report_root.name)

    for name in found:
        print(name)


def _read_bypath(pbir_path: Path) -> str | None:
    try:
        doc = json.loads(pbir_path.read_text(encoding="utf-8"))
        ref = doc.get("datasetReference", {}).get("byPath", {})
        return ref.get("path")
    except (json.JSONDecodeError, KeyError, FileNotFoundError):
        return None


def main():
    parser = argparse.ArgumentParser(prog="model_downstream_deps")
    parser.add_argument(
        "--root", default="src", help="Root directory to scan for reports"
    )

    sub = parser.add_subparsers(dest="command", required=True)
    sub.parser = sub.add_parser(
        "report-deps", help="List reports that depend on a given model"
    )
    sub.parser.add_argument("model", help="Path to the .SemanticModel directory")

    args = parser.parse_args()
    cmd_report_deps(args)


if __name__ == "__main__":
    main()
