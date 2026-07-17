import pytest
import pandas as pd
from datetime import date
from hestodb import _test_files_directory
from hestodb.report import (
    Report,
    check_volume_calculation,
    extract_summary_fields,
    SUMMARY_FIELD_SPEC,
)

test_report_file = (
    _test_files_directory / "HESTO-202612_Report_24-HTIDS24_Smith-rev3.pptx"
)


def test_report():
    report = Report(test_report_file)
    assert isinstance(report, Report)


def test_report_string_path():
    report = Report(str(test_report_file))
    assert isinstance(report, Report)


def test_report_slide_count():
    report = Report(test_report_file)
    assert len(report.slide_titles) == 34


def test_report_project_id():
    report = Report(test_report_file)
    assert report.project_id == "24-HTIDS24-0009"


def test_report_principal_investigator():
    report = Report(test_report_file)
    assert report.principal_investigator == "Jane Smith"


def test_report_slide_titles():
    report = Report(test_report_file)
    expected_titles = [
        "hesto report: 12 2026",
        "summary",
        "    project\u2019s relevance and impact ",
        "key accomplishments",
        "project highlights",
        "system trl status",
        "technology maturation and infusion",
        "science traceability matrix",
        "project summary",
        "issue log",
        "budget reporting",
        "planned accomplishments",
        "student metrics",
        "hesto support",
        "      anticipated payload accommodation need ",
        "      presentations",
        "patents, licenses",
        "lessons learned",
        "content for techport",
        "content for techport",
        "backup material",
        "development concept",
        "supporting material",
        "guidance material",
        "taxonomy and keyword guidance",
        "slide guidance 1",
        "slide guidance 2",
        "slide guidance 3",
        "strong relevance and impact example",
        "fever chart guidance",
        "budget report definitions",
        "identifiers 1",
        "identifiers 2",
        "thank you",
    ]
    assert report.slide_titles == expected_titles


def test_report_file_not_found():
    with pytest.raises(FileNotFoundError):
        Report("nonexistent_file.pptx")


def test_report_repr():
    report = Report(test_report_file)
    result = repr(report)
    assert "HESTO-202612_Report_24-HTIDS24_Smith-rev3.pptx" in result
    assert "34 slides" in result
    assert "24-HTIDS24-0009" in result
    assert "Jane Smith" in result


def test_report_accomodation_table():
    report = Report(test_report_file)
    df = report.accomodation_table
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["category", "sub_category", "value"]

    def get_value(category, sub_category=""):
        rows = df[(df["category"] == category) & (df["sub_category"] == sub_category)]
        return rows["value"].iloc[0]

    assert get_value("payload size", "length") == 10.0
    assert get_value("payload size", "width") == 10.0
    assert get_value("payload size", "height") == 10.0
    assert get_value("payload volume") == 1.0
    assert get_value("power requirements", "average") == 5.0
    assert get_value("power requirements", "peak") == 10.0
    assert get_value("mass") == 5.4
    assert get_value("pointing requirements", "arcsecs") == 60.0
    assert get_value("pointing requirements", "arcminutes") == 1.0
    assert get_value("data rate", "average") == 15.0
    assert get_value("data rate", "peak") == 100.0
    assert get_value("power interface port") == "db-9, 28 v, 1a"
    assert get_value("communication interface protocol") == "uart"
    assert get_value("data communication port") == "db-9"
    assert get_value("requires thermal isolation") == "false"
    assert get_value("special power considerations") == "none"


def test_report_accomodation_table_records_match_expected():
    report = Report(test_report_file)
    records = report.accomodation_table.to_dict(orient="records")
    expected = [
        {"category": "payload size", "sub_category": "length", "value": 10.0},
        {"category": "payload size", "sub_category": "width", "value": 10.0},
        {"category": "payload size", "sub_category": "height", "value": 10.0},
        {"category": "payload volume", "sub_category": "", "value": 1.0},
        {"category": "power requirements", "sub_category": "average", "value": 5.0},
        {"category": "power requirements", "sub_category": "peak", "value": 10.0},
        {"category": "mass", "sub_category": "", "value": 5.4},
        {"category": "pointing requirements", "sub_category": "arcsecs", "value": 60.0},
        {
            "category": "pointing requirements",
            "sub_category": "arcminutes",
            "value": 1.0,
        },
        {"category": "data rate", "sub_category": "average", "value": 15.0},
        {"category": "data rate", "sub_category": "peak", "value": 100.0},
        {
            "category": "power interface port",
            "sub_category": "",
            "value": "db-9, 28 v, 1a",
        },
        {
            "category": "communication interface protocol",
            "sub_category": "",
            "value": "uart",
        },
        {"category": "data communication port", "sub_category": "", "value": "db-9"},
        {
            "category": "requires thermal isolation",
            "sub_category": "",
            "value": "false",
        },
        {
            "category": "special power considerations",
            "sub_category": "",
            "value": "none",
        },
    ]
    assert records == expected


def test_report_publication_table_records_match_expected():
    report = Report(test_report_file)
    records = report.publication_table.to_dict(orient="records")
    expected = [
        {
            "Type choose one of below": "Conference presentation (oral)",
            "Title": "Development of the Next-Generation Solar X-ray detector",
            "Publication/Presentation Date": date(2026, 1, 23),
            "Publisher/Conference Name": "IEEE NSS/MIC",
            "URL": "https://ieeexplore.ieee.org/document/10657175",
        }
    ]
    assert records == expected


def test_report_patents_table_records_match_expected():
    report = Report(test_report_file)
    records = report.patents_table.to_dict(orient="records")
    expected = [
        {
            "Type (Issued, Filing)": "Issued",
            "Name": "Art of transmitting electrical energy through the natural mediums",
            "Patent or License Number": "US787412A",
            "Date": date(1900, 5, 16),
            "Resource Link (e.g., Google Patents Link)": "https://patents.google.com/patent/US787412A/",
        }
    ]
    assert records == expected


def test_report_student_metrics_table_records_match_expected():
    report = Report(test_report_file)
    records = report.student_metrics_table.to_dict(orient="records")
    expected = [
        {
            "Student Name (first last)": "John Doe",
            "Major": "Physics",
            "Affiliation (School, University, etc.)": "University of Alabama",
            "Level (High School, Undergrad, Grad, PhD)": "Undergrad",
        }
    ]
    assert records == expected


def test_report_accomodation_table_numeric_values():
    report = Report(test_report_file)
    df = report.accomodation_table
    numeric_categories = {
        "payload size",
        "payload volume",
        "power requirements",
        "mass",
        "pointing requirements",
        "data rate",
    }
    for _, row in df[df["category"].isin(numeric_categories)].iterrows():
        assert isinstance(row["value"], (int, float)), (
            f"{row['category']}[{row['sub_category']!r}] should be numeric"
        )


def test_report_payload_consistency():
    report = Report(test_report_file)
    df = report.accomodation_table
    size = df[df["category"] == "payload size"].set_index("sub_category")["value"]
    volume = df[df["category"] == "payload volume"]["value"].iloc[0]
    assert (
        check_volume_calculation(size["length"], size["width"], size["height"], volume)
        is True
    )


def test_report_project_status_overall_yellow():
    report = Report(test_report_file)
    df = report.project_status
    current = df[df["category"] == "overall"]["current"].iloc[0]
    assert current == "y"


def test_report_trl_status_table():
    report = Report(test_report_file)
    df = report.trl_status_table
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["input", "current", "planned_exit"]
    assert len(df) == 1
    row = df.iloc[0]
    assert row["input"] == "4"
    assert row["current"] == "5"
    assert row["planned_exit"] == "6"


def test_report_performance_period():
    report = Report(test_report_file)
    # 2x6 metadata table on the Project Summary slide, cell (0, 5)
    assert report.performance_period == "MM/DD/YY – MM/DD/YY"


# --------------------------------------------------------------------------- #
# extract_summary_fields
#
# Sole owner of the Summary-slide label -> field mapping (SUMMARY_FIELD_SPEC),
# shared by Report._process_summary and util.find_latest_report_pptx.
# --------------------------------------------------------------------------- #
def test_extract_summary_fields_real_report_matches_template():
    report = Report(test_report_file)

    assert extract_summary_fields(report.summary) == {
        "project_id": "24-HTIDS24-0009",
        "principal_investigator": "Jane Smith",
        "email": "Jane.smith@fakeemail.org",
        "affiliation": "NASA Goddard Space Flight Center",
        "research_regime": "heliosphere",
        "proposal_title": "A project to develop a new x-ray detector",
        # U+2013 EN DASH, not a hyphen -- verified against the template deck
        "hesto_taxonomy": "Photons \u2013 X-rays",
        "technology_keyword": "Quantum Sensing",
        "techport_url": "https://techport.nasa.gov/projects/95780",
        "technology_name": "AWESOME",
        "instrument_types": "Spectrometer",
        "project_summary": (
            "This is a project to develop a new x-ray detector. "
            "This is the second sentence. This is the third sentence."
        ),
    }


@pytest.mark.parametrize("bad_summary", [None, {}, "not a dict", 42, []])
def test_extract_summary_fields_never_raises_and_returns_all_none(bad_summary):
    # Batch-parser rule: one malformed deck must not stop the batch.
    fields = extract_summary_fields(bad_summary)
    assert set(fields) == set(SUMMARY_FIELD_SPEC)
    assert all(value is None for value in fields.values())


def test_extract_summary_fields_prefix_tolerates_trimmed_parentheticals():
    # A PI who trims the trailing instruction -- "Technology Name (Acronym)"
    # -> "Technology Name" -- must still match. This is the shape test_util.py's
    # mock fixture actually uses.
    fields = extract_summary_fields(
        {
            "technology name": "TestTech",
            "instrument type": "Imager",
            "project summary": "Test summary",
        }
    )
    assert fields["technology_name"] == "TestTech"
    assert fields["instrument_types"] == "Imager"
    assert fields["project_summary"] == "Test summary"


def test_extract_summary_fields_prefix_does_not_cross_match_technology_labels():
    # "technology keyword" must not be captured by the "technology name" prefix.
    fields = extract_summary_fields({"technology keyword": "Quantum Sensing"})
    assert fields["technology_keyword"] == "Quantum Sensing"
    assert fields["technology_name"] is None


def test_extract_summary_fields_blank_or_non_string_values_are_none():
    fields = extract_summary_fields(
        {
            "proposal title": "   ",  # blank -> None
            "pi email": None,  # missing value -> None
            "techport url": 12345,  # non-string (e.g. JSON cache) -> None
            "hesto taxonomy": "  Photons \u2013 X-rays  ",  # stripped
        }
    )
    assert fields["proposal_title"] is None
    assert fields["email"] is None
    assert fields["techport_url"] is None
    assert fields["hesto_taxonomy"] == "Photons \u2013 X-rays"


def test_summary_field_spec_modes_and_labels_are_well_formed():
    # Labels are compared against parse_summary_slide's already-lowercased keys.
    for _, (how, label) in SUMMARY_FIELD_SPEC.items():
        assert how in {"exact", "prefix"}
        assert label == label.lower()


def test_report_summary_attributes_survive_extractor_refactor():
    # Only project_id / principal_investigator are stored on Report (read by
    # __repr__ and get_accomodation_data); they keep their legacy "" semantics.
    report = Report(test_report_file)
    assert report.project_id == "24-HTIDS24-0009"
    assert report.principal_investigator == "Jane Smith"


def test_report_no_longer_stores_redundant_summary_attributes():
    # email / affiliation / research_regime were removed: the summary dict is the
    # single source, read through extract_summary_fields.
    report = Report(test_report_file)

    for attribute in ["email", "affiliation", "research_regime"]:
        assert not hasattr(report, attribute), f"{attribute} should be removed"

    fields = extract_summary_fields(report.summary)
    assert fields["email"] == "Jane.smith@fakeemail.org"
    assert fields["affiliation"] == "NASA Goddard Space Flight Center"
    assert fields["research_regime"] == "heliosphere"
