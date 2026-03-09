"""Tests for the fcrent crawler — uses mock HTML, no live requests."""
from __future__ import annotations

import json

from tw_rent_radar.crawlers.fcrent import FcrentCrawler

SAMPLE_NEXT_DATA = {
    "props": {
        "pageProps": {
            "object": {
                "id": "YFDIpopHGnXUMhbccoBa",
                "title": "可補助|近衛武營2房1廳",
                "price": 16000,
                "city": "高雄市",
                "district": "苓雅區",
                "address": "高雄市苓雅區",
                "size": 20,
                "rooms": "2房1廳2衛",
                "type": "整層住家",
                "floor": "2F/5F",
                "contact": "許小姐",
                "phone": "0985-583-670",
                "images": ["https://example.com/img1.jpg"],
                "description": "近捷運、近輕軌",
                "amenities": ["冰箱", "洗衣機", "電視", "冷氣"],
            }
        }
    }
}


def _make_html(next_data: dict | None = None) -> str:
    """Build a minimal HTML page with an optional __NEXT_DATA__ script tag."""
    body = "<html><head>"
    if next_data is not None:
        payload = json.dumps(next_data, ensure_ascii=False)
        body += (
            f'<script id="__NEXT_DATA__" type="application/json">'
            f"{payload}</script>"
        )
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
        assert result["size"] == 20
        assert result["rooms"] == "2房1廳2衛"
        assert result["type"] == "整層住家"
        assert result["floor"] == "2F/5F"
        assert result["contact"] == "許小姐"
        assert result["phone"] == "0985-583-670"
        assert result["url"] == "https://fcrent.tw/object/YFDIpopHGnXUMhbccoBa"
        assert result["description"] == "近捷運、近輕軌"

        # images and amenities are stored as JSON strings
        assert json.loads(result["images"]) == ["https://example.com/img1.jpg"]
        assert json.loads(result["amenities"]) == ["冰箱", "洗衣機", "電視", "冷氣"]

        # raw_data preserves the original object
        raw = json.loads(result["raw_data"])
        assert raw["id"] == "YFDIpopHGnXUMhbccoBa"

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
            '<html><head>'
            '<script id="__NEXT_DATA__" type="application/json">'
            '{not valid json}'
            '</script>'
            '</head><body></body></html>'
        )
        crawler = FcrentCrawler()
        result = crawler.parse_listing_page(html)
        assert result is None
