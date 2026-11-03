"""Unit tests for the Markdown escaping in the report service."""

from app.services.report_service import escape_cell, escape_text


def test_html_is_escaped():
    assert escape_text("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_table_cells_cannot_break_the_table():
    assert escape_cell("a|b\nc") == "a\\|b c"


def test_empty_values_show_a_dash():
    assert escape_text(None) == "—"
    assert escape_cell("") == "—"
