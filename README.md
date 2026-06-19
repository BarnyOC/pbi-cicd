# PBIP CI/CD Tools

A set of Python stdlib-only tools for validating and maintaining Power BI Project (PBIP) repositories.

> **WIP — Subject to change.** These tools are early-stage and may evolve significantly as patterns emerge. Assumptions may be wrong. Expect breakage.

---

## Key Assumptions

- **Repository structure**: All PBIP items live under a single root directory (e.g. `src/`) with `*.SemanticModel/` and `*.Report/` folders.
- **Reports use `byPath`** to reference models (not `byConnection`). The `definition.pbir` for each report contains a relative `byPath` reference to a `.SemanticModel` directory.
- **dbt-first warehouses**: The semantic model is expected to mirror a dbt-managed warehouse schema. Validation of model fields against the warehouse is intended for dbt CI pipelines (or equivalent).
- **Minimal Power Query**: The tools assume transformations happen upstream (dbt), not in Power Query. No Power Query expression parsing is included.
- **Output format**: All field-listing tools emit `Table.Col` format (flat, pipe-friendly) for use with `comm(1)` for cross-referencing and diffing.

---

## Scripts

### Field validation

Designed to be composed via shell pipes. Common pipeline:

```bash
python model_fields.py src/Model01.SemanticModel | sort > model.txt
python report_fields.py src/Report01.Report | sort > report.txt
comm -23 report.txt model.txt   # orphaned report references
```

| Script | Purpose |
|--------|---------|
| `model_fields.py` | Lists all columns + measures from a `.SemanticModel` by parsing TMDL files. Supports `--measures` (list only measures) and `--datatypes` (include column data types). |
| `report_fields.py` | Lists all field references used across report visuals by parsing `visual.json` files. Supports `--measures` (list only measure references). |
| `measure_fields.py` | Resolves transitive field dependencies of one or more measures by parsing DAX expressions in TMDL. Takes measure name(s) as positional args (`Table.Measure` or bare name). Supports `--datatypes`. |
| `model_downstream_deps.py` | Discovers which reports reference a given model via `byPath`. Subcommand: `report-deps <model_path>`. Use `--root` to change the scan root (default: `src`). |

### Dev UX — directory renaming

PBIP auto-generates GUID-named directories for visuals and pages. These scripts rename them to human-readable names.

| Script | Purpose |
|--------|---------|
| `rename_visuals.py` | Renames visual directories to a derived name (custom title → fallback to `visualType~field1+field2~...`). Collision-safe with `_1`, `_2` suffixes. Idempotent (skips non-GUID and already-renamed dirs). |
| `rename_pages.py` | Renames page directories to their `displayName` from `page.json`. Updates `page.json` `name` field and `pages.json` references. Outputs JSON mapping to stdout (for use with `rename_bookmark_refs.py`); human output to stderr. |
| `rename_bookmark_refs.py` | After `rename_pages.py`, updates bookmark `explorationState.activeSection` and `sections` keys to match renamed page directories. Takes the JSON mapping from `rename_pages.py` as input. |

### Typical rename workflow

```bash
# 1. Rename pages, capture mapping
python rename_pages.py src/Report01.Report > page_map.json

# 2. Update bookmark references
python rename_bookmark_refs.py src/Report01.Report page_map.json

# 3. Rename visuals
python rename_visuals.py src/Report01.Report
```

---

## Dependencies

**None.** These scripts use Python stdlib only (tested on 3.12). No `pip install` required.

---

## CI Integration

The tools are designed to be composable via `comm(1)` in CI pipelines:

```yaml
- name: Check report references exist in model
  run: |
    comm -23 \
      <(python report_fields.py src/Report01.Report | sort) \
      <(python model_fields.py src/Model01.SemanticModel | sort) \
      | tee orphaned.txt
    test ! -s orphaned.txt
```

You might also compare `model_fields.py` output against your dbt manifest (`dbt docs generate` produces `catalog.json`) to validate warehouse coverage.
