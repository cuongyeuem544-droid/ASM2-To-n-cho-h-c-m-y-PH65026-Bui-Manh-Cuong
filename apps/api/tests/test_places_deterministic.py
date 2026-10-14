import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.places_service import PlacesService


@pytest.mark.asyncio
async def test_curated_poi_search_without_network():
    """Kiểm tra tìm kiếm POI trọng điểm quốc gia ngay cả khi mạng ngoài ngắt kết nối."""
    PlacesService.clear_caches()
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Network offline")):
        results = await PlacesService.autocomplete_places("FPT Polytechnic", limit=5)
        assert len(results) >= 2, "Phải tìm thấy ít nhất 2 cơ sở FPT Polytechnic từ Curated POIs"
        for r in results:
            if "fpt" in r["name"].lower():
                assert r["provider"] == "curated_national_poi"
                assert r["verified"] is True
                assert r["province_code"] in ["01", "79", "48"]
                assert r["commune_code"] is not None


@pytest.mark.asyncio
async def test_autocomplete_cache_hit():
    """Kiểm tra TTL Cache: Lần gọi thứ 2 phải trả về từ bộ nhớ đệm, không gọi mạng ngoài."""
    PlacesService.clear_caches()
    mock_get = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {"features": []}))
    with patch("httpx.AsyncClient.get", mock_get):
        res1 = await PlacesService.autocomplete_places("Bệnh viện Bạch Mai", limit=5)
        assert len(res1) >= 1
        initial_call_count = mock_get.call_count

        # Lần gọi thứ 2 với cùng tham số
        res2 = await PlacesService.autocomplete_places("Bệnh viện Bạch Mai", limit=5)
        assert len(res2) == len(res1)
        assert res2[0]["place_id"] == res1[0]["place_id"]
        # Số lần gọi mạng không tăng vì đã hit cache
        assert mock_get.call_count == initial_call_count


@pytest.mark.asyncio
async def test_photon_timeout_fallback():
    """Kiểm tra xử lý timeout mượt mà: khi Photon timeout, fallback sang Curated POI / Admin data."""
    PlacesService.clear_caches()
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Read timeout")):
        results = await PlacesService.autocomplete_places("72 Trần Duy Hưng", limit=5)
        assert len(results) >= 1
        assert any("Trần Duy Hưng" in r["name"] or "Trần Duy Hưng" in r.get("formatted_address", "") for r in results)


@pytest.mark.asyncio
async def test_photon_rate_limit_429_fallback():
    """Kiểm tra Photon trả về HTTP 429 Too Many Requests không gây lỗi hệ thống (không crash 500)."""
    PlacesService.clear_caches()
    mock_resp = MagicMock(status_code=429, text="Too Many Requests")
    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        results = await PlacesService.autocomplete_places("Keangnam", limit=5)
        assert len(results) >= 1
        assert any("Landmark" in r["name"] or "Keangnam" in r["name"] for r in results)


@pytest.mark.asyncio
async def test_reverse_geocode_cache_hit():
    """Kiểm tra reverse geocode cache hit cho cùng một tọa độ GPS."""
    PlacesService.clear_caches()
    mock_get = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {"features": []}))
    with patch("httpx.AsyncClient.get", mock_get):
        res1 = await PlacesService.reverse_geocode(21.0169, 105.7841)
        assert res1 is not None
        assert res1["lat"] == 21.0169
        initial_call_count = mock_get.call_count

        res2 = await PlacesService.reverse_geocode(21.0169, 105.7841)
        assert res2["place_id"] == res1["place_id"]
        assert mock_get.call_count == initial_call_count


@pytest.mark.asyncio
async def test_reverse_geocode_network_down_fallback():
    """Kiểm tra reverse geocode fallback về internal bounding box khi mạng sập hoàn toàn."""
    PlacesService.clear_caches()
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("No internet")):
        # Tọa độ tại trung tâm Hà Nội (Hồ Gươm)
        res = await PlacesService.reverse_geocode(21.0285, 105.8542)
        assert res is not None
        assert res["provider"] == "internal_bbox"
        assert res["province_code"] == "01"
        assert res["province_name"] == "Thành phố Hà Nội"
        assert res["is_verified"] is True


@pytest.mark.asyncio
async def test_junk_query_filtered():
    """Kiểm tra các query rác hoặc quá ngắn bị lọc bỏ và trả về danh sách rỗng."""
    assert await PlacesService.autocomplete_places("a") == []
    assert await PlacesService.autocomplete_places("tt") == []
    assert await PlacesService.autocomplete_places("abc") == []
    assert await PlacesService.autocomplete_places("123 test") == []
    assert await PlacesService.autocomplete_places("zzzzxyqwerty987") == []


def test_provider_status_reporting():
    """Kiểm tra báo cáo trạng thái Geocoding Provider theo yêu cầu đặc tả."""
    status = PlacesService.get_provider_status()
    assert "google_configured" in status
    assert "active_provider" in status
    assert "fallback_provider" in status
    assert "report" in status
    assert "FALLBACK: OpenStreetMap" in status["report"] or "GOOGLE PLACES: CONFIGURED" in status["report"]
