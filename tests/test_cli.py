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


def test_search_chinese_characters_in_output(runner, empty_db):
    """Chinese characters in listing data render correctly in CLI output.

    This was a real bug on Windows: sys.stdout with cp950 encoding raised
    UnicodeEncodeError for Chinese characters outside the Big5 range.
    """
    from tw_rent_radar.db import Session, get_engine, upsert_listing

    engine = get_engine(empty_db)
    with Session(engine) as session:
        upsert_listing(
            session,
            source="591",
            source_id="chinese1",
            title="三民區溫馨套房 近高雄車站",
            price=8500,
            city="高雄市",
            district="三民區",
        )
        session.commit()

    # JSON output should contain the Chinese characters
    result = runner.invoke(cli, ["search", "--json", "--db", empty_db])
    assert result.exit_code == 0
    assert "三民區溫馨套房" in result.output
    assert "高雄市" in result.output

    # Table output should also work
    result = runner.invoke(cli, ["search", "--db", empty_db])
    assert result.exit_code == 0
    assert "三民區溫馨套房" in result.output


def test_show_chinese_characters(runner, empty_db):
    """show command handles Chinese text correctly."""
    from tw_rent_radar.db import Session, get_engine, upsert_listing

    engine = get_engine(empty_db)
    with Session(engine) as session:
        upsert_listing(
            session,
            source="fcrent",
            source_id="cn1",
            title="苓雅區兩房一廳",
            price=16000,
            city="高雄市",
            district="苓雅區",
            description="近捷運站，可開伙，天然瓦斯",
        )
        session.commit()

    result = runner.invoke(cli, ["show", "1", "--json", "--db", empty_db])
    assert result.exit_code == 0
    assert "苓雅區兩房一廳" in result.output
    assert "可開伙" in result.output


def test_crawl_geocodes_listings(runner, empty_db, monkeypatch):
    """crawl command geocodes listings that have addresses."""
    from unittest.mock import AsyncMock, patch

    from tw_rent_radar.crawlers.rent591 import Rent591Crawler

    mock_crawl = AsyncMock(
        return_value=[
            {
                "source": "591",
                "source_id": "geo_test_1",
                "title": "Test",
                "price": 10000,
                "city": "高雄市",
                "address": "前鎮區復興四路2號",
            }
        ]
    )
    monkeypatch.setattr(Rent591Crawler, "crawl", mock_crawl)

    with patch("tw_rent_radar.cli.geocode_listing") as mock_geo:
        result = runner.invoke(cli, ["crawl", "591", "--city", "高雄市", "--db", empty_db])
        assert result.exit_code == 0
        mock_geo.assert_called_once()
