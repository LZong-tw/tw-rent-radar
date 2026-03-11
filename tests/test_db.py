"""Tests for the database layer."""

from sqlalchemy.orm import Session

from tw_rent_radar.db import CONFIG_DIR, Listing, create_tables, get_engine, upsert_listing


def test_create_and_insert(tmp_path):
    """Create tables and insert a listing."""
    db_path = tmp_path / "test.db"
    engine = get_engine(str(db_path))
    create_tables(engine)

    with Session(engine) as session:
        upsert_listing(
            session,
            source="591",
            source_id="12345",
            title="Test Apartment",
            price=15000,
            city="Taipei",
            district="Da'an",
            url="https://example.com/12345",
        )

    with Session(engine) as session:
        listing = session.query(Listing).one()
        assert listing.source == "591"
        assert listing.source_id == "12345"
        assert listing.title == "Test Apartment"
        assert listing.price == 15000
        assert listing.city == "Taipei"
        assert listing.url == "https://example.com/12345"
        assert listing.created_at is not None


def test_upsert_deduplicates(tmp_path):
    """Upsert updates existing listing instead of duplicating."""
    db_path = tmp_path / "test.db"
    engine = get_engine(str(db_path))
    create_tables(engine)

    with Session(engine) as session:
        upsert_listing(
            session,
            source="591",
            source_id="12345",
            title="Old Title",
            price=15000,
        )

    with Session(engine) as session:
        upsert_listing(
            session,
            source="591",
            source_id="12345",
            title="New Title",
            price=18000,
        )

    with Session(engine) as session:
        listings = session.query(Listing).all()
        assert len(listings) == 1
        assert listings[0].title == "New Title"
        assert listings[0].price == 18000


def test_get_engine_default_uses_home_dir(monkeypatch, tmp_path):
    """get_engine with no args defaults to ~/.tw-rent-radar/radar.db.

    Previously it used ~/.tw-rent-radar/radar.db — now it uses CWD/radar.db.
    """
    fake_cwd = tmp_path / "fakecwd"
    fake_cwd.mkdir()
    monkeypatch.setattr("tw_rent_radar.db.DEFAULT_DB_PATH", str(fake_cwd / "radar.db"))
    engine = get_engine()
    create_tables(engine)

    with Session(engine) as session:
        upsert_listing(session, source="591", source_id="test1", title="Test")

    assert (fake_cwd / "radar.db").exists()


def test_get_engine_explicit_path(tmp_path):
    """get_engine with an explicit path creates the DB at that exact location."""
    db_path = tmp_path / "subdir" / "custom.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = get_engine(str(db_path))
    create_tables(engine)

    with Session(engine) as session:
        upsert_listing(session, source="591", source_id="abs1", title="Absolute")

    assert db_path.exists()


def test_config_dir_points_to_home():
    """CONFIG_DIR should be under the user's home directory."""
    from pathlib import Path

    assert CONFIG_DIR == Path.home() / ".tw-rent-radar"


def test_listing_has_geo_and_detail_columns(tmp_path):
    """Listing model has latitude, longitude, cooking, gas_type columns."""
    db_path = tmp_path / "test.db"
    engine = get_engine(str(db_path))
    create_tables(engine)

    with Session(engine) as session:
        upsert_listing(
            session,
            source="591",
            source_id="geo1",
            title="Test",
            latitude=22.6273,
            longitude=120.3014,
            cooking="可開伙",
            gas_type="天然瓦斯",
        )

    with Session(engine) as session:
        listing = session.query(Listing).one()
        assert listing.latitude == 22.6273
        assert listing.longitude == 120.3014
        assert listing.cooking == "可開伙"
        assert listing.gas_type == "天然瓦斯"


def test_to_dict_includes_new_columns(tmp_path):
    """to_dict includes latitude, longitude, cooking, gas_type."""
    db_path = tmp_path / "test.db"
    engine = get_engine(str(db_path))
    create_tables(engine)

    with Session(engine) as session:
        upsert_listing(
            session,
            source="591",
            source_id="dict1",
            title="Test",
            latitude=25.033,
            longitude=121.565,
            cooking="不可開伙",
            gas_type="桶裝瓦斯",
        )

    with Session(engine) as session:
        listing = session.query(Listing).one()
        d = listing.to_dict()
        assert d["latitude"] == 25.033
        assert d["longitude"] == 121.565
        assert d["cooking"] == "不可開伙"
        assert d["gas_type"] == "桶裝瓦斯"
