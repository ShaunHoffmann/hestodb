import pandas as pd

from hestodb import _test_report_pptx
from hestodb.report import Report
from hestodb.export import (
    build_detail_csv,
    build_master_table,
    accommodation_fields,
    group_for,
    ACCOMMODATION_FIELDS,
    DETAIL_SEP,
    GROUP_ORDER,
    PUBLICATION_COLS,
    STUDENT_COLS,
    STATUS_COLS,
)


class FakeReport:
    """Minimal stand-in exposing the four sub-table attributes."""

    def __init__(
        self,
        publication_table=None,
        patents_table=None,
        student_metrics_table=None,
        project_status=None,
        accomodation_table=None,
        trl_status_table=None,
        performance_period="",
    ):
        self.publication_table = publication_table
        self.patents_table = patents_table
        self.student_metrics_table = student_metrics_table
        self.project_status = project_status
        self.accomodation_table = accomodation_table
        self.trl_status_table = trl_status_table
        self.performance_period = performance_period


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


# --------------------------------------------------------------------------- #
# group_for
# --------------------------------------------------------------------------- #
def test_group_for_maps_known_columns():
    assert group_for("project_id") == "summary"
    assert group_for("length") == "accommodations"
    assert group_for("overall_prior") == "project_status"
    assert group_for("n_patents") == "patents"
    assert group_for("students_detail") == "student_metrics"
    assert group_for("trl_input") == "trl_status"
    assert group_for("trl_current") == "trl_status"
    assert group_for("trl_planned_exit") == "trl_status"
    # performance_period rolls up under the project_status header
    assert group_for("performance_period") == "project_status"


def test_group_for_unknown_column_is_metadata():
    assert group_for("file_path") == "metadata"
    assert group_for("report_date") == "metadata"


# --------------------------------------------------------------------------- #
# build_detail_csv
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


def test_build_detail_csv_skips_inactive_and_none_reports():
    pub = _verbose_publication_df([["Web article", "T", "d", "p", "u"]])
    reports = [
        FakeReport(publication_table=pub),  # active -> kept
        FakeReport(publication_table=pub),  # inactive -> dropped
        FakeReport(publication_table=None),  # active but None -> skipped
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


def test_build_detail_csv_drops_entirely_blank_rows():
    pub = _verbose_publication_df(
        [
            ["", "", "", "", ""],  # blank -> dropped
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
# --------------------------------------------------------------------------- #
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
        FakeReport(),  # inactive
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
    assert "index" not in master.columns


def test_build_master_table_pulls_trl_and_performance_period(tmp_path):
    files = _make_files()
    trl = pd.DataFrame(
        [{"input": "4", "current": "5", "planned_exit": "6"}],
        columns=["input", "current", "planned_exit"],
    )
    reports = [
        FakeReport(trl_status_table=trl, performance_period="01/01/26 - 12/31/26"),
        FakeReport(),  # inactive
    ]

    master = build_master_table(reports, files, tmp_path / "m.csv")

    row = master.iloc[0]
    assert row["trl_input"] == "4"
    assert row["trl_current"] == "5"
    assert row["trl_planned_exit"] == "6"
    assert row["performance_period"] == "01/01/26 - 12/31/26"


def test_build_master_table_columns_grouped_contiguously_in_order(tmp_path):
    files = _make_files()
    reports = [FakeReport(), FakeReport()]

    master = build_master_table(reports, files, tmp_path / "m.csv")

    groups = [group_for(c) for c in master.columns]
    # collapse consecutive duplicates -> order of first appearance
    seen = []
    for g in groups:
        if not seen or seen[-1] != g:
            seen.append(g)
    # each group appears exactly once (contiguous) and follows GROUP_ORDER
    assert len(seen) == len(set(seen))
    idxs = [GROUP_ORDER.index(g) for g in seen]
    assert idxs == sorted(idxs)


def test_build_master_table_writes_two_row_header(tmp_path):
    files = _make_files()
    reports = [FakeReport(), FakeReport()]
    out_file = tmp_path / "m.csv"

    build_master_table(reports, files, out_file)

    df = pd.read_csv(out_file, header=[0, 1])
    top_level = {c[0] for c in df.columns}
    assert {"metadata", "summary", "project_status"} <= top_level
    assert ("summary", "project_id") in list(df.columns)


# --------------------------------------------------------------------------- #
# accommodation_fields
# --------------------------------------------------------------------------- #
def _accom_df(rows):
    return pd.DataFrame(rows, columns=["category", "sub_category", "value"])


def test_accommodation_fields_flattens_named_columns():
    accom = _accom_df(
        [
            {"category": "payload size", "sub_category": "length", "value": 10.0},
            {"category": "mass", "sub_category": "", "value": 5.4},
        ]
    )
    fields = accommodation_fields(FakeReport(accomodation_table=accom))

    assert set(fields) == set(ACCOMMODATION_FIELDS)  # always the full field set
    assert fields["length"] == 10.0
    assert fields["total_mass"] == 5.4
    assert fields["width"] is None  # absent rows -> None


def test_accommodation_fields_handles_missing_table():
    fields = accommodation_fields(FakeReport(accomodation_table=None))
    assert set(fields) == set(ACCOMMODATION_FIELDS)
    assert all(v is None for v in fields.values())


def test_build_master_table_pulls_accommodations_from_report(tmp_path):
    files = _make_files()
    accom = _accom_df(
        [
            {"category": "payload size", "sub_category": "length", "value": 10.0},
        ]
    )
    reports = [FakeReport(accomodation_table=accom), FakeReport()]

    master = build_master_table(reports, files, tmp_path / "m.csv")

    assert group_for("length") == "accommodations"
    assert master.iloc[0]["length"] == 10.0


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
