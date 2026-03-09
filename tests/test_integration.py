import json

from click.testing import CliRunner
from tw_rent_radar.cli import cli
from tw_rent_radar.db import get_engine, create_tables, Session, upsert_listing


def test_full_workflow(tmp_path):
    """Insert data, then search via CLI."""
    db_path = str(tmp_path / "test.db")
    engine = get_engine(db_path)
    create_tables(engine)

    with Session(engine) as session:
        upsert_listing(session,
            source="591", source_id="111", title="三民區套房",
            price=8000, city="高雄市", district="三民區",
            rooms="1房", type="套房",
            url="https://rent.591.com.tw/111",
        )
        upsert_listing(session,
            source="fcrent", source_id="aaa", title="苓雅兩房",
            price=16000, city="高雄市", district="苓雅區",
            rooms="2房1廳", type="整層住家",
            url="https://fcrent.tw/object/aaa",
        )
        upsert_listing(session,
            source="591", source_id="222", title="台北套房",
            price=12000, city="台北市", district="大安區",
            rooms="1房", type="套房",
            url="https://rent.591.com.tw/222",
        )
        session.commit()

    runner = CliRunner()

    # Search by city — JSON
    result = runner.invoke(cli, ["search", "--city", "高雄市", "--json", "--db", db_path])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 2

    # Search with max price
    result = runner.invoke(cli, ["search", "--max-price", "10000", "--json", "--db", db_path])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["title"] == "三民區套房"

    # Search with fields filter
    result = runner.invoke(cli, ["search", "--json", "--fields", "title,price", "--db", db_path])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 3
    assert set(data[0].keys()) == {"title", "price"}

    # Stats JSON
    result = runner.invoke(cli, ["stats", "--json", "--db", db_path])
    assert result.exit_code == 0
    stats = json.loads(result.output)
    assert stats["total"] == 3

    # Show single listing JSON
    result = runner.invoke(cli, ["show", "1", "--json", "--db", db_path])
    assert result.exit_code == 0

    # Table output (human mode)
    result = runner.invoke(cli, ["search", "--city", "高雄市", "--db", db_path])
    assert result.exit_code == 0
    assert "三民區套房" in result.output


def test_crawl_command_exists():
    """Verify crawl command accepts all sources."""
    runner = CliRunner()
    for source in ["591", "rakuya", "fcrent", "fb_group", "fb_market"]:
        result = runner.invoke(cli, ["crawl", source, "--help"])
        assert result.exit_code == 0
