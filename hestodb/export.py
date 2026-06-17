"""Shape parsed :class:`~hestodb.report.Report` objects into linked CSV exports.

Detail tables (publications, patents, student metrics, project status) are
written *long* — one row per item, linked back to the master by ``project_id``.
The master table rolls all six slide parsers up to one row per active report,
with a two-row column header (top = source group, bottom = field name).

In every function ``reports[i]`` must align positionally with row ``i`` of the
``files`` DataFrame produced by :func:`hestodb.util.find_latest_report_pptx`.
"""

import pandas as pd
from hestodb.report import get_accom_value

# Clean column names for each sub-table, in slide column order. Headers are
# renamed BY POSITION, so verbose / inconsistent PPTX headers don't matter.
PUBLICATION_COLS = [
    "publication_type",
    "title",
    "publication_date",
    "publisher_name",
    "url",
]
PATENT_COLS = [
    "patent_type",
    "patent_name",
    "patent_number",
    "patent_date",
    "resource_link",
]
STUDENT_COLS = ["student_name", "major", "affiliation", "level"]
STATUS_COLS = ["category", "prior", "current", "rationale"]

DETAIL_SEP = " -- "  # separates items when rolled up into the master table

STATUS_CATEGORIES = [
    "overall",
    "cost",
    "schedule",
    "technical",
    "staffing",
    "facilities",
]
STATUS_FIELDS = ("prior", "current", "rationale")
# pivoted project-status columns, e.g. overall_prior, overall_current, ...
STATUS_PIVOT_COLS = [f"{c}_{f}" for c in STATUS_CATEGORIES for f in STATUS_FIELDS]

# Accommodation fields flattened from a report's category/sub_category/value
# table into named master columns: field name -> (category, sub_category).
ACCOMMODATION_FIELDS = {
    "length": ("payload size", "length"),
    "width": ("payload size", "width"),
    "height": ("payload size", "height"),
    "total_volume": ("payload volume", ""),
    "average_power": ("power requirements", "average"),
    "peak_power": ("power requirements", "peak"),
    "total_mass": ("mass", ""),
    "attitude_knowledge": ("pointing requirements", "arcsecs"),
    "attitude_control": ("pointing requirements", "arcminutes"),
    "average_data_rate": ("data rate", "average"),
    "peak_data_rate": ("data rate", "peak"),
    "power_interface_port": ("power interface port", ""),
    "communication_interface_protocol": ("communication interface protocol", ""),
    "data_connector_type": ("data communication port", ""),
    "thermal_isolation": ("requires thermal isolation", ""),
    "circuit_protection": ("special power considerations", ""),
}

# Map every master column to its top-level (slide / source) group. Columns not
# listed here fall under "metadata" (file_path, report_date, year, ...).
COLUMN_GROUPS = {
    "summary": [
        "project_id",
        "principal_investigator",
        "affiliation",
        "research_regime",
    ],
    "accommodations": list(ACCOMMODATION_FIELDS),
    "publications": ["n_publications", "publications_detail"],
    "patents": ["n_patents", "patents_detail"],
    "project_status": STATUS_PIVOT_COLS,
    "student_metrics": ["n_students", "students_detail"],
}

# Left-to-right group order in the master table.
GROUP_ORDER = [
    "metadata",
    "summary",
    "accommodations",
    "publications",
    "patents",
    "project_status",
    "student_metrics",
]


def group_for(col: str) -> str:
    """Return the top-level header group for a master column."""
    for group, cols in COLUMN_GROUPS.items():
        if col in cols:
            return group
    return "metadata"


def accommodation_fields(report) -> dict:
    """Flatten a report's accommodation table into named master columns."""
    table = report.accomodation_table
    return {
        name: get_accom_value(table, category, sub)
        for name, (category, sub) in ACCOMMODATION_FIELDS.items()
    }


def _detail_string(df, n_cols: int) -> str:
    """Join a sub-table's rows into a single ``DETAIL_SEP``-delimited string."""
    if df is None or df.empty:
        return ""
    parts = []
    for _, r in df.iloc[:, :n_cols].iterrows():
        cells = [str(x).strip() for x in r.tolist()]
        if any(cells):
            parts.append(" | ".join(cells))
    return DETAIL_SEP.join(parts)


def _normalize_columns(df, clean_cols):
    """Return *df* with exactly ``len(clean_cols)`` columns, renamed by position.

    Extra columns are truncated; short tables are padded with blank columns so
    a malformed slide never crashes the export.
    """
    n = len(clean_cols)
    sub = df.copy()
    if sub.shape[1] >= n:
        sub = sub.iloc[:, :n]
    else:
        for j in range(sub.shape[1], n):
            sub[f"_pad{j}"] = ""
    sub.columns = list(clean_cols)
    return sub


def build_detail_csv(reports, files, attr, clean_cols, out_path):
    """Stack one sub-table across all ACTIVE reports into a long CSV.

    ``project_id`` (from ``files``, so the join key matches the master) is
    prepended as the link key; the sub-table's columns are normalized by
    position; rows that are entirely blank (ignoring ``project_id``) are
    dropped. Pass ``out_path=None`` to skip writing. Returns the DataFrame.
    """
    files = files.reset_index(drop=True)
    clean_cols = list(clean_cols)
    frames = []
    for i, rep in enumerate(reports):
        if files.loc[i, "is_active"] != "Yes":  # active reports only
            continue
        df = getattr(rep, attr)
        if df is None or df.empty:  # skip missing sub-tables
            continue
        sub = _normalize_columns(df, clean_cols)
        sub.insert(0, "project_id", files.loc[i, "project_id"])
        frames.append(sub)

    if frames:
        out = pd.concat(frames, ignore_index=True)
    else:
        out = pd.DataFrame(columns=["project_id"] + clean_cols)

    # drop rows that are blank across every non-key column
    nonblank = (
        out[clean_cols].astype(str).apply(lambda c: c.str.strip()).ne("").any(axis=1)
    )
    out = out[nonblank].reset_index(drop=True)

    if out_path is not None:
        out.to_csv(out_path, index=False)
    return out


def build_master_table(reports, files, out_path="master_table.csv"):
    """Roll all six slide parsers up to one row per ACTIVE report.

    ``project_status`` is pivoted to fixed ``{category}_prior/current/rationale``
    columns; the variable-length tables contribute a count (``n_*``) and a
    ``DETAIL_SEP``-joined detail column. Columns are grouped contiguously per
    :data:`GROUP_ORDER`. When *out_path* is given, a CSV with a two-row header
    (top = source group, bottom = field name) is written. Returns the master
    DataFrame (single-level columns; grouping is applied only in the file).
    """
    files = files.reset_index(drop=True)

    agg_rows = []
    for i, rep in enumerate(reports):
        row = {"_pos": i}

        pub, pat, stu = (
            rep.publication_table,
            rep.patents_table,
            rep.student_metrics_table,
        )
        row["n_publications"] = 0 if pub is None or pub.empty else len(pub)
        row["n_patents"] = 0 if pat is None or pat.empty else len(pat)
        row["n_students"] = 0 if stu is None or stu.empty else len(stu)
        row["publications_detail"] = _detail_string(pub, len(PUBLICATION_COLS))
        row["patents_detail"] = _detail_string(pat, len(PATENT_COLS))
        row["students_detail"] = _detail_string(stu, len(STUDENT_COLS))

        row.update(accommodation_fields(rep))  # accommodations slide -> columns

        st = rep.project_status
        if st is not None and not st.empty:
            for _, r in st.iterrows():
                cat = r["category"]
                row[f"{cat}_prior"] = r["prior"]
                row[f"{cat}_current"] = r["current"]
                row[f"{cat}_rationale"] = r["rationale"]
        agg_rows.append(row)

    agg = pd.DataFrame(agg_rows).set_index("_pos")
    for c in STATUS_PIVOT_COLS:  # ensure a stable set of status columns
        if c not in agg.columns:
            agg[c] = ""

    # files index (0..n) aligns with reports position == agg _pos
    master = files.join(agg)
    master = master[master["is_active"] == "Yes"].reset_index(drop=True)
    master = master.drop(columns=["index"], errors="ignore")  # reset_index artifact

    # order columns so each top-level group is contiguous
    metadata_cols = [c for c in master.columns if group_for(c) == "metadata"]
    ordered = []
    for g in GROUP_ORDER:
        if g == "metadata":
            ordered += metadata_cols  # keep original order
        else:
            ordered += [c for c in COLUMN_GROUPS[g] if c in master.columns]
    master = master[ordered]

    if out_path is not None:
        groups = [group_for(c) for c in master.columns]
        with open(out_path, "w", newline="", encoding="utf-8") as fh:
            fh.write(",".join(groups) + "\n")
            fh.write(",".join(map(str, master.columns)) + "\n")
            fh.write(master.to_csv(index=False, header=False))

    return master
