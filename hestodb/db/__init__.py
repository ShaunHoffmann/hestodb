"""Database helpers that use hesto/db/postgres_schema.sql as source of truth."""

from __future__ import annotations

from pathlib import Path
import re

from sqlalchemy import MetaData, create_engine, text

SCHEMA_FILE = Path(__file__).resolve().with_name("postgres_schema.sql")
SCHEMA_MERMAID_FILE = Path(__file__).resolve().with_name("schema.mmd")


def get_schema_sql() -> str:
    """Return the raw SQL schema text from hesto/db/postgres_schema.sql."""
    return SCHEMA_FILE.read_text(encoding="utf-8")


def create_schema(engine) -> None:
    """Apply the schema SQL to the provided SQLAlchemy engine."""
    schema_sql = get_schema_sql()
    with engine.begin() as connection:
        connection.execute(text(schema_sql))


def reflect_metadata(engine) -> MetaData:
    """Reflect and return metadata from an existing database."""
    metadata = MetaData()
    metadata.reflect(bind=engine)
    return metadata


def render_mermaid_schema(engine) -> str:
    """Render a Mermaid ER diagram from reflected DB metadata."""
    metadata = reflect_metadata(engine)
    lines = ["erDiagram"]

    for table in sorted(metadata.tables.values(), key=lambda t: t.name):
        lines.append(f"    {table.name} {{")
        for column in table.columns:
            type_label = _type_label(column)
            flags = []
            if column.primary_key:
                flags.append("PK")
            if column.foreign_keys:
                flags.append("FK")
            if not column.nullable and not column.primary_key:
                flags.append("NN")
            suffix = f" {' '.join(flags)}" if flags else ""
            lines.append(f"        {type_label} {column.name}{suffix}")
        lines.append("    }")

    seen_edges = set()
    for table in sorted(metadata.tables.values(), key=lambda t: t.name):
        for fk_constraint in table.foreign_key_constraints:
            parent = fk_constraint.referred_table.name
            child = table.name
            child_cols = tuple(
                sorted(element.parent.name for element in fk_constraint.elements)
            )
            edge_key = (parent, child, child_cols)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            label = ", ".join(element.parent.name for element in fk_constraint.elements)
            lines.append(f"    {parent} ||--o{{ {child} : {label}")

    return "\n".join(lines)


def write_mermaid_schema(engine, output_path: str | Path) -> Path:
    """Write Mermaid ER diagram text to a file from a live database."""
    output = Path(output_path)
    output.write_text(render_mermaid_schema(engine), encoding="utf-8")
    return output


def render_mermaid_schema_from_sql(schema_sql: str | None = None) -> str:
    """Render Mermaid ER diagram text directly from schema SQL text."""
    sql = schema_sql if schema_sql is not None else get_schema_sql()
    table_blocks = re.findall(r"CREATE TABLE\s+(\w+)\s*\((.*?)\)\s*\n\n", sql, re.S)

    tables: dict[str, list[tuple[str, str]]] = {}
    edges: list[tuple[str, str, str]] = []

    for table_name, body in table_blocks:
        columns: list[tuple[str, str]] = []
        for raw_line in body.splitlines():
            line = raw_line.strip().rstrip(",")
            if not line:
                continue

            upper = line.upper()
            if upper.startswith(("PRIMARY KEY", "UNIQUE", "CHECK", "CONSTRAINT")):
                continue

            if upper.startswith("FOREIGN KEY"):
                fk = re.search(
                    r"FOREIGN KEY\((\w+)\) REFERENCES\s+(\w+)\s*\((\w+)\)",
                    line,
                    re.I,
                )
                if fk:
                    child_col, parent, _ = fk.groups()
                    edges.append((parent, table_name, child_col))
                continue

            column_match = re.match(
                r"(\w+)\s+([A-Z][A-Z0-9_]*(?:\([^)]*\))?)", line, re.I
            )
            if column_match:
                col_name = column_match.group(1)
                col_type = _sanitize_mermaid_type_label(column_match.group(2).upper())
                columns.append((col_name, col_type))

        tables[table_name] = columns

    for child, child_col, parent, _ in re.findall(
        r"ALTER TABLE\s+(\w+)\s+ADD CONSTRAINT\s+\w+\s+FOREIGN KEY\s*\((\w+)\)\s+REFERENCES\s+(\w+)\((\w+)\)",
        sql,
        re.I | re.S,
    ):
        edges.append((parent, child, child_col))

    lines = ["erDiagram"]
    for table_name in sorted(tables):
        lines.append(f"    {table_name} {{")
        for col_name, col_type in tables[table_name]:
            lines.append(f"        {col_type} {col_name}")
        lines.append("    }")

    seen_edges: set[tuple[str, str, str]] = set()
    for parent, child, child_col in edges:
        edge_key = (parent, child, child_col)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        lines.append(f"    {parent} ||--o{{ {child} : {child_col}")

    return "\n".join(lines)


def write_mermaid_schema_from_sql(output_path: str | Path | None = None) -> Path:
    """Write Mermaid ER diagram text generated from postgres_schema.sql."""
    output = Path(output_path) if output_path is not None else SCHEMA_MERMAID_FILE
    output.write_text(render_mermaid_schema_from_sql(), encoding="utf-8")
    return output


def validate_mermaid_er_diagram(diagram_text: str) -> list[str]:
    """Return preview-compatibility issues for a Mermaid ER diagram."""
    issues: list[str] = []
    lines = diagram_text.splitlines()

    non_comment = [
        line for line in lines if line.strip() and not line.lstrip().startswith("%%")
    ]
    if not non_comment or non_comment[0].strip() != "erDiagram":
        issues.append("First non-comment line must be 'erDiagram'.")
        return issues

    table_start_re = re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*\{$")
    table_end_re = re.compile(r"^\s*\}\s*$")
    field_re = re.compile(
        r"^\s*[A-Z][A-Z0-9_]*(?:\([^)]*\))?\s+[A-Za-z_][A-Za-z0-9_]*(?:\s+(?:PK|FK|NN)(?:\s+(?:PK|FK|NN))*)?\s*$"
    )
    relation_re = re.compile(
        r"^\s*[A-Za-z_][A-Za-z0-9_]*\s+\|\|--o\{\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*[A-Za-z_][A-Za-z0-9_, ]*\s*$"
    )

    in_table = False
    for line_no, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("%%"):
            continue
        if line == "erDiagram":
            continue

        if in_table:
            if table_end_re.match(raw):
                in_table = False
                continue
            if not field_re.match(raw):
                issues.append(f"Line {line_no}: invalid field declaration '{line}'.")
            continue

        if table_start_re.match(raw):
            in_table = True
            continue

        if relation_re.match(raw):
            continue

        issues.append(f"Line {line_no}: unrecognized Mermaid ER syntax '{line}'.")

    if in_table:
        issues.append("Unclosed table block: missing '}'.")

    return issues


def check_schema_mermaid_preview_diagnostic(
    schema_path: str | Path | None = None,
) -> tuple[bool, list[str]]:
    """Check that schema.mmd conforms to supported Mermaid ER syntax."""
    path = Path(schema_path) if schema_path is not None else SCHEMA_MERMAID_FILE
    issues = validate_mermaid_er_diagram(path.read_text(encoding="utf-8"))
    return (len(issues) == 0, issues)


def _type_label(column) -> str:
    type_name = type(column.type).__name__
    if type_name == "ENUM":
        return getattr(column.type, "name", "ENUM")
    if type_name == "CITEXT":
        return "CITEXT"
    if type_name == "INTEGER":
        return "INTEGER"
    if type_name == "BIGINT":
        return "BIGINT"
    if type_name == "NUMERIC":
        precision = getattr(column.type, "precision", None)
        scale = getattr(column.type, "scale", None)
        if precision is not None and scale is not None:
            return f"NUMERIC({precision},{scale})"
        return "NUMERIC"
    if type_name == "BOOLEAN":
        return "BOOLEAN"
    if type_name == "DATE":
        return "DATE"
    if type_name in {"TIMESTAMP", "DATETIME"}:
        return "TIMESTAMPTZ"
    if type_name == "VARCHAR":
        length = getattr(column.type, "length", None)
        return f"VARCHAR({length})" if length else "VARCHAR"
    if type_name == "TEXT":
        return "TEXT"
    return type_name.upper()


def _sanitize_mermaid_type_label(type_label: str) -> str:
    """Strip SQL precision/length suffixes for Mermaid ER parser compatibility."""
    return re.sub(r"\([^)]*\)", "", type_label).strip()


def build_engine(url: str):
    """Create a SQLAlchemy engine from a database URL."""
    return create_engine(url)


__all__ = [
    "SCHEMA_FILE",
    "SCHEMA_MERMAID_FILE",
    "get_schema_sql",
    "create_schema",
    "reflect_metadata",
    "render_mermaid_schema",
    "render_mermaid_schema_from_sql",
    "write_mermaid_schema",
    "write_mermaid_schema_from_sql",
    "validate_mermaid_er_diagram",
    "check_schema_mermaid_preview_diagnostic",
    "build_engine",
]
