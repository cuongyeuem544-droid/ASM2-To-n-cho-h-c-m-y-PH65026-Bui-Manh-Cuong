from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.models import (
    CanonicalProduct,
    InventoryBatch,
    Order,
    OrderItem,
    PaymentTransaction,
    PriceObservation,
    ProductSku,
    User,
    Voucher,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import PublishStatus, RegulatoryStatus, RxOtcStatus, UserRole
from app.services.momo_service import MomoPaymentService


@pytest.fixture
def pricing_seed(database):
    """Thiết lập sản phẩm, kho hàng, tồn kho và các voucher thử nghiệm."""
    with SessionLocal() as db:
        # 1. Kho hàng
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-TEST"))
        if not wh:
            wh = Warehouse(
                code="KHO-HCM-TEST",
                name="Tổng Kho Thử Nghiệm",
                address="123 Nguyễn Huệ, Q1, HCM",
                lat=10.7769,
                lng=106.7009,
                is_active=True,
                is_central=True,
            )
            db.add(wh)
            db.flush()

        # 2. Sản phẩm OTC
        prod = db.scalar(select(CanonicalProduct).where(CanonicalProduct.canonical_name == "Paracetamol Test 500mg"))
        if not prod:
            prod = CanonicalProduct(
                canonical_name="Paracetamol Test 500mg",
                registration_number="VD-TEST-001",
                regulatory_status=RegulatoryStatus.ACTIVE,
                rx_otc_status=RxOtcStatus.OTC,
                publish_status=PublishStatus.PUBLISHED,
                package_description="Hộp 10 vỉ x 10 viên",
            )
            db.add(prod)
            db.flush()

        # 3. Giá quan sát & SKU
        po = db.scalar(select(PriceObservation).where(PriceObservation.product_id == prod.id))
        if not po:
            po = PriceObservation(
                product_id=prod.id,
                source_id=1,
                source_url="https://test.pharmatrust.vn/p/test001",
                observed_price=Decimal("120000.0"),
            )
            db.add(po)

        sku = db.scalar(select(ProductSku).where(ProductSku.canonical_product_id == prod.id))
        if not sku:
            sku = ProductSku(
                canonical_product_id=prod.id,
                sku_code="SKU-PARA-HOP",
                uom="Hộp",
                barcode="8931234567890",
                base_price=Decimal("120000.0"),
                is_default=True,
                is_active=True,
                conversion_rate=1,
            )
            db.add(sku)
            db.flush()

        # 4. Lô hàng & Tồn kho
        batch = db.scalar(select(InventoryBatch).where(InventoryBatch.batch_number == "BATCH-TEST-PRICING"))
        if not batch:
            batch = InventoryBatch(
                sku_id=sku.id,
                batch_number="BATCH-TEST-PRICING",
                manufacture_date=(datetime.now(UTC) - timedelta(days=60)).date(),
                expiry_date=(datetime.now(UTC) + timedelta(days=365)).date(),
                initial_quantity=100,
                status="ACTIVE",
            )
            db.add(batch)
            db.flush()

        stock = db.scalar(select(WarehouseBatchStock).where(WarehouseBatchStock.batch_id == batch.id))
        if not stock:
            stock = WarehouseBatchStock(
                warehouse_id=wh.id,
                batch_id=batch.id,
                quantity_on_hand=100,
                quantity_reserved=0,
                quantity_available=100,
            )
            db.add(stock)

        # 5. Vouchers
        # H4CARENEW: Fixed 20.000đ cho đơn từ 100.000đ
        v_new = db.scalar(select(Voucher).where(Voucher.code == "H4CARENEW"))
        if not v_new:
            v_new = Voucher(
                code="H4CARENEW",
                name="Chào bạn mới",
                discount_type="FIXED",
                discount_value=Decimal("20000.0"),
                min_order_amount=Decimal("100000.0"),
                start_date=datetime.now(UTC) - timedelta(days=1),
                end_date=datetime.now(UTC) + timedelta(days=30),
                usage_limit=1000,
                used_count=0,
                is_active=True,
            )
            db.add(v_new)

        # FREESHIP: Giảm cước 25.000đ cho đơn từ 200.000đ
        v_ship = db.scalar(select(Voucher).where(Voucher.code == "FREESHIP"))
        if not v_ship:
            v_ship = Voucher(
                code="FREESHIP",
                name="Miễn phí vận chuyển",
                discount_type="SHIPPING",
                discount_value=Decimal("25000.0"),
                min_order_amount=Decimal("200000.0"),
                start_date=datetime.now(UTC) - timedelta(days=1),
                end_date=datetime.now(UTC) + timedelta(days=30),
                usage_limit=500,
                used_count=0,
                is_active=True,
            )
            db.add(v_ship)

        # EXPIRED_VOUCHER
        v_exp = db.scalar(select(Voucher).where(Voucher.code == "TEST_EXPIRED"))
        if not v_exp:
            v_exp = Voucher(
                code="TEST_EXPIRED",
                name="Mã đã hết hạn",
                discount_type="FIXED",
                discount_value=Decimal("15000.0"),
                min_order_amount=Decimal("50000.0"),
                start_date=datetime.now(UTC) - timedelta(days=30),
                end_date=datetime.now(UTC) - timedelta(days=1),
                usage_limit=100,
                used_count=0,
                is_active=True,
            )
            db.add(v_exp)

        # EXHAUSTED_VOUCHER
        v_exh = db.scalar(select(Voucher).where(Voucher.code == "TEST_EXHAUSTED"))
        if not v_exh:
            v_exh = Voucher(
                code="TEST_EXHAUSTED",
                name="Mã đã hết lượt",
                discount_type="FIXED",
                discount_value=Decimal("10000.0"),
                min_order_amount=Decimal("50000.0"),
                start_date=datetime.now(UTC) - timedelta(days=1),
                end_date=datetime.now(UTC) + timedelta(days=30),
                usage_limit=5,
                used_count=5,
                is_active=True,
            )
            db.add(v_exh)

        # Buyer User
        buyer = db.scalar(select(User).where(User.email == "buyer_pricing@pharmatrust.vn"))
        if not buyer:
            buyer = User(
                email="buyer_pricing@pharmatrust.vn",
                password_hash=hash_password("Pass@123456"),
                full_name="Nguyễn Văn Test Pricing",
                role=UserRole.CUSTOMER,
                phone="0909999888",
                is_active=True,
                token_version=1,
            )
            db.add(buyer)

        db.commit()
        db.refresh(prod)
        db.refresh(sku)
        db.refresh(buyer)

        prod_id = prod.id
        sku_id = sku.id
        buyer_id = buyer.id

    token = create_access_token(subject=str(buyer_id), role="CUSTOMER", token_version=1)
    return {
        "product_id": prod_id,
        "sku_id": sku_id,
        "buyer_id": buyer_id,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def test_cart_calculate_pricing_and_shipping(client: TestClient, pricing_seed):
    """
    Test tính tiền giỏ hàng từ máy chủ:
    - Subtotal = 120.000đ (1 hộp)
    - Phí ship tiêu chuẩn = 15.000đ (nội thành cùng kho)
    - Grand total = 135.000đ
    """
    res = client.post(
        "/api/v1/store/orders/cart/calculate",
        json={
            "items": [
                {
                    "product_id": pricing_seed["product_id"],
                    "sku_id": pricing_seed["sku_id"],
                    "quantity": 1,
                }
            ],
            "fulfillment_type": "DELIVERY",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["subtotal"] == 120000.0
    assert data["shipping_fee"] == 15000.0
    assert data["discount_amount"] == 0.0
    assert data["grand_total"] == 135000.0


def test_cart_calculate_free_shipping_threshold(client: TestClient, pricing_seed):
    """
    Test miễn phí vận chuyển khi đơn hàng >= 300.000đ (3 hộp = 360.000đ).
    """
    res = client.post(
        "/api/v1/store/orders/cart/calculate",
        json={
            "items": [
                {
                    "product_id": pricing_seed["product_id"],
                    "sku_id": pricing_seed["sku_id"],
                    "quantity": 3,
                }
            ],
            "fulfillment_type": "DELIVERY",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["subtotal"] == 360000.0
    assert data["shipping_fee"] == 0.0
    assert data["grand_total"] == 360000.0


def test_voucher_h4carenew_applied_correctly(client: TestClient, pricing_seed):
    """
    Test áp dụng voucher H4CARENEW (giảm 20.000đ cho đơn >= 100.000đ).
    - Subtotal: 120.000đ
    - Shipping: 15.000đ
    - Discount: 20.000đ
    - Grand total: 115.000đ
    """
    res = client.post(
        "/api/v1/store/orders/cart/calculate",
        json={
            "items": [
                {
                    "product_id": pricing_seed["product_id"],
                    "sku_id": pricing_seed["sku_id"],
                    "quantity": 1,
                }
            ],
            "voucher_code": "H4CARENEW",
            "fulfillment_type": "DELIVERY",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["voucher"]["is_valid"] is True
    assert data["discount_amount"] == 20000.0
    assert data["grand_total"] == 115000.0
    assert data["voucher"]["discount_breakdown"]["applied_discount"] == 20000.0


def test_voucher_expired_rejected(client: TestClient, pricing_seed):
    """
    Test mã voucher TEST_EXPIRED bị từ chối với lý do rõ ràng.
    """
    res = client.post(
        "/api/v1/store/orders/cart/calculate",
        json={
            "items": [
                {
                    "product_id": pricing_seed["product_id"],
                    "sku_id": pricing_seed["sku_id"],
                    "quantity": 1,
                }
            ],
            "voucher_code": "TEST_EXPIRED",
            "fulfillment_type": "DELIVERY",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["voucher"]["is_valid"] is False
    assert "hết hạn" in data["voucher"]["message"]
    assert data["discount_amount"] == 0.0


def test_voucher_min_order_amount_not_met(client: TestClient, pricing_seed):
    """
    Test mã FREESHIP đòi hỏi tối thiểu 200.000đ:
    - Khi đặt 1 hộp (120.000đ) -> không đủ điều kiện áp dụng.
    """
    res = client.post(
        "/api/v1/store/orders/cart/calculate",
        json={
            "items": [
                {
                    "product_id": pricing_seed["product_id"],
                    "sku_id": pricing_seed["sku_id"],
                    "quantity": 1,
                }
            ],
            "voucher_code": "FREESHIP",
            "fulfillment_type": "DELIVERY",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["voucher"]["is_valid"] is False
    assert "chỉ áp dụng cho đơn hàng từ" in data["voucher"]["message"]
    assert data["discount_amount"] == 0.0


def test_voucher_usage_limit_exhausted(client: TestClient, pricing_seed):
    """
    Test mã TEST_EXHAUSTED đã hết lượt sử dụng (5/5).
    """
    res = client.post(
        "/api/v1/store/orders/cart/calculate",
        json={
            "items": [
                {
                    "product_id": pricing_seed["product_id"],
                    "sku_id": pricing_seed["sku_id"],
                    "quantity": 1,
                }
            ],
            "voucher_code": "TEST_EXHAUSTED",
            "fulfillment_type": "DELIVERY",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["voucher"]["is_valid"] is False
    assert "hết số lượt sử dụng" in data["voucher"]["message"]
    assert data["discount_amount"] == 0.0


def test_checkout_ignores_tampered_client_price_and_records_discount(client: TestClient, pricing_seed):
    """
    Test tạo đơn hàng với giá giả mạo từ client (client_unit_price: 1.000đ):
    - Backend phớt lờ hoàn toàn giá 1.000đ, lấy giá 120.000đ từ DB.
    - Áp dụng voucher H4CARENEW giảm 20.000đ.
    - Phí ship 15.000đ (nội thành).
    - Tổng tiền ghi nhận trong DB phải là 115.000đ (chứ không phải 26.000đ hay 45.000đ).
    - Lưu promotion_id, voucher_code, discount_amount, discount_breakdown.
    """
    checkout_payload = {
        "customer_name": "Nguyễn Văn Tamper",
        "customer_phone": "0909999888",
        "customer_email": "tamper@example.com",
        "shipping_address": "123 Lê Duẩn, Bến Nghé, Quận 1, TP.HCM",
        "payment_method": "COD",
        "fulfillment_type": "DELIVERY",
        "is_verified": True,
        "province_code": "79",
        "district_code": "760",
        "commune_code": "26734",
        "ward_code": "26734",
        "lat": 10.7769,
        "lng": 106.7009,
        "voucher_code": "H4CARENEW",
        "idempotency_key": "IDEM-TEST-PRICE-001",
        "items": [
            {
                "product_id": pricing_seed["product_id"],
                "sku_id": pricing_seed["sku_id"],
                "quantity": 1,
                "client_unit_price": 1000.0,  # Cố tình giả mạo giá siêu rẻ
            }
        ],
    }

    res = client.post(
        "/api/v1/store/orders/checkout",
        json=checkout_payload,
        headers=pricing_seed["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["total_amount"] == 115000.0  # Server-calculated!

    # Kiểm tra database
    order_code = data["order_code"]
    with SessionLocal() as db:
        order = db.scalar(select(Order).where(Order.order_code == order_code))
        assert order is not None
        assert order.total_amount == Decimal("115000.0")
        assert order.discount_amount == Decimal("20000.0")
        assert order.voucher_code == "H4CARENEW"
        assert order.promotion_id is not None
        assert order.discount_breakdown is not None
        assert order.discount_breakdown.get("voucher_code") == "H4CARENEW"

        # Kiểm tra item price trong DB
        assert len(order.items) == 1
        assert order.items[0].price == Decimal("120000.0")  # Giá thật từ DB


def test_payment_webhook_amount_mismatch_fails_to_pay(client: TestClient, pricing_seed):
    """
    Test nguyên tắc bảo mật 'Sai một đồng cũng không tự chuyển đơn sang PAID':
    - Đơn hàng có tổng tiền 115.000đ.
    - Webhook IPN gửi số tiền thanh toán là 100.000đ hoặc 114.999đ.
    - Hệ thống đánh dấu giao dịch là UNDERPAID và KHÔNG chuyển trạng thái đơn sang PAID.
    """
    # 1. Tạo đơn hàng
    checkout_payload = {
        "customer_name": "Nguyễn Văn Underpaid",
        "customer_phone": "0909999888",
        "shipping_address": "123 Lê Duẩn, Bến Nghé, Quận 1, TP.HCM",
        "payment_method": "MOMO",
        "fulfillment_type": "DELIVERY",
        "is_verified": True,
        "province_code": "79",
        "district_code": "760",
        "commune_code": "26734",
        "ward_code": "26734",
        "lat": 10.7769,
        "lng": 106.7009,
        "voucher_code": "H4CARENEW",
        "items": [
            {
                "product_id": pricing_seed["product_id"],
                "sku_id": pricing_seed["sku_id"],
                "quantity": 1,
            }
        ],
    }

    res = client.post(
        "/api/v1/store/orders/checkout",
        json=checkout_payload,
        headers=pricing_seed["headers"],
    )
    assert res.status_code == 200
    order_code = res.json()["order_code"]

    with SessionLocal() as db:
        order = db.scalar(select(Order).where(Order.order_code == order_code))
        assert order.total_amount == Decimal("115000.0")
        order_id = order.id

    # 2. Xử lý IPN với số tiền thiếu: 100.000đ (thay vì 115.000đ)
    ipn_data = {
        "partnerCode": "MOMO",
        "orderId": order_code,
        "requestId": f"REQ-{order_code}",
        "amount": 100000,  # Sai lệch số tiền so với 115.000đ
        "orderInfo": f"Thanh toán đơn {order_code}",
        "orderType": "momo_wallet",
        "transId": 9988776655,
        "resultCode": 0,
        "message": "Successful.",
        "payType": "qr",
        "responseTime": int(datetime.now(UTC).timestamp() * 1000),
        "extraData": "",
        "signature": "mock_sig_for_test",
    }

    from unittest.mock import patch
    from fastapi import HTTPException

    with patch.object(MomoPaymentService, "verify_ipn_signature", return_value=True):
        with SessionLocal() as db:
            with pytest.raises(HTTPException) as exc_info:
                MomoPaymentService.process_ipn_callback(db=db, payload=ipn_data)
            assert exc_info.value.status_code == 400
            assert "không khớp" in str(exc_info.value.detail)

            # Kiểm tra order và transaction trong DB
            db_order = db.scalar(select(Order).where(Order.order_code == order_code))
            assert db_order.payment_status != "PAID"
            assert db_order.order_status == "PENDING"  # Vẫn PENDING, không tự ý PAID
            trans = db.scalar(select(PaymentTransaction).where(PaymentTransaction.order_id == db_order.id))
            assert trans.status == "UNDERPAID"
