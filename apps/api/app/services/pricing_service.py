from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CanonicalProduct,
    PriceObservation,
    ProductSku,
    Voucher,
)
from app.models.enums import PublishStatus
from app.services.product_eligibility_service import ProductEligibilityService
from app.services.shipping_service import ShippingService

logger = logging.getLogger("pharmatrust.pricing")


def utcnow() -> datetime:
    return datetime.now(UTC)


class PricingService:
    """
    Dịch vụ tính giá niêm yết, tính cước vận chuyển, và thẩm định mã giảm giá (Voucher Engine).
    Tuyệt đối không tin tưởng giá tiền hoặc chiết khấu gửi lên từ Client.
    """

    @classmethod
    def validate_voucher(
        cls,
        db: Session,
        voucher_code: str,
        subtotal: Decimal,
        shipping_fee: Decimal,
    ) -> dict[str, Any]:
        """
        Kiểm tra và tính số tiền giảm giá của voucher.
        Nếu không hợp lệ, trả về valid=False kèm lý do cụ thể.
        """
        clean_code = voucher_code.strip().upper()
        voucher = db.scalar(select(Voucher).where(Voucher.code == clean_code))

        if not voucher:
            return {
                "valid": False,
                "voucher": None,
                "discount_amount": Decimal("0.0"),
                "message": f"Mã giảm giá '{clean_code}' không tồn tại.",
            }

        if not voucher.is_active:
            return {
                "valid": False,
                "voucher": voucher,
                "discount_amount": Decimal("0.0"),
                "message": f"Mã giảm giá '{clean_code}' hiện đang tạm ngừng áp dụng.",
            }

        now = utcnow()
        if voucher.start_date:
            s_date = voucher.start_date if voucher.start_date.tzinfo else voucher.start_date.replace(tzinfo=UTC)
            if now < s_date:
                return {
                    "valid": False,
                    "voucher": voucher,
                    "discount_amount": Decimal("0.0"),
                    "message": f"Mã giảm giá '{clean_code}' chưa đến thời gian áp dụng.",
                }

        if voucher.end_date:
            e_date = voucher.end_date if voucher.end_date.tzinfo else voucher.end_date.replace(tzinfo=UTC)
            if now > e_date:
                return {
                    "valid": False,
                    "voucher": voucher,
                    "discount_amount": Decimal("0.0"),
                    "message": f"Mã giảm giá '{clean_code}' đã hết hạn sử dụng.",
                }

        if voucher.usage_limit is not None and voucher.used_count >= voucher.usage_limit:
            return {
                "valid": False,
                "voucher": voucher,
                "discount_amount": Decimal("0.0"),
                "message": f"Mã giảm giá '{clean_code}' đã hết số lượt sử dụng ({voucher.used_count}/{voucher.usage_limit}).",
            }

        if subtotal < voucher.min_order_amount:
            return {
                "valid": False,
                "voucher": voucher,
                "discount_amount": Decimal("0.0"),
                "message": (
                    f"Mã '{clean_code}' chỉ áp dụng cho đơn hàng từ "
                    f"{int(voucher.min_order_amount):,} đ trở lên (hiện tại: {int(subtotal):,} đ)."
                ),
            }

        discount = Decimal("0.0")
        dtype = (voucher.discount_type or "FIXED").upper()

        if dtype == "FIXED":
            discount = min(voucher.discount_value, subtotal)
        elif dtype == "PERCENT":
            raw_discount = (subtotal * voucher.discount_value) / Decimal("100.0")
            if voucher.max_discount_amount and voucher.max_discount_amount > 0:
                raw_discount = min(raw_discount, voucher.max_discount_amount)
            discount = min(raw_discount, subtotal)
        elif dtype == "SHIPPING":
            discount = min(voucher.discount_value, shipping_fee)
        else:
            discount = min(voucher.discount_value, subtotal)

        breakdown = {
            "voucher_id": voucher.id,
            "voucher_code": voucher.code,
            "voucher_name": voucher.name,
            "discount_type": voucher.discount_type,
            "discount_value": float(voucher.discount_value),
            "max_discount_amount": float(voucher.max_discount_amount) if voucher.max_discount_amount else None,
            "min_order_amount": float(voucher.min_order_amount),
            "applied_discount": float(discount),
        }

        return {
            "valid": True,
            "voucher": voucher,
            "discount_amount": discount,
            "discount_breakdown": breakdown,
            "message": f"Áp dụng thành công mã '{clean_code}'. Tiết kiệm {int(discount):,} đ.",
        }

    @classmethod
    def calculate_cart_pricing(
        cls,
        db: Session,
        items: list[dict[str, Any]],
        voucher_code: Optional[str] = None,
        fulfillment_type: str = "DELIVERY",
        province_code: Optional[str] = None,
        district_code: Optional[str] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> dict[str, Any]:
        """
        Thực hiện toàn bộ nghiệp vụ tính giá cho giỏ hàng / đơn hàng:
        1. Thẩm định tính mở bán và tồn kho từng SKU.
        2. Tải đơn giá chính thức từ DB.
        3. Tính subtotal.
        4. Tính phí ship (miễn phí nếu đơn >= 300k hoặc nhận tại quầy).
        5. Áp dụng voucher (nếu có) và tính discount.
        6. Tính grand_total.
        """
        product_ids = [it["product_id"] for it in items if "product_id" in it]
        products = db.scalars(select(CanonicalProduct).where(CanonicalProduct.id.in_(product_ids))).all()
        products_map = {p.id: p for p in products}

        calculated_items = []
        subtotal = Decimal("0.0")
        all_eligible = True

        for it in items:
            pid = it.get("product_id")
            sku_id = it.get("sku_id")
            qty = int(it.get("quantity", 1))

            prod = products_map.get(pid)
            if not prod or prod.publish_status != PublishStatus.PUBLISHED:
                all_eligible = False
                calculated_items.append({
                    "product_id": pid,
                    "sku_id": sku_id,
                    "product_name": prod.canonical_name if prod else f"Sản phẩm #{pid}",
                    "uom": "Hộp",
                    "unit_price": 0.0,
                    "quantity": qty,
                    "subtotal": 0.0,
                    "available_stock": 0,
                    "can_checkout": False,
                    "rejection_reason": "Sản phẩm không tồn tại hoặc đã ngừng kinh doanh.",
                })
                continue

            eligibility = ProductEligibilityService.evaluate_product_eligibility(prod, db)
            sku_obj = None
            if sku_id:
                sku_obj = db.get(ProductSku, sku_id)
            if not sku_obj:
                sku_obj = (
                    db.query(ProductSku)
                    .filter(
                        ProductSku.canonical_product_id == prod.id,
                        ProductSku.is_active == True,
                    )
                    .order_by(ProductSku.is_default.desc())
                    .first()
                )

            server_price = Decimal("0.0")
            if sku_obj and sku_obj.base_price and sku_obj.base_price > 0:
                server_price = Decimal(str(sku_obj.base_price))
            else:
                po = db.query(PriceObservation.observed_price).filter(PriceObservation.product_id == prod.id).first()
                if po and po[0]:
                    server_price = Decimal(str(po[0]))

            uom = sku_obj.uom if sku_obj else (prod.package_description or "Hộp")
            available_stock = eligibility.available_stock

            can_checkout = (
                eligibility.can_add_to_cart
                and server_price > 0
                and available_stock >= qty
            )

            rejection = None
            if not eligibility.can_add_to_cart:
                rejection = eligibility.primary_reason
            elif server_price <= 0:
                rejection = "Sản phẩm chưa có giá niêm yết thương mại."
            elif available_stock < qty:
                rejection = f"Chỉ còn {available_stock} {uom} trong kho (bạn đặt {qty})."

            item_subtotal = server_price * qty if can_checkout else Decimal("0.0")
            if can_checkout:
                subtotal += item_subtotal
            else:
                all_eligible = False

            calculated_items.append({
                "product_id": prod.id,
                "sku_id": sku_obj.id if sku_obj else sku_id,
                "sku_code": sku_obj.sku_code if sku_obj else None,
                "product_name": prod.canonical_name,
                "uom": uom,
                "unit_price": float(server_price),
                "quantity": qty,
                "subtotal": float(item_subtotal),
                "available_stock": available_stock,
                "can_checkout": can_checkout,
                "rejection_reason": rejection,
            })

        # Phí giao hàng
        is_store_pickup = (fulfillment_type or "").upper() == "STORE_PICKUP"
        if is_store_pickup or subtotal == 0:
            shipping_fee = Decimal("0.0")
            shipping_info = {
                "shipping_fee": 0.0,
                "is_free_shipping": True,
                "calculation_basis": "Nhận tại quầy thuốc (Miễn cước)",
            }
        else:
            ship_res = ShippingService.calculate_shipping(
                db=db,
                lat=lat,
                lng=lng,
                province_code=province_code,
                district_code=district_code,
                order_total=subtotal,
            )
            shipping_fee = Decimal(str(ship_res.get("shipping_fee", 25000.0)))
            shipping_info = ship_res

        # Voucher
        discount_amount = Decimal("0.0")
        voucher_result = None
        voucher_obj = None

        if voucher_code and voucher_code.strip():
            v_res = cls.validate_voucher(
                db=db,
                voucher_code=voucher_code,
                subtotal=subtotal,
                shipping_fee=shipping_fee,
            )
            voucher_result = {
                "code": voucher_code.strip().upper(),
                "is_valid": v_res["valid"],
                "message": v_res["message"],
                "discount_amount": float(v_res["discount_amount"]),
                "discount_breakdown": v_res.get("discount_breakdown"),
            }
            if v_res["valid"]:
                discount_amount = v_res["discount_amount"]
                voucher_obj = v_res["voucher"]

        grand_total = max(Decimal("0.0"), subtotal + shipping_fee - discount_amount)

        return {
            "all_eligible": all_eligible,
            "items": calculated_items,
            "subtotal": float(subtotal),
            "shipping_fee": float(shipping_fee),
            "shipping_info": shipping_info,
            "discount_amount": float(discount_amount),
            "grand_total": float(grand_total),
            "voucher": voucher_result,
            "_voucher_obj": voucher_obj,  # Internal for checkout mutation
        }
