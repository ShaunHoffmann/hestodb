from pathlib import Path
import pandas as pd
from datetime import datetime
from hestodb.report import extract_report_date, format_report_date


def find_latest_report_pptx(root_dir: Path | str) -> pd.DataFrame:
    """
    Find all .pptx files matching the structure:
        <root>/<year>/<project>/Triannual*/<file>.pptx
    Skips temporary Office lock files (~ prefix).
    When multiple files exist in the same Triannual folder, only the most
    recently modified one is kept.

    Returns a DataFrame indexed by filename with columns:
        - file_path: Path to the selected .pptx file
        - project_id: parsed project identifier from folder structure
        - principal_investigator: parsed PI name from folder structure
        - modified_ts: last-modified timestamp (Unix seconds)
        - modified: last-modified datetime (local time)
        - folder: parent folder used for grouping
    """
    if isinstance(root_dir, str):
        root_dir = Path(root_dir)

    all_files = [
        p
        for p in root_dir.glob("*/*/Reports/HESTO/*.pptx")
        if not p.name.startswith("~$")
    ]

    # Group by parent folder, keep the newest file in each
    folders: dict = {}
    report_dates: dict = {}
    for p in all_files:
        report_date = extract_report_date(p.name)
        if report_date is None:
            continue
        if report_date >= 202604:
            key = p.parent
            if key not in folders or report_date > report_dates[key]:
                folders[key] = p
                report_dates[key] = report_date

    rows = []
    for p in sorted(folders.values(), key=lambda this_p: this_p.name.lower()):
        metadata = parse_file_path(p)
        modified_ts = p.stat().st_mtime
        rows.append(
            {
                "filename": p.name,
                "file_path": p,
                "project_id": metadata["project_id"],
                "report_date": format_report_date(str(metadata["report_date"])) if metadata["report_date"] else "",
                "year": metadata["year"],
                "principal_investigator": metadata["principal_investigator"],
                "modified": datetime.fromtimestamp(modified_ts),
                "folder": p.parent,
                "is_active": "Yes" if metadata["report_date"] and int(metadata["report_date"]) >= 202511 else "No"
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
