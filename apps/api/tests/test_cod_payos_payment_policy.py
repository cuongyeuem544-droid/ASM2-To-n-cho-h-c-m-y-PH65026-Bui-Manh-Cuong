import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

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
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import PublishStatus, RegulatoryStatus, RxOtcStatus, UserRole


@pytest.fixture(scope="module")
def setup_test_data():
    db = SessionLocal()

    # 1. User
    user = db.query(User).filter(User.email == "policy_buyer@h4care.vn").first()
    if not user:
        user = User(
            email="policy_buyer@h4care.vn",
            password_hash=hash_password("PolicyPass123!"),
            full_name="Khách Hàng Chính Sách",
            phone="0988776655",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # 2. Warehouse
    wh = db.query(Warehouse).filter(Warehouse.is_active.is_(True)).first()
    if not wh:
        wh = Warehouse(
            code="WH-POL-01",
            name="Kho Dược Chính Sách",
            address="123 Phố Huế, Hai Bà Trưng, Hà Nội",
            province="Hà Nội",
            district="Hai Bà Trưng",
            lat=21.0285,
            lng=105.8542,
            is_active=True,
            is_central=True,
        )
        db.add(wh)
        db.commit()
        db.refresh(wh)

    # 3. Product & SKU
    prod_id = 9988
    prod = db.query(CanonicalProduct).filter(CanonicalProduct.id == prod_id).first()
    if not prod:
        prod = CanonicalProduct(
            id=prod_id,
            canonical_name="Thuốc Kháng Sinh H4Care 500mg",
            registration_number="VD-9988-26",
            regulatory_status=RegulatoryStatus.ACTIVE,
            rx_otc_status=RxOtcStatus.OTC,
            publish_status=PublishStatus.PUBLISHED,
            publish_mode="SALE_ELIGIBLE",
        )
        db.add(prod)
        db.commit()
        db.refresh(prod)

    sku = db.query(ProductSku).filter(ProductSku.canonical_product_id == prod_id).first()
    if not sku:
        sku = ProductSku(
            canonical_product_id=prod_id,
            sku_code="SKU-POL-9988",
            base_price=Decimal("75000.0"),
            is_default=True,
            is_active=True,
            uom="Hộp",
        )
        db.add(sku)
        db.commit()
        db.refresh(sku)

    # 4. Price observation
    obs = db.query(PriceObservation).filter(PriceObservation.product_id == prod_id).first()
    if not obs:
        obs = PriceObservation(
            product_id=prod_id,
            source_id=1,
            source_url="https://example.com/pol/9988",
            observed_price=Decimal("75000.0"),
        )
        db.add(obs)
        db.commit()

    # 5. Batch & stock
    batch = db.query(InventoryBatch).filter(InventoryBatch.batch_number == "LOT-POL-9988").first()
    if not batch:
        batch = InventoryBatch(
            sku_id=sku.id,
            batch_number="LOT-POL-9988",
            expiry_date=date.today() + timedelta(days=365),
            initial_quantity=1000,
            status="ACTIVE",
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)

    stock = db.query(WarehouseBatchStock).filter(
        WarehouseBatchStock.warehouse_id == wh.id,
        WarehouseBatchStock.batch_id == batch.id,
    ).first()
    if not stock:
        stock = WarehouseBatchStock(
            warehouse_id=wh.id,
            batch_id=batch.id,
            quantity_on_hand=1000,
            quantity_available=1000,
            quantity_reserved=0,
        )
        db.add(stock)
        db.commit()
    else:
        stock.quantity_available = 1000
        stock.quantity_on_hand = 1000
        stock.quantity_reserved = 0
        db.commit()

    res = {
        "user_id": user.id,
        "phone": user.phone,
        "wh_id": wh.id,
        "product_id": prod.id,
        "sku_id": sku.id,
        "sku_code": sku.sku_code,
    }
    db.close()
    return res


def _create_db_order(db, user_id, order_code, product_id, sku_code, payment_method="PAYOS", status="PENDING", payment_status="UNPAID", amount=150000):
    order = Order(
        order_code=order_code,
        user_id=user_id,
        customer_name="Khách Hàng Test",
        customer_phone="0988776655",
        shipping_address="123 Phố Huế, Hà Nội",
        shipping_city="Hà Nội",
        payment_method=payment_method,
        order_status=status,
        fulfillment_status="WAITING_PAYMENT" if payment_method != "COD" else "ALLOCATED",
        payment_status=payment_status,
        total_amount=Decimal(str(amount)),
        shipping_fee=Decimal("0"),
        is_verified=True,
    )
    db.add(order)
    db.flush()

    item = OrderItem(
        order_id=order.id,
        product_id=product_id,
        product_sku=sku_code,
        product_name="Thuốc Kháng Sinh H4Care 500mg",
        quantity=2,
        price=Decimal(str(amount / 2)),
        subtotal=Decimal(str(amount)),
    )
    db.add(item)

    tx = PaymentTransaction(
        order_id=order.id,
        transaction_code=f"TXN-{payment_method}-{order_code}",
        provider=payment_method,
        amount=Decimal(str(amount)),
        currency="VND",
        status="PENDING" if payment_status == "UNPAID" else "SUCCESS",
    )
    db.add(tx)
    db.commit()
    db.refresh(order)
    return order


class TestCodPayosPaymentPolicy:
    """
    Bộ kiểm thử chính sách thanh toán H4CARE:
    - Đơn hàng mới: Chỉ chấp nhận COD và PAYOS.
    - MoMo và VietQR thủ công mới: Bị từ chối 400 Bad Request trên mọi endpoint (checkout, create, intent, retry).
    - Giao dịch cũ: Bảo toàn 100% khả năng truy vấn, đối soát và tiếp nhận webhook.
    """

    def test_01_checkout_cod_accepted(self, client: TestClient, setup_test_data):
        """Đặt hàng mới với phương thức COD -> Thành công."""
        token = create_access_token(str(setup_test_data["user_id"]), "CUSTOMER")

        res = client.post(
            "/api/v1/store/orders/checkout",
            json={
                "customer_name": "Khách Test COD",
                "customer_phone": setup_test_data["phone"],
                "shipping_address": "456 Cầu Giấy, Hà Nội",
                "shipping_city": "Hà Nội",
                "province_code": "01",
                "district_code": "009",
                "ward_code": "00142",
                "commune_code": "00142",
                "payment_method": "COD",
                "fulfillment_type": "DELIVERY",
                "is_verified": True,
                "lat": 21.0285,
                "lng": 105.8542,
                "items": [{"product_id": setup_test_data["product_id"], "sku_id": setup_test_data["sku_id"], "quantity": 1}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data.get("order_code") is not None

        db = SessionLocal()
        order = db.query(Order).filter(Order.order_code == data["order_code"]).first()
        db.close()
        assert order is not None
        assert order.payment_method == "COD"
        assert order.order_status in ["PENDING", "PROCESSING", "CONFIRMED"]

    def test_02_checkout_payos_accepted(self, client: TestClient, setup_test_data):
        """Đặt hàng mới với phương thức PAYOS -> Thành công, fulfillment_status là WAITING_PAYMENT."""
        token = create_access_token(str(setup_test_data["user_id"]), "CUSTOMER")

        res = client.post(
            "/api/v1/store/orders/checkout",
            json={
                "customer_name": "Khách Test payOS",
                "customer_phone": setup_test_data["phone"],
                "shipping_address": "456 Cầu Giấy, Hà Nội",
                "shipping_city": "Hà Nội",
                "province_code": "01",
                "district_code": "009",
                "ward_code": "00142",
                "commune_code": "00142",
                "payment_method": "PAYOS",
                "fulfillment_type": "DELIVERY",
                "is_verified": True,
                "lat": 21.0285,
                "lng": 105.8542,
                "items": [{"product_id": setup_test_data["product_id"], "sku_id": setup_test_data["sku_id"], "quantity": 1}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data.get("order_code") is not None

        db = SessionLocal()
        order = db.query(Order).filter(Order.order_code == data["order_code"]).first()
        db.close()
        assert order is not None
        assert order.payment_method == "PAYOS"
        assert order.payment_status in ["PENDING", "UNPAID"]
        assert order.payment_status != "PAID"
        assert order.fulfillment_status == "WAITING_PAYMENT"

    def test_03_checkout_momo_rejected(self, client: TestClient, setup_test_data):
        """Đặt hàng mới với phương thức MOMO -> Bị chặn 400 Bad Request."""
        token = create_access_token(str(setup_test_data["user_id"]), "CUSTOMER")

        res = client.post(
            "/api/v1/store/orders/checkout",
            json={
                "customer_name": "Khách Thử MoMo",
                "customer_phone": setup_test_data["phone"],
                "shipping_address": "789 Cầu Giấy, Hà Nội",
                "province_code": "01",
                "district_code": "009",
                "ward_code": "00142",
                "commune_code": "00142",
                "payment_method": "MOMO",
                "fulfillment_type": "DELIVERY",
                "is_verified": True,
                "lat": 21.0285,
                "lng": 105.8542,
                "items": [{"product_id": setup_test_data["product_id"], "sku_id": setup_test_data["sku_id"], "quantity": 1}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        detail = res.json().get("detail", "").lower()
        assert "ngừng hỗ trợ" in detail or "chọn cod hoặc payos" in detail

    def test_04_checkout_vietqr_rejected(self, client: TestClient, setup_test_data):
        """Đặt hàng mới với phương thức VIETQR / BANK_TRANSFER -> Bị chặn 400."""
        token = create_access_token(str(setup_test_data["user_id"]), "CUSTOMER")

        for method in ["VIETQR", "BANK_TRANSFER"]:
            res = client.post(
                "/api/v1/store/orders/checkout",
                json={
                    "customer_name": "Khách Thử VietQR",
                    "customer_phone": setup_test_data["phone"],
                    "shipping_address": "101 Cầu Giấy, Hà Nội",
                    "province_code": "01",
                    "district_code": "009",
                    "ward_code": "00142",
                    "commune_code": "00142",
                    "payment_method": method,
                    "fulfillment_type": "DELIVERY",
                    "is_verified": True,
                    "lat": 21.0285,
                    "lng": 105.8542,
                    "items": [{"product_id": setup_test_data["product_id"], "sku_id": setup_test_data["sku_id"], "quantity": 1}],
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 400
            assert "ngừng hỗ trợ" in res.json().get("detail", "").lower()

    def test_05_direct_momo_create_blocked(self, client: TestClient, setup_test_data):
        """Endpoint trực tiếp /payments/momo/create -> Bị từ chối 400."""
        db = SessionLocal()
        order_code = f"TEST-MOMO-BLK-{uuid.uuid4().hex[:6].upper()}"
        _create_db_order(
            db,
            setup_test_data["user_id"],
            order_code,
            setup_test_data["product_id"],
            setup_test_data["sku_code"],
            payment_method="PAYOS",
        )
        token = create_access_token(str(setup_test_data["user_id"]), "CUSTOMER")
        db.close()

        res = client.post(
            "/api/v1/payments/momo/create",
            json={"order_code": order_code},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        assert "ngừng cung cấp" in res.json().get("detail", "").lower()

    def test_06_direct_vietqr_create_blocked(self, client: TestClient, setup_test_data):
        """Endpoint trực tiếp /payments/vietqr/create -> Bị từ chối 400."""
        db = SessionLocal()
        order_code = f"TEST-VQR-BLK-{uuid.uuid4().hex[:6].upper()}"
        _create_db_order(
            db,
            setup_test_data["user_id"],
            order_code,
            setup_test_data["product_id"],
            setup_test_data["sku_code"],
            payment_method="PAYOS",
        )
        token = create_access_token(str(setup_test_data["user_id"]), "CUSTOMER")
        db.close()

        res = client.post(
            "/api/v1/payments/vietqr/create",
            json={"order_code": order_code},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        assert "ngừng cung cấp" in res.json().get("detail", "").lower()

    def test_07_payment_intent_policy_enforcement(self, client: TestClient, setup_test_data):
        """Endpoint /payments/intent: MOMO/VIETQR bị từ chối 400; COD thành công."""
        db = SessionLocal()
        order_code = f"TEST-INT-POL-{uuid.uuid4().hex[:6].upper()}"
        _create_db_order(
            db,
            setup_test_data["user_id"],
            order_code,
            setup_test_data["product_id"],
            setup_test_data["sku_code"],
            payment_method="PAYOS",
        )
        token = create_access_token(str(setup_test_data["user_id"]), "CUSTOMER")
        db.close()

        # 1. Thử intent MOMO -> 400
        res_momo = client.post(
            "/api/v1/payments/intent",
            json={"order_code": order_code, "payment_method": "MOMO"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_momo.status_code == 400
        assert "ngừng hỗ trợ" in res_momo.json()["detail"].lower()

        # 2. Thử intent VIETQR -> 400
        res_vqr = client.post(
            "/api/v1/payments/intent",
            json={"order_code": order_code, "payment_method": "VIETQR"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_vqr.status_code == 400
        assert "ngừng hỗ trợ" in res_vqr.json()["detail"].lower()

        # 3. Chuyển sang COD -> 200 OK
        res_cod = client.post(
            "/api/v1/payments/intent",
            json={"order_code": order_code, "payment_method": "COD"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_cod.status_code == 200
        assert res_cod.json()["provider"] == "COD"

    def test_08_payment_retry_policy_enforcement(self, client: TestClient, setup_test_data):
        """Endpoint /payments/retry: Không cho retry sang MOMO/VIETQR; Retry sang COD hợp lệ."""
        db = SessionLocal()
        order_code = f"TEST-RTY-POL-{uuid.uuid4().hex[:6].upper()}"
        _create_db_order(
            db,
            setup_test_data["user_id"],
            order_code,
            setup_test_data["product_id"],
            setup_test_data["sku_code"],
            payment_method="PAYOS",
        )
        token = create_access_token(str(setup_test_data["user_id"]), "CUSTOMER")
        db.close()

        # Thử retry sang MOMO -> 400
        res_momo = client.post(
            "/api/v1/payments/retry",
            json={"order_code": order_code, "new_payment_method": "MOMO"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_momo.status_code == 400
        assert "ngừng hỗ trợ" in res_momo.json()["detail"].lower()

        # Retry sang COD -> 200 OK
        res_cod = client.post(
            "/api/v1/payments/retry",
            json={"order_code": order_code, "new_payment_method": "COD"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_cod.status_code == 200
        assert res_cod.json()["provider"] == "COD"

    def test_09_historical_order_query_maintained(self, client: TestClient, setup_test_data):
        """Bảo tồn đối soát: Đơn hàng cũ sử dụng MOMO hoặc VIETQR vẫn tra cứu được 100%."""
        db = SessionLocal()
        momo_code = f"OLD-MOMO-{uuid.uuid4().hex[:6].upper()}"
        vqr_code = f"OLD-VQR-{uuid.uuid4().hex[:6].upper()}"
        _create_db_order(
            db,
            setup_test_data["user_id"],
            momo_code,
            setup_test_data["product_id"],
            setup_test_data["sku_code"],
            payment_method="MOMO",
            payment_status="PAID",
        )
        _create_db_order(
            db,
            setup_test_data["user_id"],
            vqr_code,
            setup_test_data["product_id"],
            setup_test_data["sku_code"],
            payment_method="VIETQR",
            payment_status="PAID",
        )
        token = create_access_token(str(setup_test_data["user_id"]), "CUSTOMER")
        db.close()

        # Tra cứu đơn MoMo cũ
        res_m = client.get(f"/api/v1/payments/orders/{momo_code}/status", headers={"Authorization": f"Bearer {token}"})
        assert res_m.status_code == 200
        data_m = res_m.json()
        assert data_m["payment_method"] == "MOMO"
        assert data_m["payment_status"] == "PAID"

        # Tra cứu đơn VietQR cũ
        res_v = client.get(f"/api/v1/payments/orders/{vqr_code}/status", headers={"Authorization": f"Bearer {token}"})
        assert res_v.status_code == 200
        data_v = res_v.json()
        assert data_v["payment_method"] == "VIETQR"
        assert data_v["payment_status"] == "PAID"

    def test_10_paid_order_cannot_be_retried(self, client: TestClient, setup_test_data):
        """Đơn hàng đã PAID không được phép thanh toán lại hay chuyển phương thức."""
        db = SessionLocal()
        paid_code = f"PAID-ORDER-{uuid.uuid4().hex[:6].upper()}"
        _create_db_order(
            db,
            setup_test_data["user_id"],
            paid_code,
            setup_test_data["product_id"],
            setup_test_data["sku_code"],
            payment_method="PAYOS",
            payment_status="PAID",
        )
        token = create_access_token(str(setup_test_data["user_id"]), "CUSTOMER")
        db.close()

        res = client.post(
            "/api/v1/payments/retry",
            json={"order_code": paid_code, "new_payment_method": "COD"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        assert "đã được thanh toán" in res.json()["detail"].lower()
