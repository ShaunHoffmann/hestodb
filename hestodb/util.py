from pathlib import Path
import pandas as pd
from datetime import datetime
from hestodb.report import extract_report_date, format_report_date, Report


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
    folders: dict = {}
    report_dates: dict = {}
    
    for p in all_files:
        try:
            report = Report(p)
            
            # Extract and format report date from summary slide
            raw_date = report.summary.get("date") if report.summary else None
            if not raw_date:
                continue
            
            formatted_date = format_report_date(raw_date)
            
            # Skip if date formatting failed
            if not formatted_date:
                continue
            
            key = p.parent
            # Compare dates as strings (YYYY-MM-DD format sorts correctly)
            if key not in folders or formatted_date > report_dates[key]:
                folders[key] = report
                report_dates[key] = formatted_date
        except Exception as e:
            # Skip files that fail to load
            continue

    rows = []
    for report in sorted(folders.values(), key=lambda r: r.filename.lower()):
        metadata = parse_file_path(report.file_path)
        modified_ts = report.file_path.stat().st_mtime

        report_date = report_dates[report.file_path.parent]
        
        rows.append(
            {
                "filename": report.filename,
                "file_path": report.file_path,
                "project_id": report.project_id or metadata["project_id"],
                "report_date": report_date or metadata["report_date"],
                "year": metadata["year"],
                "principal_investigator": report.principal_investigator or metadata["principal_investigator"],
                "affiliation": report.affiliation,
                "research_regime": report.research_regime,
                "modified": datetime.fromtimestamp(modified_ts),
                "folder": report.file_path.parent,
                "is_active": "Yes" if report_date >= "2025-12-01" else "No",
            }
        )

    if not rows:
        empty_df = pd.DataFrame(
            columns=[
                "filename",
                "file_path",
                "project_id",
                "report_date",
                "principal_investigator",
                "year",
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
    project_id, project_pi = project_str.split(maxsplit=1)
    #project_id = project_str[0:15]
    #project_pi = project_str[16:].lstrip()
    if len(parts) < 4:
        raise ValueError(f"Unexpected file path structure: {file_path}")
    return {
        "year": int(parts[-5][0:2]) + 2000,
        "project_id": project_id,
        "report_date": extract_report_date(file_path.name),
        "principal_investigator": project_pi,
        "filename": parts[-1],
    }
