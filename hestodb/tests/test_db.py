from hestodb import db


def test_schema_file_exists_and_has_core_tables():
    sql = db.get_schema_sql()
    assert "CREATE TABLE mission" in sql
    assert "CREATE TABLE awards" in sql
    assert "CREATE TABLE reports" in sql


def test_schema_file_path_points_to_db_sql_file():
    assert db.SCHEMA_FILE.name == "postgres_schema.sql"
    assert db.SCHEMA_FILE.parent.name == "db"
    assert db.SCHEMA_FILE.exists()


def test_sql_mermaid_render_contains_key_relationships():
    diagram = db.render_mermaid_schema_from_sql()
    assert diagram.startswith("erDiagram")
    assert "mission ||--o{ technology : mission_id" in diagram
    assert "awards ||--o{ reports : award_id" in diagram


def test_write_mermaid_schema_from_sql(tmp_path):
    output = db.write_mermaid_schema_from_sql(tmp_path / "schema.mmd")
    text = output.read_text(encoding="utf-8")
    assert output.exists()
    assert text.startswith("erDiagram")


def test_schema_mermaid_preview_diagnostic_passes():
    ok, issues = db.check_schema_mermaid_preview_diagnostic()
    assert ok, "\n".join(issues)


def test_sql_derived_mermaid_preview_diagnostic_passes():
    diagram = db.render_mermaid_schema_from_sql()
    issues = db.validate_mermaid_er_diagram(diagram)
    assert issues == []
