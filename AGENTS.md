# Agent context — pbi-cicd

This is a collection of Python 3.12+ scripts for Power BI Project (PBIP) validation and maintenance. Zero external dependencies — stdlib only.

---

## Repository structure

```
├── AGENTS.md                          # this file
├── README.md                          # human documentation
├── measure_fields.py                  # transitive DAX dependency resolver (TMDL → DAX → deps)
├── model_downstream_deps.py           # byPath report discovery (definition.pbir scanner)
├── model_fields.py                    # TMDL parser: list columns + measures from .SemanticModel
├── rename_bookmark_refs.py           # bookmark page reference updater
├── rename_pages.py                    # page directory renamer (displayName → dir name)
├── rename_visuals.py                  # visual directory renamer (title/fields → dir name)
├── report_fields.py                   # visual.json parser: list field refs from .Report
└── .gitignore                         # ignores .venv/
```

---

## Technical details

### TMDL parsing (`model_fields.py`, `measure_fields.py`)
- TMDL is tab-indented, line-oriented. Not valid JSON or YAML.
- A state-machine parser (~60 lines) suffices: track `table` context, flush on new object declarations.
- Object lines match `^(\t*)(\w+)\s+(.+?)(?:\s*=\s*(.*))?$` — group 2 is kind (table/column/measure/etc), group 3 is name, group 4 is optional inline value (DAX for measures).
- Property lines match `^(\t*)(\w[\w.]*):\s*(.*)$` — group 2 is property name, group 3 is value.
- `dataType` property on a column replaces the kind to allow `--datatypes` output format (`Table.Col: dataType`).
- Multi-line DAX (fenced with triple backticks) is handled by `_collect_dax()` in `measure_fields.py`.

### Report field extraction (`report_fields.py`)
- Scans `definition/pages/*/visuals/*/visual.json`.
- Field references live at `visual.query.queryState[].projections[].field.{Column,Measure}.Expression.SourceRef.Entity` (table) + `.Property` (column name).
- Output format: `Table.Col` (flat, compatible with `comm(1)`).
- Supports `--measures` flag to filter to `Measure`-kind fields only.
- Data types are NOT present in report JSONs — only in TMDL.

### Model downstream discovery (`model_downstream_deps.py`)
- Scans `definition.pbir` files for `datasetReference.byPath.path`.
- Assumes `byPath` (relative path to `.SemanticModel`), NOT `byConnection`.
- Subcommand-driven: `python model_downstream_deps.py report-deps <model>`.

### Measure transitive dependency resolution (`measure_fields.py`)
- Parses all measures across all TMDL files, builds a `{(table, name): dax}` map.
- Uses BFS to resolve transitive column/measure dependencies.
- DAX patterns extracted:
  - `'Table'[Column]` — fully qualified
  - `Table[Column]` — naked table name
  - `[BareMeasure]` — bare measure reference, resolved by name lookup (ambiguous if multiple tables have same measure name).
- Regex bug fixed: use `[ \t]*=[ \t]*([^\n]*)` instead of `\s*=\s*(.*?)$` to avoid `$` + `re.MULTILINE` issues with internal newlines.

### Visual renaming (`rename_visuals.py`)
- Skips directories whose name doesn't match the GUID pattern `[0-9a-f]{20}`.
- Name priority: custom title from `visualContainerObjects.title[].properties.text` → derived `visualType~field1+field2~...`.
- Collision-safe via `_1`, `_2` suffixes.
- Idempotent — safe to re-run.

### Page renaming (`rename_pages.py`)
- Renames page directories to `displayName` from `page.json`.
- Updates `page.json` `name` field AND `pages.json` (`pageOrder`, `activePageName`).
- Outputs JSON mapping to stdout (for bookmark ref updates); human output to stderr.
- Does NOT touch bookmark files — that's `rename_bookmark_refs.py`.

### Bookmark reference updating (`rename_bookmark_refs.py`)
- Takes report dir + JSON mapping file (from `rename_pages.py` stdout).
- Updates `explorationState.activeSection` and `explorationState.sections` keys in each `*.bookmark.json`.

---

## CLI conventions

All scripts follow these conventions:
- Positional args for primary input (model dir, report dir).
- `-h`/`--help` consistently supported.
- `-n`/`--dry-run` for rename tools (no-op mode).
- Output is flat text suitable for shell pipes (`|`, `>`, `comm`, `sort`, `diff`).
- Errors go to stdout (not stderr) currently — be aware for CI integration.
