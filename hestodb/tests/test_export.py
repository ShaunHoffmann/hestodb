import pandas as pd

from hestodb import _test_report_pptx
from hestodb.report import Report
from hestodb.export import (
    build_detail_csv,
    build_master_table,
    accommodation_fields,
    group_for,
    _detail_string,
    _normalize_columns,
    ACCOMMODATION_FIELDS,
    COLUMN_GROUPS,
    DETAIL_SEP,
    GROUP_ORDER,
    PUBLICATION_COLS,
    STUDENT_COLS,
    STATUS_COLS,
    STATUS_PIVOT_COLS,
)


class FakeReport:
    """Minimal stand-in exposing the attributes ``build_*`` reads off a Report.

    ``accomodation_table`` keeps the real code's misspelling on purpose so the
    fake matches the attribute name :func:`accommodation_fields` actually reads.
    ``performance_period_start`` / ``performance_period_end`` are included
    because :func:`build_master_table` reads them unconditionally.
    """

    def __init__(
        self,
        publication_table=None,
        patents_table=None,
        student_metrics_table=None,
        project_status=None,
        accomodation_table=None,
        trl_status_table=None,
        performance_period="",
        performance_period_start=None,
        performance_period_end=None,
        email=None,
    ):
        self.publication_table = publication_table
        self.patents_table = patents_table
        self.student_metrics_table = student_metrics_table
        self.project_status = project_status
        self.accomodation_table = accomodation_table
        self.trl_status_table = trl_status_table
        self.performance_period = performance_period
        self.performance_period_start = performance_period_start
        self.performance_period_end = performance_period_end
        self.email = email


def _verbose_publication_df(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "Type choose one of below",
            "Title",
            "Publication/Presentation Date",
            "Publisher/Conference Name",
            "URL",
        ],
    )


def _accom_df(rows):
    return pd.DataFrame(rows, columns=["category", "sub_category", "value"])


def _make_files():
    return pd.DataFrame(
        [
            {
                "file_path": "/a",
                "report_date": "2026-04-01",
                "year": 2024,
                "project_id": "P1",
                "principal_investigator": "PI1",
                "is_active": "Yes",
            },
            {
                "file_path": "/b",
                "report_date": "2026-04-02",
                "year": 2024,
                "project_id": "P2",
                "principal_investigator": "PI2",
                "is_active": "No",
            },
        ]
    )


# --------------------------------------------------------------------------- #
# group_for
#
# Docstring: "Return the top-level header group for a master column." Anything
# not listed in COLUMN_GROUPS falls under "metadata" (export.py:70-71).
# --------------------------------------------------------------------------- #
def test_group_for_maps_columns_to_their_source_group():
    assert group_for("project_id") == "summary"
    assert group_for("email") == "summary"
    assert group_for("trl_input") == "trl_status"
    assert group_for("trl_current") == "trl_status"
    assert group_for("trl_planned_exit") == "trl_status"
    assert group_for("length") == "accommodations"
    assert group_for("n_publications") == "publications"
    assert group_for("publications_detail") == "publications"
    assert group_for("n_patents") == "patents"
    assert group_for("patents_detail") == "patents"
    assert group_for("overall_prior") == "project_status"
    # performance_period is declared in the project_status group
    assert group_for("performance_period") == "project_status"
    assert group_for("n_students") == "student_metrics"
    assert group_for("students_detail") == "student_metrics"


def test_group_for_is_consistent_with_column_groups():
    # Every column declared in COLUMN_GROUPS must map back to its own group.
    for group, cols in COLUMN_GROUPS.items():
        for col in cols:
            assert group_for(col) == group


def test_group_for_unknown_column_falls_back_to_metadata():
    assert group_for("file_path") == "metadata"
    assert group_for("report_date") == "metadata"
    assert group_for("year") == "metadata"
    assert group_for("is_active") == "metadata"
    assert group_for("") == "metadata"
    assert group_for("totally_unknown") == "metadata"


# --------------------------------------------------------------------------- #
# accommodation_fields
#
# Docstring: "Flatten a report's accommodation table into named master columns."
# Values come from report.get_accom_value, which returns None when the row is
# absent and None when the table is None/empty (report.py:789-798).
# --------------------------------------------------------------------------- #
def test_accommodation_fields_returns_full_field_set():
    accom = _accom_df(
        [
            {"category": "payload size", "sub_category": "length", "value": 10.0},
            {"category": "mass", "sub_category": "", "value": 5.4},
        ]
    )
    fields = accommodation_fields(FakeReport(accomodation_table=accom))
    # keys are always the full declared field set, regardless of table contents
    assert set(fields) == set(ACCOMMODATION_FIELDS)


def test_accommodation_fields_pulls_present_values_unchanged():
    accom = _accom_df(
        [
            {"category": "payload size", "sub_category": "length", "value": 10.0},
            {"category": "mass", "sub_category": "", "value": 5.4},
            {"category": "power requirements", "sub_category": "peak", "value": 42},
        ]
    )
    fields = accommodation_fields(FakeReport(accomodation_table=accom))
    assert fields["length"] == 10.0
    assert fields["total_mass"] == 5.4
    assert fields["peak_power"] == 42


def test_accommodation_fields_absent_row_is_none():
    accom = _accom_df(
        [{"category": "payload size", "sub_category": "length", "value": 10.0}]
    )
    fields = accommodation_fields(FakeReport(accomodation_table=accom))
    # fields whose (category, sub_category) has no row -> None
    assert fields["width"] is None
    assert fields["total_mass"] is None


def test_accommodation_fields_missing_table_all_none():
    fields = accommodation_fields(FakeReport(accomodation_table=None))
    assert set(fields) == set(ACCOMMODATION_FIELDS)
    assert all(v is None for v in fields.values())


def test_accommodation_fields_empty_table_all_none():
    fields = accommodation_fields(FakeReport(accomodation_table=_accom_df([])))
    assert set(fields) == set(ACCOMMODATION_FIELDS)
    assert all(v is None for v in fields.values())


# --------------------------------------------------------------------------- #
# _detail_string
#
# Docstring: "Join a sub-table's rows into a single DETAIL_SEP-delimited
# string." Cells within a row are joined with " | "; None/empty df -> "".
#
# NOTE: null (NaN/None) cell rendering is intentionally NOT tested. str(NaN)
# yields the literal token "nan", which is undocumented and likely unintended;
# asserting either "nan" or "" would codify a guess. Left for a behavior
# decision on _detail_string itself.
# --------------------------------------------------------------------------- #
def test_detail_string_none_or_empty_returns_blank():
    assert _detail_string(None, 5) == ""
    assert _detail_string(pd.DataFrame(), 5) == ""


def test_detail_string_joins_cells_within_a_row_with_pipe():
    df = pd.DataFrame([["a", "b", "c"]], columns=list("xyz"))
    assert _detail_string(df, 3) == "a | b | c"


def test_detail_string_joins_rows_with_detail_sep():
    df = pd.DataFrame([["a", "b"], ["c", "d"]], columns=list("xy"))
    assert _detail_string(df, 2) == "a | b" + DETAIL_SEP + "c | d"


def test_detail_string_truncates_to_n_cols():
    df = pd.DataFrame([["a", "b", "c", "d", "e"]], columns=list("abcde"))
    # only the first two columns participate
    assert _detail_string(df, 2) == "a | b"


def test_detail_string_drops_all_blank_rows_keeps_partial_rows():
    df = pd.DataFrame([["", "", ""], ["kept", "", ""]], columns=list("xyz"))
    # the all-blank row contributes nothing; the partial row keeps its blanks
    assert _detail_string(df, 3) == "kept |  | "


def test_detail_string_strips_whitespace_from_cells():
    df = pd.DataFrame([["  x  ", "\ty\n"]], columns=list("ab"))
    assert _detail_string(df, 2) == "x | y"


# --------------------------------------------------------------------------- #
# _normalize_columns
#
# Docstring: "Return df with exactly len(clean_cols) columns, renamed by
# position. Extra columns are truncated; short tables are padded with blank
# columns" (export.py:123-128).
# --------------------------------------------------------------------------- #
def test_normalize_columns_exact_width_renames_by_position():
    df = pd.DataFrame([["A", "B", "C", "D"]], columns=["w", "x", "y", "z"])
    out = _normalize_columns(df, STUDENT_COLS)
    assert list(out.columns) == STUDENT_COLS
    # rename is positional, not by name: source col 0 -> first clean col
    assert out.iloc[0]["student_name"] == "A"
    assert out.iloc[0]["level"] == "D"


def test_normalize_columns_truncates_extra_columns():
    df = pd.DataFrame([["a", "b", "c", "d", "e", "EXTRA"]], columns=list("abcdef"))
    out = _normalize_columns(df, PUBLICATION_COLS)
    assert list(out.columns) == PUBLICATION_COLS
    assert "EXTRA" not in out.iloc[0].tolist()
    assert out.iloc[0]["url"] == "e"  # 5th column retained


def test_normalize_columns_pads_short_tables_with_blanks():
    df = pd.DataFrame([["Jane", "Physics", "UA"]], columns=["n", "m", "a"])
    out = _normalize_columns(df, STUDENT_COLS)
    assert list(out.columns) == STUDENT_COLS
    assert out.iloc[0]["level"] == ""  # padded column


def test_normalize_columns_does_not_mutate_input():
    df = pd.DataFrame([["a", "b", "c", "d"]], columns=["w", "x", "y", "z"])
    original_cols = list(df.columns)
    _normalize_columns(df, STUDENT_COLS)
    # df.copy() protects the caller's frame
    assert list(df.columns) == original_cols


# --------------------------------------------------------------------------- #
# build_detail_csv
#
# Docstring at export.py:141-147.
# --------------------------------------------------------------------------- #
def test_build_detail_csv_renames_by_position_and_prepends_project_id():
    pub = _verbose_publication_df(
        [["Web article", "T1", "2026", "Publisher", "http://x"]]
    )
    reports = [FakeReport(publication_table=pub)]
    files = pd.DataFrame([{"project_id": "P1", "is_active": "Yes"}])

    out = build_detail_csv(reports, files, "publication_table", PUBLICATION_COLS, None)

    assert list(out.columns) == ["project_id"] + PUBLICATION_COLS
    assert out.iloc[0].tolist() == [
        "P1",
        "Web article",
        "T1",
        "2026",
        "Publisher",
        "http://x",
    ]


def test_build_detail_csv_skips_inactive_and_missing_subtables():
    pub = _verbose_publication_df([["Web article", "T", "d", "p", "u"]])
    reports = [
        FakeReport(publication_table=pub),  # active + data -> kept
        FakeReport(publication_table=pub),  # inactive -> dropped
        FakeReport(publication_table=None),  # active but no sub-table -> skipped
    ]
    files = pd.DataFrame(
        [
            {"project_id": "P1", "is_active": "Yes"},
            {"project_id": "P2", "is_active": "No"},
            {"project_id": "P3", "is_active": "Yes"},
        ]
    )

    out = build_detail_csv(reports, files, "publication_table", PUBLICATION_COLS, None)

    assert out["project_id"].tolist() == ["P1"]


def test_build_detail_csv_is_active_is_case_sensitive():
    pub = _verbose_publication_df([["Web article", "T", "d", "p", "u"]])
    reports = [FakeReport(publication_table=pub)]
    files = pd.DataFrame([{"project_id": "P1", "is_active": "yes"}])  # lowercase

    out = build_detail_csv(reports, files, "publication_table", PUBLICATION_COLS, None)

    # only the exact string "Yes" counts as active (export.py: `!= "Yes"`)
    assert len(out) == 0


def test_build_detail_csv_drops_entirely_blank_rows():
    pub = _verbose_publication_df(
        [
            ["", "", "", "", ""],  # blank across every field -> dropped
            ["Web article", "", "", "", ""],  # has a type -> kept
        ]
    )
    reports = [FakeReport(publication_table=pub)]
    files = pd.DataFrame([{"project_id": "P1", "is_active": "Yes"}])

    out = build_detail_csv(reports, files, "publication_table", PUBLICATION_COLS, None)

    assert len(out) == 1
    assert out.iloc[0]["publication_type"] == "Web article"


def test_build_detail_csv_pads_short_tables():
    # 3 columns supplied, STUDENT_COLS expects 4
    stu = pd.DataFrame([["Jane", "Physics", "UA"]], columns=["n", "m", "a"])
    reports = [FakeReport(student_metrics_table=stu)]
    files = pd.DataFrame([{"project_id": "P1", "is_active": "Yes"}])

    out = build_detail_csv(reports, files, "student_metrics_table", STUDENT_COLS, None)

    assert list(out.columns) == ["project_id"] + STUDENT_COLS
    assert out.iloc[0]["level"] == ""  # padded blank


def test_build_detail_csv_truncates_extra_columns():
    pub = pd.DataFrame([["a", "b", "c", "d", "e", "EXTRA"]], columns=list("abcdef"))
    reports = [FakeReport(publication_table=pub)]
    files = pd.DataFrame([{"project_id": "P1", "is_active": "Yes"}])

    out = build_detail_csv(reports, files, "publication_table", PUBLICATION_COLS, None)

    assert list(out.columns) == ["project_id"] + PUBLICATION_COLS
    assert "EXTRA" not in out.iloc[0].tolist()


def test_build_detail_csv_empty_returns_headers_only():
    reports = [FakeReport(publication_table=None)]
    files = pd.DataFrame([{"project_id": "P1", "is_active": "Yes"}])

    out = build_detail_csv(reports, files, "publication_table", PUBLICATION_COLS, None)

    assert list(out.columns) == ["project_id"] + PUBLICATION_COLS
    assert len(out) == 0


def test_build_detail_csv_resets_files_index():
    pub = _verbose_publication_df([["Web article", "T", "d", "p", "u"]])
    reports = [FakeReport(publication_table=pub)]
    # a non-default index must not break positional reports[i] <-> files row i
    files = pd.DataFrame([{"project_id": "P1", "is_active": "Yes"}], index=[5])

    out = build_detail_csv(reports, files, "publication_table", PUBLICATION_COLS, None)

    assert out["project_id"].tolist() == ["P1"]


def test_build_detail_csv_stacks_multiple_active_reports():
    pub1 = _verbose_publication_df([["Web article", "T1", "d", "p", "u"]])
    pub2 = _verbose_publication_df([["Journal", "T2", "d2", "p2", "u2"]])
    reports = [FakeReport(publication_table=pub1), FakeReport(publication_table=pub2)]
    files = pd.DataFrame(
        [
            {"project_id": "P1", "is_active": "Yes"},
            {"project_id": "P2", "is_active": "Yes"},
        ]
    )

    out = build_detail_csv(reports, files, "publication_table", PUBLICATION_COLS, None)

    # long-format stack, each row carries its own project_id
    assert out["project_id"].tolist() == ["P1", "P2"]
    assert out.iloc[1]["title"] == "T2"


def test_build_detail_csv_writes_file(tmp_path):
    pub = _verbose_publication_df([["Web article", "T", "d", "p", "u"]])
    reports = [FakeReport(publication_table=pub)]
    files = pd.DataFrame([{"project_id": "P1", "is_active": "Yes"}])
    out_file = tmp_path / "publications.csv"

    build_detail_csv(reports, files, "publication_table", PUBLICATION_COLS, out_file)

    written = pd.read_csv(out_file)
    assert list(written.columns) == ["project_id"] + PUBLICATION_COLS
    assert written.iloc[0]["project_id"] == "P1"


# --------------------------------------------------------------------------- #
# build_master_table
#
# Docstring at export.py:178-186.
# --------------------------------------------------------------------------- #
def test_build_master_table_one_row_per_active_report(tmp_path):
    files = _make_files()
    status = pd.DataFrame(
        [
            {"category": "overall", "prior": "g", "current": "y", "rationale": "r1"},
            {"category": "cost", "prior": "g", "current": "g", "rationale": ""},
        ]
    )
    pub = _verbose_publication_df(
        [
            ["Web article", "T1", "d", "p", "u"],
            ["Peer-reviewed publication", "T2", "d2", "p2", "u2"],
        ]
    )
    reports = [
        FakeReport(publication_table=pub, project_status=status),
        FakeReport(),  # inactive -> dropped
    ]

    master = build_master_table(reports, files, tmp_path / "master.csv")

    assert len(master) == 1
    row = master.iloc[0]
    assert row["project_id"] == "P1"
    assert row["n_publications"] == 2
    assert row["n_patents"] == 0
    assert row["n_students"] == 0
    assert DETAIL_SEP in row["publications_detail"]
    assert row["overall_current"] == "y"
    assert row["overall_rationale"] == "r1"
    assert "index" not in master.columns  # reset_index artifact dropped


def test_build_master_table_counts_all_variable_tables(tmp_path):
    files = _make_files()
    pub = _verbose_publication_df([["Web article", "T", "d", "p", "u"]])
    pat = pd.DataFrame(
        [["Utility", "PatName", "123", "2026", "link"]], columns=list("abcde")
    )
    stu = pd.DataFrame(
        [["Jane", "Physics", "UA", "PhD"], ["Joe", "Math", "UB", "MS"]],
        columns=list("abcd"),
    )
    reports = [
        FakeReport(publication_table=pub, patents_table=pat, student_metrics_table=stu),
        FakeReport(),
    ]

    master = build_master_table(reports, files, tmp_path / "m.csv")

    row = master.iloc[0]
    assert row["n_publications"] == 1
    assert row["n_patents"] == 1
    assert row["n_students"] == 2
    assert row["patents_detail"] != ""
    assert row["students_detail"] != ""


def test_build_master_table_status_pivot_pads_absent_categories(tmp_path):
    files = _make_files()
    status = pd.DataFrame(
        [{"category": "overall", "prior": "g", "current": "y", "rationale": "r1"}]
    )
    reports = [FakeReport(project_status=status), FakeReport()]

    master = build_master_table(reports, files, tmp_path / "m.csv")

    row = master.iloc[0]
    assert row["overall_prior"] == "g"
    # categories not present in this report's status still exist, padded to ""
    assert row["cost_prior"] == ""
    assert row["technical_current"] == ""
    for c in STATUS_PIVOT_COLS:
        assert c in master.columns


def test_build_master_table_no_status_still_has_pivot_columns(tmp_path):
    files = _make_files()
    reports = [FakeReport(), FakeReport()]

    master = build_master_table(reports, files, tmp_path / "m.csv")

    row = master.iloc[0]
    for c in STATUS_PIVOT_COLS:
        assert c in master.columns
        assert row[c] == ""  # stable, blank-padded status columns


def test_build_master_table_pulls_trl_and_performance_period(tmp_path):
    files = _make_files()
    trl = pd.DataFrame(
        [{"input": "4", "current": "5", "planned_exit": "6"}],
        columns=["input", "current", "planned_exit"],
    )
    reports = [
        FakeReport(trl_status_table=trl, performance_period="01/01/26 - 12/31/26"),
        FakeReport(),
    ]

    master = build_master_table(reports, files, tmp_path / "m.csv")

    row = master.iloc[0]
    assert row["trl_input"] == "4"
    assert row["trl_current"] == "5"
    assert row["trl_planned_exit"] == "6"
    assert row["performance_period"] == "01/01/26 - 12/31/26"


def test_build_master_table_absent_trl_columns_when_no_report_has_trl(tmp_path):
    files = _make_files()
    reports = [FakeReport(), FakeReport()]  # no report supplies a TRL table

    master = build_master_table(reports, files, tmp_path / "m.csv")

    # TRL has no padding step (unlike project_status / accommodations), so with
    # no TRL data anywhere the columns never materialize. (Agreed behavior.)
    assert "trl_input" not in master.columns
    assert "trl_current" not in master.columns
    assert "trl_planned_exit" not in master.columns


def test_build_master_table_mixed_trl_leaves_nan_for_report_without(tmp_path):
    files = pd.DataFrame(
        [
            {
                "file_path": "/a",
                "report_date": "2026-04-01",
                "year": 2024,
                "project_id": "P1",
                "principal_investigator": "PI1",
                "is_active": "Yes",
            },
            {
                "file_path": "/b",
                "report_date": "2026-04-02",
                "year": 2024,
                "project_id": "P2",
                "principal_investigator": "PI2",
                "is_active": "Yes",
            },
        ]
    )
    trl = pd.DataFrame(
        [{"input": "4", "current": "5", "planned_exit": "6"}],
        columns=["input", "current", "planned_exit"],
    )
    reports = [FakeReport(trl_status_table=trl), FakeReport()]  # second lacks TRL

    master = build_master_table(reports, files, tmp_path / "m.csv")

    # column exists because at least one report supplied it; the report without
    # a TRL table is left NaN by the join (no blank-padding for TRL).
    assert "trl_input" in master.columns
    p1 = master[master["project_id"] == "P1"].iloc[0]
    p2 = master[master["project_id"] == "P2"].iloc[0]
    assert p1["trl_input"] == "4"
    assert pd.isna(p2["trl_input"])


def test_build_master_table_pulls_accommodations(tmp_path):
    files = _make_files()
    accom = _accom_df(
        [{"category": "payload size", "sub_category": "length", "value": 10.0}]
    )
    reports = [FakeReport(accomodation_table=accom), FakeReport()]

    master = build_master_table(reports, files, tmp_path / "m.csv")

    assert master.iloc[0]["length"] == 10.0
    # the full accommodation field set is always present as columns
    for name in ACCOMMODATION_FIELDS:
        assert name in master.columns


def test_build_master_table_zero_active_reports_yields_empty_frame(tmp_path):
    files = pd.DataFrame(
        [
            {
                "file_path": "/a",
                "report_date": "2026-04-01",
                "year": 2024,
                "project_id": "P1",
                "principal_investigator": "PI1",
                "is_active": "No",
            }
        ]
    )
    reports = [FakeReport()]

    master = build_master_table(reports, files, tmp_path / "m.csv")

    assert len(master) == 0
    # columns still present even with no active rows
    assert "project_id" in master.columns
    for c in STATUS_PIVOT_COLS:
        assert c in master.columns


def test_build_master_table_returns_single_level_columns(tmp_path):
    files = _make_files()
    reports = [FakeReport(), FakeReport()]

    master = build_master_table(reports, files, tmp_path / "m.csv")

    # grouping is applied only in the file; the returned frame is flat
    assert not isinstance(master.columns, pd.MultiIndex)


def test_build_master_table_columns_grouped_contiguously_in_group_order(tmp_path):
    files = _make_files()
    reports = [FakeReport(), FakeReport()]

    master = build_master_table(reports, files, tmp_path / "m.csv")

    groups = [group_for(c) for c in master.columns]
    # collapse consecutive duplicates into the sequence of group blocks
    seen = []
    for g in groups:
        if not seen or seen[-1] != g:
            seen.append(g)
    # each group is contiguous (appears exactly once) ...
    assert len(seen) == len(set(seen))
    # ... and the blocks follow GROUP_ORDER
    assert seen == [g for g in GROUP_ORDER if g in seen]


def test_build_master_table_within_group_order_matches_source(tmp_path):
    files = _make_files()
    accom = _accom_df(
        [{"category": "payload size", "sub_category": "length", "value": 10.0}]
    )
    status = pd.DataFrame(
        [{"category": "overall", "prior": "g", "current": "y", "rationale": "r"}]
    )
    reports = [
        FakeReport(accomodation_table=accom, project_status=status),
        FakeReport(),
    ]

    master = build_master_table(reports, files, tmp_path / "m.csv")
    cols = list(master.columns)

    # accommodations columns appear in ACCOMMODATION_FIELDS declaration order
    accom_cols = [c for c in cols if group_for(c) == "accommodations"]
    assert accom_cols == list(ACCOMMODATION_FIELDS)
    # project-status pivot columns appear in STATUS_PIVOT_COLS order
    status_cols = [c for c in cols if c in STATUS_PIVOT_COLS]
    assert status_cols == STATUS_PIVOT_COLS


def test_build_master_table_writes_two_row_header(tmp_path):
    files = _make_files()
    status = pd.DataFrame(
        [{"category": "overall", "prior": "g", "current": "y", "rationale": "r"}]
    )
    reports = [FakeReport(project_status=status), FakeReport()]
    out_file = tmp_path / "m.csv"

    master = build_master_table(reports, files, out_file)

    lines = out_file.read_text(encoding="utf-8").splitlines()
    top = lines[0].split(",")
    bottom = lines[1].split(",")
    # top row = source group per column, bottom row = the column names
    assert top == [group_for(c) for c in master.columns]
    assert bottom == list(master.columns)
    # exactly two header rows, then one data row per master row
    assert len(lines) == 2 + len(master)
    # spot-check specific (group, field) pairings
    pairs = list(zip(top, bottom))
    assert ("summary", "project_id") in pairs
    assert ("project_status", "overall_prior") in pairs
    assert ("metadata", "file_path") in pairs


# --------------------------------------------------------------------------- #
# integration against the bundled test report
# --------------------------------------------------------------------------- #
def test_build_detail_csv_with_real_report(tmp_path):
    report = Report(_test_report_pptx)
    files = pd.DataFrame([{"project_id": report.project_id, "is_active": "Yes"}])

    out = build_detail_csv(
        [report], files, "publication_table", PUBLICATION_COLS, tmp_path / "pub.csv"
    )

    assert list(out.columns) == ["project_id"] + PUBLICATION_COLS
    assert out.iloc[0]["project_id"] == "24-HTIDS24-0009"
    assert out.iloc[0]["publication_type"] == "Conference presentation (oral)"
    assert out.iloc[0]["title"].startswith("Development of the Next-Generation")


def test_build_detail_csv_status_includes_rationale_column(tmp_path):
    report = Report(_test_report_pptx)
    files = pd.DataFrame([{"project_id": report.project_id, "is_active": "Yes"}])

    out = build_detail_csv([report], files, "project_status", STATUS_COLS, None)

    assert list(out.columns) == ["project_id"] + STATUS_COLS
    assert (out["category"] == "overall").any()
