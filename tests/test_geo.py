"""Tests for the geocoding module."""

from unittest.mock import patch

from tw_rent_radar.geo import geocode, get_config, haversine_km


class TestHaversine:
    def test_same_point(self):
        assert haversine_km(25.033, 121.565, 25.033, 121.565) == 0.0

    def test_taipei_to_kaohsiung(self):
        dist = haversine_km(25.033, 121.565, 22.627, 120.301)
        assert 280 < dist < 310

    def test_short_distance(self):
        dist = haversine_km(22.6125, 120.3056, 22.6186, 120.3187)
        assert 0.5 < dist < 3.0


class TestGeocode:
    def test_tgos_success(self):
        mock_xml = '<?xml version="1.0" encoding="utf-8"?><string xmlns="http://tempuri.org/">{"Info":[{"IsSuccess":"True","OutTotal":"1"}],"AddressList":[{"X":120.3014,"Y":22.6273,"FULL_ADDR":"高雄市前鎮區復興四路2號"}]}</string>'
        with patch("tw_rent_radar.geo._tgos_request") as mock_tgos:
            mock_tgos.return_value = mock_xml
            result = geocode("高雄市前鎮區復興四路2號", tgos_app_id="test", tgos_api_key="test")
            assert result is not None
            lat, lng = result
            assert abs(lat - 22.6273) < 0.001
            assert abs(lng - 120.3014) < 0.001

    def test_tgos_fail_google_fallback(self):
        mock_google_json = {
            "status": "OK",
            "results": [{"geometry": {"location": {"lat": 22.6125, "lng": 120.3056}}}],
        }
        with (
            patch("tw_rent_radar.geo._tgos_request", side_effect=Exception("TGOS down")),
            patch("tw_rent_radar.geo._google_request") as mock_google,
        ):
            mock_google.return_value = mock_google_json
            result = geocode(
                "高雄軟體園區",
                tgos_app_id="test",
                tgos_api_key="test",
                google_api_key="test",
            )
            assert result is not None
            lat, lng = result
            assert abs(lat - 22.6125) < 0.01

    def test_both_fail_returns_none(self):
        with (
            patch("tw_rent_radar.geo._tgos_request", side_effect=Exception("TGOS down")),
            patch("tw_rent_radar.geo._google_request", side_effect=Exception("Google down")),
        ):
            result = geocode("invalid", tgos_app_id="t", tgos_api_key="t", google_api_key="g")
            assert result is None

    def test_no_keys_returns_none(self):
        result = geocode("高雄市前鎮區")
        assert result is None


class TestGetConfig:
    def test_empty_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tw_rent_radar.geo.CONFIG_PATH", tmp_path / "config.json")
        config = get_config()
        assert config == {}

    def test_loads_config(self, tmp_path, monkeypatch):
        import json

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"tgos_app_id": "abc"}))
        monkeypatch.setattr("tw_rent_radar.geo.CONFIG_PATH", config_file)
        config = get_config()
        assert config["tgos_app_id"] == "abc"
