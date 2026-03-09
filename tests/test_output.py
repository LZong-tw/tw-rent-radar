"""Tests for the output layer."""

import json

from tw_rent_radar.output import format_json, format_table


def _sample_listings():
    return [
        {
            "id": 1,
            "source": "591",
            "source_id": "12345",
            "title": "Cozy Studio",
            "price": 15000,
            "city": "Taipei",
            "district": "Da'an",
            "url": "https://example.com/12345",
        },
        {
            "id": 2,
            "source": "rakuya",
            "source_id": "67890",
            "title": "Spacious 2BR",
            "price": 25000,
            "city": "Taipei",
            "district": "Xinyi",
            "url": "https://example.com/67890",
        },
    ]


def test_json_full_output():
    """JSON output contains all fields for each listing."""
    listings = _sample_listings()
    result = format_json(listings)
    parsed = json.loads(result)
    assert len(parsed) == 2
    assert parsed[0]["title"] == "Cozy Studio"
    assert parsed[1]["price"] == 25000


def test_json_with_fields_filter():
    """JSON output with fields filter only includes specified fields."""
    listings = _sample_listings()
    result = format_json(listings, fields=["title", "price"])
    parsed = json.loads(result)
    assert len(parsed) == 2
    assert set(parsed[0].keys()) == {"title", "price"}
    assert parsed[0]["title"] == "Cozy Studio"
    assert parsed[0]["price"] == 15000


def test_table_output_contains_values():
    """Rich table output contains expected values."""
    listings = _sample_listings()
    result = format_table(listings)
    assert "Cozy Studio" in result
    assert "15000" in result or "15,000" in result
    assert "Spacious 2BR" in result
