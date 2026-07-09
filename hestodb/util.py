from pathlib import Path
import json
import pandas as pd
from datetime import datetime
from hestodb.report import extract_report_date, format_report_date, Report

CUTOFF_DATE = datetime(2025, 12, 31)


def _load_cache(cache_path) -> dict:
    """Load the summary-peek cache. Returns {} when disabled, missing, or corrupt."""
    if cache_path is None:
        return {}
    try:
        with open(cache_path, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache_path, cache: dict) -> None:
    """Atomically write the summary-peek cache, unless caching is disabled."""
    if cache_path is None:
        return
    cache_path = Path(cache_path)
    tmp = cache_path.with_name(cache_path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cache, fh)
    tmp.replace(cache_path)


def _select_final_date(summary, filepath):
    """
    Returns a tuple: (chosen_date, rank, keep_report_boolean)
    chosen_date = datetime written to the report_date column (plain datetime).
    rank        = (summary_dt, filename_dt, modified_dt) tuple used ONLY to
                  pick the winner within a folder. Missing dates use
                  datetime.min so they sort lowest.
    keep_report_boolean = True if report passes cutoff.

    Precedence for "latest" within a folder:
        1. summary slide date  (latest wins)
        2. tie -> filename YYYYMM date  (latest wins)
        3. tie -> file modified time    (latest wins)
    """
    # Summary date
    summary_raw = summary.get("date") if summary else None
    summary_dt = None
    if summary_raw:
        try:
            formatted = format_report_date(summary_raw)
            summary_dt = datetime.strptime(formatted, "%Y-%m-%d")
        except (ValueError, TypeError):
            summary_dt = None

    # Filename fallback date
    filename_raw = extract_report_date(filepath.name)
    filename_dt = None
    if filename_raw:
        try:
            filename_dt = datetime.strptime(f"{filename_raw}15", "%Y%m%d")
        except (ValueError, TypeError):
            filename_dt = None

    # --- Filtering ---
    passes_filter = False

    # Summary date qualifies
    if summary_dt and summary_dt >= CUTOFF_DATE:
        passes_filter = True

    # Filename fallback qualifies (your requirement)
    elif filename_dt and filename_dt >= CUTOFF_DATE:
        passes_filter = True

    if not passes_filter:
        return None, None, False

    # --- Build ranking tuple (final tiebreak) ---
    # modified_dt is always present, so the tuple comparison is deterministic
    # even when both date signals tie.
    modified_dt = datetime.fromtimestamp(filepath.stat().st_mtime)
    rank = (
        summary_dt or datetime.min,
        filename_dt or datetime.min,
        modified_dt,
    )

    # --- Pick chosen date (stays a plain datetime for the report_date column) ---
    chosen = summary_dt if summary_dt else filename_dt
    return chosen, rank, True


def find_latest_report_pptx(
    root_dir: Path | str, cache_path: Path | str | None = None
) -> pd.DataFrame:
    """
    Find all .pptx files matching the structure:
        <root>/<year>/<project>/Triannual*/<file>.pptx
    Skips temporary Office lock files (~ prefix).
    When multiple files exist in the same Triannual folder, only the most
    recently modified one is kept (based on report_date from summary slide).

    When *cache_path* is given, each file's summary-slide peek is cached keyed
    by mtime; unchanged files are not re-opened on subsequent runs. Pass None
    (default) to disable caching.

    Returns a DataFrame indexed by filename with columns:
        - file_path: Path to the selected .pptx file
        - project_id: project identifier from Report summary
        - principal_investigator: PI name from Report summary
        - report_date: formatted date from summary slide (YYYY-MM-DD)
        - year: extracted year from folder structure
        - modified: last-modified datetime (local time)
        - folder: parent folder used for grouping
        - is_active: "Yes" if report_date >= 2025-12-01, "No" otherwise
    """
    if isinstance(root_dir, str):
        root_dir = Path(root_dir)

    all_files = [
        p
        for p in root_dir.glob("*/*/Reports/HESTO/*.pptx")
        if not p.name.startswith("~$")
    ]

    # Group by parent folder, keep the newest file in each. "Newest" is decided
    # by the rank tuple (summary date -> filename date -> modified time), while
    # folder_dates stores the plain datetime that goes in the report_date column.
    folders = {}
    folder_dates = {}
    folder_ranks = {}

    cache = _load_cache(cache_path)

    for p in all_files:
        key = str(p)
        mtime_ns = p.stat().st_mtime_ns
        entry = cache.get(key)
        if entry is not None and entry["mtime_ns"] == mtime_ns:
            summary = entry["summary"]  # cache hit: file not opened
        else:
            try:
                summary = Report.peek_summary(p)  # cache miss: open + peek
            except Exception:
                continue
            cache[key] = {"mtime_ns": mtime_ns, "summary": summary}

        chosen_date, rank, keep = _select_final_date(summary, p)
        if not keep:
            continue

        folder = p.parent

        if folder not in folders or rank > folder_ranks[folder]:
            folders[folder] = (p, summary)
            folder_dates[folder] = chosen_date
            folder_ranks[folder] = rank

    _save_cache(cache_path, cache)

    rows = []
    for file_path, summary in sorted(
        folders.values(), key=lambda fs: fs[0].name.lower()
    ):
        metadata = parse_file_path(file_path)
        modified_ts = file_path.stat().st_mtime
        report_date = folder_dates[file_path.parent]

        # Summary-slide fields, mirroring Report._process_summary -- derived from
        # the peeked summary dict instead of a full Report. When the summary slide
        # is missing/empty these stay None and path metadata fills in below.
        if summary:
            project_id = summary.get("proposal id", None)
            principal_investigator = (
                summary.get("principal investigator", "") or ""
            ).strip()
            affiliation = (summary.get("affiliation", "") or "").strip()
            research_regime = (summary.get("research regime", "") or "").strip()
        else:
            project_id = principal_investigator = affiliation = research_regime = None

        rows.append(
            {
                "filename": file_path.name,
                "file_path": file_path,
                "project_id": project_id or metadata["project_id"],
                "report_date": report_date or metadata["report_date"],
                "year": metadata["year"],
                "principal_investigator": principal_investigator
                or metadata["principal_investigator"],
                "first_name": metadata["first_name"],
                "last_name": metadata["last_name"],
                "affiliation": affiliation,
                "research_regime": research_regime,
                "modified": datetime.fromtimestamp(modified_ts),
                "folder": file_path.parent,
                "is_active": "Yes" if report_date >= CUTOFF_DATE else "No",
            }
        )

    if not rows:
        empty_df = pd.DataFrame(
            columns=[
                "filename",
                "file_path",
                "project_id",
                "report_date",
                "year",
                "principal_investigator",
                "first_name",
                "last_name",
                "affiliation",
                "research_regime",
                "modified",
                "folder",
                "is_active",
            ]
        )
        return empty_df.set_index("filename")

    return pd.DataFrame(rows).set_index("filename").sort_values("year", ascending=False)


def parse_file_path(file_path: Path | str) -> dict:
    """Parse a report path to extract metadata like year, project, and filename."""
    if isinstance(file_path, str):
        file_path = Path(file_path)
    parts = file_path.parts
    project_str = parts[-4]
    parts_split = project_str.split(maxsplit=1)
    project_id = parts_split[0]
    project_pi = parts_split[1] if len(parts_split) > 1 else ""
    name_parts = project_pi.split()
    if not name_parts:
        first_name, last_name = "", ""
    elif len(name_parts) == 1:
        # A lone token is a surname, not a given name.
        first_name, last_name = "", name_parts[0]
    else:
        # last token, so a middle name/initial isn't mistaken for the surname.
        first_name, last_name = name_parts[0], name_parts[-1]
    if len(parts) < 4:
        raise ValueError(f"Unexpected file path structure: {file_path}")
    return {
        "year": int(parts[-5][0:2]) + 2000,
        "project_id": project_id,
        "report_date": extract_report_date(file_path.name),
        "principal_investigator": project_pi,
        "first_name": first_name,
        "last_name": last_name,
        "filename": parts[-1],
    }
