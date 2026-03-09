"""Tests for the fcrent crawler — uses mock HTML, no live requests."""

from __future__ import annotations

import json

from tw_rent_radar.crawlers.fcrent import FcrentCrawler

SAMPLE_NEXT_DATA = {
    "props": {
        "pageProps": {
            "object": {
                "name": {"zhTW": "可補助|近衛武營2房1廳"},
                "rent": "16000",
                "city": "city-id-1",
                "district": "dist-id-1",
                "type": "type-id-1",
                "layout": "layout-id-1",
                "ping": "20",
                "pattern": "2房1廳2衛",
                "floor": "2F/5F",
                "coordinator": "coord-id-1",
                "picture": ["img1.jpg", "img2.jpg"],
                "contents": {"zhTW": [{"data": {"html": "<p>近捷運、近輕軌</p>"}}]},
                "facility": ["fac-id-1", "fac-id-2"],
                "others": ["other-id-1"],
            },
            "city": [{"id": "city-id-1", "name": {"zhTW": "高雄市"}}],
            "district": [
                {
                    "id": "dist-id-1",
                    "name": {"zhTW": "苓雅區"},
                    "city": "city-id-1",
                }
            ],
            "type": [{"id": "type-id-1", "name": {"zhTW": "公寓(無電梯)"}}],
            "layout": [{"id": "layout-id-1", "name": {"zhTW": "整層住家"}}],
            "coordinators": [
                {
                    "id": "coord-id-1",
                    "name": {"zhTW": "許小姐"},
                    "phone": "0985-583-670",
                }
            ],
            "facilities": [
                {"id": "fac-id-1", "name": {"zhTW": "冰箱"}},
                {"id": "fac-id-2", "name": {"zhTW": "洗衣機"}},
            ],
            "others": [{"id": "other-id-1", "name": {"zhTW": "近捷運"}}],
        }
    },
    "query": {"id": "YFDIpopHGnXUMhbccoBa"},
}


def _make_html(next_data: dict | None = None) -> str:
    """Build a minimal HTML page with an optional __NEXT_DATA__ script tag."""
    body = "<html><head>"
    if next_data is not None:
        payload = json.dumps(next_data, ensure_ascii=False)
        body += f'<script id="__NEXT_DATA__" type="application/json">{payload}</script>'
    body += "</head><body></body></html>"
    return body


class TestParseNextData:
    """Tests for FcrentCrawler.parse_listing_page."""

    def test_parse_next_data(self):
        """Parsing a page with valid __NEXT_DATA__ returns a correct dict."""
        html = _make_html(SAMPLE_NEXT_DATA)
        crawler = FcrentCrawler()
        result = crawler.parse_listing_page(html)

        assert result is not None
        assert result["source"] == "fcrent"
        assert result["source_id"] == "YFDIpopHGnXUMhbccoBa"
        assert result["title"] == "可補助|近衛武營2房1廳"
        assert result["price"] == 16000
        assert result["city"] == "高雄市"
        assert result["district"] == "苓雅區"
        assert result["address"] == "高雄市苓雅區"
        assert result["size"] == 20.0
        assert result["rooms"] == "2房1廳2衛"
        assert result["type"] == "整層住家"
        assert result["floor"] == "2F/5F"
        assert result["contact"] == "許小姐"
        assert result["phone"] == "0985-583-670"
        assert result["url"] == "https://fcrent.tw/object/YFDIpopHGnXUMhbccoBa"

        # Description is extracted from rich text and includes "others"
        assert "近捷運" in result["description"]
        assert "近輕軌" in result["description"]

        # images and amenities are stored as JSON strings
        images = json.loads(result["images"])
        assert images == ["img1.jpg", "img2.jpg"]

        amenities = json.loads(result["amenities"])
        assert "冰箱" in amenities
        assert "洗衣機" in amenities

        # raw_data preserves the original object
        raw = json.loads(result["raw_data"])
        assert raw["rent"] == "16000"
        assert raw["name"]["zhTW"] == "可補助|近衛武營2房1廳"

    def test_parse_next_data_missing(self):
        """HTML without __NEXT_DATA__ returns None."""
        html = _make_html()  # no next_data
        crawler = FcrentCrawler()
        result = crawler.parse_listing_page(html)
        assert result is None

    def test_parse_next_data_missing_object(self):
        """__NEXT_DATA__ present but without props.pageProps.object returns None."""
        html = _make_html({"props": {"pageProps": {}}})
        crawler = FcrentCrawler()
        result = crawler.parse_listing_page(html)
        assert result is None

    def test_parse_next_data_invalid_json(self):
        """Malformed JSON inside __NEXT_DATA__ returns None."""
        html = (
            "<html><head>"
            '<script id="__NEXT_DATA__" type="application/json">'
            "{not valid json}"
            "</script>"
            "</head><body></body></html>"
        )
        crawler = FcrentCrawler()
        result = crawler.parse_listing_page(html)
        assert result is None
