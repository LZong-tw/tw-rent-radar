"""Tests for the CLI skeleton."""

import pytest
from click.testing import CliRunner

from tw_rent_radar.cli import cli
from tw_rent_radar.db import create_tables, get_engine


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def empty_db(tmp_path):
    db_path = tmp_path / "test.db"
    engine = get_engine(str(db_path))
    create_tables(engine)
    return str(db_path)


def test_help(runner):
    """--help works."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "tw-rent-radar" in result.output.lower() or "Usage" in result.output


def test_search_empty_db(runner, empty_db):
    """search with empty db returns empty."""
    result = runner.invoke(cli, ["search", "--db", empty_db])
    assert result.exit_code == 0


def test_search_json_empty_db(runner, empty_db):
    """search --json with empty db returns []."""
    result = runner.invoke(cli, ["search", "--json", "--db", empty_db])
    assert result.exit_code == 0
    assert "[]" in result.output


def test_stats_empty_db(runner, empty_db):
    """stats with empty db works."""
    result = runner.invoke(cli, ["stats", "--db", empty_db])
    assert result.exit_code == 0


def test_list_sources(runner):
    """list sources shows all platform names."""
    result = runner.invoke(cli, ["list", "sources"])
    assert result.exit_code == 0
    assert "591" in result.output
    assert "rakuya" in result.output
    assert "fcrent" in result.output
    assert "fb_group" in result.output
    assert "fb_market" in result.output
