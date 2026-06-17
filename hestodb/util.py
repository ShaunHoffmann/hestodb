from pathlib import Path
import pandas as pd
from datetime import datetime
from hestodb.report import (
    extract_report_date,
    format_report_date,
    Report,
)

CUTOFF_DATE = datetime(2026, 4, 1)


def _filename_date_to_dt(raw: int):
    """Convert YYYYMM integer to a datetime (YYYY-MM-15)."""
    if not raw:
        return None
    try:
        s = str(raw)
        year = int(s[:4])
        month = int(s[4:6])
        return datetime(year, month, 15)
    except (ValueError, TypeError):
        return None


def _select_final_date(report, filepath):
    """
    Returns a tuple: (chosen_date, keep_report_boolean)
    chosen_date = datetime for ranking within folder.
    keep_report_boolean = True if report passes cutoff.
    """
    # Summary date
    summary_raw = report.summary.get("date") if report.summary else None
    summary_dt = None

    if summary_raw:
        try:
            formatted = format_report_date(summary_raw)
            summary_dt = datetime.strptime(formatted, "%Y-%m-%d")
        except (ValueError, TypeError):
            summary_dt = None

    # Filename fallback date
    filename_raw = extract_report_date(filepath.name)
    filename_dt = _filename_date_to_dt(filename_raw)

    # --- Filtering ---
    passes_filter = False

    # Summary date qualifies
    if summary_dt and summary_dt >= CUTOFF_DATE:
        passes_filter = True

    # Filename fallback qualifies (your requirement)
    elif filename_dt and filename_dt >= CUTOFF_DATE:
        passes_filter = True

    if not passes_filter:
        return None, False

    # --- Pick chosen date ---
    chosen = summary_dt if summary_dt else filename_dt
    return chosen, True


def find_latest_report_pptx(root_dir: Path | str) -> pd.DataFrame:
    """
    Find all .pptx files matching the structure:
        <root>/<year>/<project>/Triannual*/<file>.pptx
    Skips temporary Office lock files (~ prefix).
    When multiple files exist in the same Triannual folder, only the most
    recently modified one is kept (based on report_date from summary slide).

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

    # Group by parent folder, keep the newest file in each (based on summary date)
    folders = {}
    folder_dates = {}

    for p in all_files:
        try:
            report = Report(p)
        except Exception:
            continue

        chosen_date, keep = _select_final_date(report, p)
        if not keep:
            continue

        folder = p.parent

        if folder not in folders or chosen_date > folder_dates[folder]:
            folders[folder] = report
            folder_dates[folder] = chosen_date

    # NOTE (perf): each kept file is fully parsed into a Report above, but only
    # its extracted fields are written into the DataFrame below -- the Report
    # objects themselves are discarded. The notebook then re-parses the selected
    # files (`reports = [Report(p) for p in files["file_path"]]`), so those files
    # are parsed twice. To remove the double parse, this function could return
    # the already-built Report objects (e.g. via an optional `_report` column)
    # for the caller to reuse instead of re-parsing.
    rows = []
    for report in sorted(folders.values(), key=lambda r: r.filename.lower()):
        metadata = parse_file_path(report.file_path)
        modified_ts = report.file_path.stat().st_mtime
        report_date = folder_dates[report.file_path.parent]
        rows.append(
            {
                "filename": report.filename,
                "file_path": report.file_path,
                "project_id": report.project_id or metadata["project_id"],
                "report_date": report_date or metadata["report_date"],
                "year": metadata["year"],
                "principal_investigator": report.principal_investigator
                or metadata["principal_investigator"],
                "affiliation": report.affiliation,
                "research_regime": report.research_regime,
                "modified": datetime.fromtimestamp(modified_ts),
                "folder": report.file_path.parent,
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
    if len(parts) < 4:
        raise ValueError(f"Unexpected file path structure: {file_path}")
    return {
        "year": int(parts[-5][0:2]) + 2000,
        "project_id": project_id,
        "report_date": extract_report_date(file_path.name),
        "principal_investigator": project_pi,
        "filename": parts[-1],
    }
