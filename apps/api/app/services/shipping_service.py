"""
apps/api/app/services/shipping_service.py

Dịch vụ tính toán cước phí và dự kiến thời gian giao hàng (H4CARE Delivery Engine).
Tính toán cước dựa trên khoảng cách Haversine thực tế từ kho dược đến tọa độ giao hàng của khách.
"""

from decimal import Decimal
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models import Warehouse
from app.services.geo_service import calculate_haversine_distance, GeoService


class ShippingService:
    FREE_SHIPPING_THRESHOLD = Decimal("300000.0")  # Đơn hàng >= 300.000đ được miễn phí ship

    @classmethod
    def calculate_shipping(
        cls,
        db: Session,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        province_code: Optional[str] = None,
        district_code: Optional[str] = None,
        order_total: Decimal = Decimal("0.0"),
    ) -> dict[str, Any]:
        """
        Tính toán chi tiết chi phí vận chuyển và kho phụ trách.
        """
        nearest_info = GeoService.find_nearest_warehouses(
            db=db,
            lat=lat,
            lng=lng,
            province_code=province_code,
            district_code=district_code,
        )

        nearest_wh = nearest_info.get("nearest_warehouse")
        if not nearest_wh:
            return {
                "warehouse_id": None,
                "warehouse_code": None,
                "warehouse_name": "Kho trung tâm H4CARE",
                "distance_km": 0.0,
                "base_fee": 25000.0,
                "shipping_fee": 0.0 if order_total >= cls.FREE_SHIPPING_THRESHOLD else 25000.0,
                "is_free_shipping": order_total >= cls.FREE_SHIPPING_THRESHOLD,
                "estimated_delivery": "Dự kiến 24 - 48 giờ (Tiêu chuẩn)",
                "calculation_basis": "Cước chuẩn mặc định (Chưa có tọa độ chính xác)",
            }

        dist = float(nearest_wh["distance_km"])

        # Bậc thang cước phí giao hàng dựa trên khoảng cách km thực tế
        if dist <= 5.0:
            base_fee = 15000.0
            eta = "Dự kiến giao siêu tốc 1 - 2 giờ (Nội thành cùng kho)"
            logic_desc = f"Khoảng cách {dist:.1f} km (Bán kính siêu tốc ≤ 5km - Ước tính đường chim bay)"
        elif dist <= 15.0:
            base_fee = 25000.0
            eta = "Dự kiến giao trong ngày 3 - 6 giờ (Bán kính 5 - 15km)"
            logic_desc = f"Khoảng cách {dist:.1f} km (Khu vực lân cận - Ước tính đường chim bay)"
        elif dist <= 50.0:
            base_fee = 35000.0
            eta = "Dự kiến giao trong 24 giờ (Ngoại thành / Tỉnh lân cận)"
            logic_desc = f"Khoảng cách {dist:.1f} km (Bán kính 15 - 50km - Ước tính đường chim bay)"
        else:
            base_fee = 45000.0
            eta = "Dự kiến giao tiêu chuẩn 24 - 48 giờ (Chuyển phát liên tỉnh)"
            logic_desc = f"Khoảng cách {dist:.1f} km (Liên tỉnh > 50km - Ước tính đường chim bay)"

        is_free = order_total >= cls.FREE_SHIPPING_THRESHOLD
        final_fee = 0.0 if is_free else base_fee

        return {
            "warehouse_id": nearest_wh["warehouse_id"],
            "warehouse_code": nearest_wh["warehouse_code"],
            "warehouse_name": nearest_wh["warehouse_name"],
            "warehouse_address": nearest_wh["warehouse_address"],
            "distance_km": dist,
            "base_fee": base_fee,
            "shipping_fee": final_fee,
            "is_free_shipping": is_free,
            "free_shipping_threshold": float(cls.FREE_SHIPPING_THRESHOLD),
            "estimated_delivery": eta,
            "calculation_basis": logic_desc,
        }
