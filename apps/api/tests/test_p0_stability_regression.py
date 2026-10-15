"""
apps/api/tests/test_p0_stability_regression.py

Dedicated regression tests covering the 4 P0 Priorities:
1. Anti-IDOR: Guest order token required, phone-only rejected with 403.
2. Anti-IDOR on Returns, Eligibility, Cancellation, and Payment Status.
3. Commercial Integrity: Backend calculates voucher, shipping fee, and grand total.
4. Data Integrity: No fake barcodes, no fake prices synthesized.
5. Production Deployment Safety: Secret key length and simulator disabling fail-closed checks.
"""

from decimal import Decimal
import unittest
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import create_guest_order_token, verify_guest_order_token
from app.db.session import SessionLocal
from app.main import app
from app.models import CanonicalProduct, Order, OrderItem, ProductSku, Warehouse, WarehouseBatchStock, InventoryBatch, BatchStatus
from app.models.enums import RegulatoryStatus, RxOtcStatus, PublishStatus
from app.services.fulfillment_service import FulfillmentRoutingService


class TestP0StabilityRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Setup test warehouse
        cls.wh = cls.db.query(Warehouse).filter_by(code="KHO-P0-REG").first()
        if not cls.wh:
            cls.wh = Warehouse(
                code="KHO-P0-REG",
                name="Kho P0 Regression Test",
                address="77 Đường Cách Mạng, Q.1, TP.HCM",
                lat=10.7769,
                lng=106.7009,
                is_active=True,
                is_central=True,
            )
            cls.db.add(cls.wh)
            cls.db.commit()
            cls.db.refresh(cls.wh)

        # Setup test product and SKU
        cls.prod = cls.db.query(CanonicalProduct).filter_by(id=9901).first()
        if not cls.prod:
            cls.prod = CanonicalProduct(
                id=9901,
                canonical_name="Thuốc Kháng Sinh P0 Test 500mg",
                registration_number="VD-9901-26",
                regulatory_status=RegulatoryStatus.ACTIVE,
                rx_otc_status=RxOtcStatus.OTC,
                publish_status=PublishStatus.PUBLISHED,
                publish_mode="SALE_ELIGIBLE",
            )
            cls.db.add(cls.prod)
            cls.db.commit()

        cls.sku = cls.db.query(ProductSku).filter_by(canonical_product_id=9901).first()
        if not cls.sku:
            cls.sku = ProductSku(
                canonical_product_id=9901,
                sku_code="SKU-9901-TEST",
                base_price=Decimal("120000.0"),
                is_default=True,
                is_active=True,
            )
            cls.db.add(cls.sku)
            cls.db.commit()
            cls.db.refresh(cls.sku)

        cls.batch = cls.db.query(InventoryBatch).filter_by(sku_id=cls.sku.id).first()
        if not cls.batch:
            from datetime import date, timedelta
            cls.batch = InventoryBatch(
                sku_id=cls.sku.id,
                batch_number="LOT-P0-9901",
                expiry_date=date.today() + timedelta(days=365),
                initial_quantity=500,
                status=BatchStatus.ACTIVE,
            )
            cls.db.add(cls.batch)
            cls.db.commit()
            cls.db.refresh(cls.batch)

        cls.stock = cls.db.query(WarehouseBatchStock).filter_by(warehouse_id=cls.wh.id, batch_id=cls.batch.id).first()
        if not cls.stock:
            cls.stock = WarehouseBatchStock(
                warehouse_id=cls.wh.id,
                batch_id=cls.batch.id,
                quantity_on_hand=500,
                quantity_reserved=0,
                quantity_available=500,
            )
            cls.db.add(cls.stock)
            cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def tearDown(self):
        self.db.rollback()

    # -------------------------------------------------------------------------
    # PRIORITY 1: ANTI-IDOR & GUEST TOKEN SECURITY
    # -------------------------------------------------------------------------
    def test_01_guest_order_token_cryptography(self):
        """Token can be verified, but altered or expired tokens fail."""
        order_code = "PT-REG-0001"
        phone = "0988776655"
        token = create_guest_order_token(order_code, phone)
        self.assertTrue(verify_guest_order_token(token, order_code))
        self.assertFalse(verify_guest_order_token(token, "PT-OTHER-9999"))
        self.assertFalse(verify_guest_order_token("invalid.token.structure", order_code))
        self.assertFalse(verify_guest_order_token(None, order_code))

    def test_02_order_detail_phone_only_rejected(self):
        """Viewing guest order with phone only returns 403 Forbidden."""
        order = Order(
            order_code="PT-P0-PHONE-ONLY",
            customer_name="Trần Văn Phone",
            customer_phone="0911223344",
            shipping_address="123 Nguyễn Trãi, Hà Nội",
            payment_method="COD",
            payment_status="PENDING",
            order_status="PENDING",
            total_amount=Decimal("120000.0"),
        )
        self.db.add(order)
        self.db.commit()

        # Phone only -> 403 Forbidden
        res_phone = self.client.get(f"/api/v1/store/orders/{order.order_code}?phone={order.customer_phone}")
        self.assertEqual(res_phone.status_code, 403)
        self.assertIn("Số điện thoại không phải là bằng chứng duy nhất", res_phone.json()["detail"])

        # Signed guest token -> 200 OK
        token = create_guest_order_token(order.order_code, order.customer_phone)
        res_token = self.client.get(f"/api/v1/store/orders/{order.order_code}?token={token}")
        self.assertEqual(res_token.status_code, 200)
        self.assertEqual(res_token.json()["order_code"], order.order_code)

    def test_03_payment_status_and_cancellation_phone_only_rejected(self):
        """Payment status check and cancellation reject phone-only requests."""
        order = Order(
            order_code="PT-P0-PAY-CANCEL",
            customer_name="Lê Văn Hủy",
            customer_phone="0933445566",
            shipping_address="456 CMT8, TP.HCM",
            payment_method="MOMO",
            payment_status="PENDING",
            order_status="PENDING",
            total_amount=Decimal("120000.0"),
        )
        self.db.add(order)
        self.db.commit()

        # 1. Status check with phone only -> 403
        r_status = self.client.get(f"/api/v1/payments/orders/{order.order_code}/status?phone_verify={order.customer_phone}")
        self.assertEqual(r_status.status_code, 403)

        # Status check with token -> 200
        token = create_guest_order_token(order.order_code, order.customer_phone)
        r_status_ok = self.client.get(f"/api/v1/payments/orders/{order.order_code}/status?token={token}")
        self.assertEqual(r_status_ok.status_code, 200)

        # 2. Cancel order with phone only -> 403
        r_cancel = self.client.post(f"/api/v1/payments/orders/{order.order_code}/cancel", json={
            "reason": "Test cancel without token",
            "phone_verify": order.customer_phone,
        })
        self.assertEqual(r_cancel.status_code, 403)

        # Cancel order with token -> 200
        r_cancel_ok = self.client.post(f"/api/v1/payments/orders/{order.order_code}/cancel", json={
            "reason": "Test cancel with valid token",
            "phone_verify": order.customer_phone,
            "order_token": token,
        })
        self.assertEqual(r_cancel_ok.status_code, 200)

    # -------------------------------------------------------------------------
    # PRIORITY 2: COMMERCIAL INTEGRITY & BACKEND PRICING TRUTH
    # -------------------------------------------------------------------------
    def test_04_server_side_voucher_and_shipping_calculation(self):
        """Backend calculates voucher discount and shipping fee; client cannot dictate price."""
        payload = {
            "customer_name": "Nguyễn Giá Chuẩn",
            "customer_phone": "0977112233",
            "shipping_address": "88 Phố Huế, Hoàn Kiếm, Hà Nội",
            "shipping_city": "Hà Nội",
            "province_code": "01",
            "commune_code": "00001",
            "lat": 21.0285,
            "lng": 105.8542,
            "is_verified": True,
            "payment_method": "COD",
            "voucher_code": "H4CARENEW",  # Giảm 20.000đ
            "items": [{"product_id": 9901, "sku_id": self.sku.id, "quantity": 1}],
        }
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Catalog price is 120,000 VND
        # Discount H4CARENEW is 20,000 VND
        # Subtotal: 120,000 - 20,000 = 100,000 + shipping fee
        self.assertIn("order_token", data)
        self.assertIn("guest_access_token", data)
        self.assertEqual(data["order_status"], "PENDING")

        order_code = data["order_code"]
        db_order = self.db.query(Order).filter_by(order_code=order_code).first()
        self.assertIsNotNone(db_order)
        # Server-side calculation: 120,000 subtotal - 20,000 discount = 100,000 + server shipping fee (15k local or 45k interprovincial)
        self.assertIn(db_order.total_amount, [Decimal("115000.0"), Decimal("145000.0")])
        self.assertIn(db_order.shipping_fee, [Decimal("15000.0"), Decimal("45000.0")])

    def test_05_no_fabricated_barcodes_or_prices(self):
        """FulfillmentRoutingService does not synthesize fake 893... barcodes or 50k prices."""
        temp_prod = CanonicalProduct(
            id=9902,
            canonical_name="Thuốc Mới Chưa Có Lô 9902",
            registration_number="VD-9902-26",
            regulatory_status=RegulatoryStatus.ACTIVE,
            rx_otc_status=RxOtcStatus.OTC,
            publish_status=PublishStatus.PUBLISHED,
        )
        self.db.add(temp_prod)
        self.db.commit()

        sku = FulfillmentRoutingService.get_or_create_default_sku(self.db, 9902)
        # Barcode must be None (not fake 893000009902)
        self.assertIsNone(sku.barcode)
        # Base price must be Decimal("0.0") when no price observation exists (not fabricated 50000.0)
        self.assertEqual(sku.base_price, Decimal("0.0"))

    # -------------------------------------------------------------------------
    # PRIORITY 3: PRODUCTION DEPLOYMENT SAFETY
    # -------------------------------------------------------------------------
    def test_06_production_secrets_and_simulator_fail_closed(self):
        """Production startup validator crashes on default secret or active simulator."""
        # 1. Default secret in production -> Must raise ValueError
        with self.assertRaises(ValueError) as ctx1:
            Settings(
                app_env="production",
                secret_key="development-only-secret-change-me-please",
                enable_payment_simulator=False,
            )
        self.assertIn("BẢO MẬT SẢN PHẨM", str(ctx1.exception))

        # 2. Secret too short in production -> Must raise ValueError
        with self.assertRaises(ValueError) as ctx2:
            Settings(
                app_env="production",
                secret_key="short_secret_under_32_chars",
                enable_payment_simulator=False,
            )
        self.assertIn("BẢO MẬT SẢN PHẨM", str(ctx2.exception))

        # 3. Simulator enabled in production -> Must raise ValueError
        with self.assertRaises(ValueError) as ctx3:
            Settings(
                app_env="production",
                secret_key="a_very_secure_random_key_of_at_least_32_chars_ok",
                enable_payment_simulator=True,
            )
        self.assertIn("BẢO MẬT SẢN PHẨM", str(ctx3.exception))

        # 4. Valid production settings -> Must succeed
        prod_settings = Settings(
            app_env="production",
            secret_key="a_very_secure_random_key_of_at_least_32_chars_ok",
            enable_payment_simulator=False,
        )
        self.assertEqual(prod_settings.app_env, "production")
        self.assertFalse(prod_settings.is_simulator_permitted)

    # -------------------------------------------------------------------------
    # PRIORITY 4: IDEMPOTENCY REPLAY ACCESS CONTROL & COMMERCE TAMPERING
    # -------------------------------------------------------------------------
    def test_07_idempotency_replay_unauthorized_attacker_rejected(self):
        """Attacker cannot steal guest order token by replaying another customer's idempotency key."""
        import uuid
        idem_key = f"IDEM-SEC-{uuid.uuid4().hex[:10]}"
        legit_phone = "0988776655"
        attacker_phone = "0912345999"

        payload_legit = {
            "customer_name": "Chủ Đơn Thật",
            "customer_phone": legit_phone,
            "shipping_address": "77 Đường Cách Mạng, Q.1, TP.HCM",
            "shipping_city": "TP. Hồ Chí Minh",
            "province_code": "79",
            "district_code": "760",
            "ward_code": "26734",
            "lat": 10.7769,
            "lng": 106.7009,
            "is_verified": True,
            "payment_method": "COD",
            "idempotency_key": idem_key,
            "items": [{"product_id": 9901, "quantity": 1}],
        }
        res_legit = self.client.post("/api/v1/store/orders/checkout", json=payload_legit)
        self.assertEqual(res_legit.status_code, 200, res_legit.text)
        legit_data = res_legit.json()
        self.assertIn("guest_access_token", legit_data)

        # 1. Attacker calls with same idempotency key but different phone -> Must be rejected with 403
        payload_attacker = dict(payload_legit)
        payload_attacker["customer_phone"] = attacker_phone
        payload_attacker["customer_name"] = "Kẻ Tấn Công"
        res_attacker = self.client.post("/api/v1/store/orders/checkout", json=payload_attacker)
        self.assertEqual(res_attacker.status_code, 403, res_attacker.text)
        self.assertIn("Idempotency key này không thuộc về số điện thoại", res_attacker.json()["detail"])

        # 2. Replay with same phone & key without token -> 200 OK (Idempotent replay) BUT token is NOT re-issued
        res_replay = self.client.post("/api/v1/store/orders/checkout", json=payload_legit)
        self.assertEqual(res_replay.status_code, 200, res_replay.text)
        replay_data = res_replay.json()
        self.assertTrue(replay_data["is_idempotent_replay"])
        self.assertEqual(replay_data["order_code"], legit_data["order_code"])
        self.assertNotIn("guest_access_token", replay_data, "Guest token must NOT be re-issued merely by matching phone and idempotency key")

        # 3. Replay with verified X-Order-Token -> token confirmed
        res_token = self.client.post("/api/v1/store/orders/checkout", json=payload_legit, headers={"X-Order-Token": legit_data["guest_access_token"]})
        self.assertEqual(res_token.status_code, 200)
        self.assertIn("guest_access_token", res_token.json())

    def test_08_shipping_fee_tampering_rejected(self):
        """Negative shipping fee or invalid numeric value is strictly rejected with HTTP 400."""
        payload_neg = {
            "customer_name": "Test Ship Fee",
            "customer_phone": "0988776654",
            "shipping_address": "77 Đường Cách Mạng, Q.1, TP.HCM",
            "shipping_city": "TP. Hồ Chí Minh",
            "province_code": "79",
            "district_code": "760",
            "ward_code": "26734",
            "lat": 10.7769,
            "lng": 106.7009,
            "is_verified": True,
            "payment_method": "COD",
            "shipping_fee": -50000.0,  # Negative shipping fee tampering
            "items": [{"product_id": 9901, "quantity": 1}],
        }
        res = self.client.post("/api/v1/store/orders/checkout", json=payload_neg)
        self.assertEqual(res.status_code, 400, res.text)
        self.assertIn("Phí vận chuyển không hợp lệ", res.json()["detail"])

        # Zero shipping fee tampering on order < 300k is strictly rejected with HTTP 400
        payload_zero = dict(payload_neg)
        payload_zero["shipping_fee"] = 0.0
        res_zero = self.client.post("/api/v1/store/orders/checkout", json=payload_zero)
        self.assertEqual(res_zero.status_code, 400, res_zero.text)
        self.assertIn("Không cho phép client tự quyết định phí giao hàng bằng 0đ", res_zero.json()["detail"])

    def test_09_free_shipping_threshold_enforced(self):
        """Orders >= 300,000 VND always receive 0 VND shipping fee by server calculation."""
        # 4 boxes of 9901 (120,000 x 4 = 480,000 > 300,000)
        payload_free = {
            "customer_name": "Test Free Ship",
            "customer_phone": "0988776653",
            "shipping_address": "77 Đường Cách Mạng, Q.1, TP.HCM",
            "shipping_city": "TP. Hồ Chí Minh",
            "province_code": "79",
            "district_code": "760",
            "ward_code": "26734",
            "lat": 10.7769,
            "lng": 106.7009,
            "is_verified": True,
            "payment_method": "COD",
            "shipping_fee": 99000.0,  # Client tries to send high shipping fee
            "items": [{"product_id": 9901, "quantity": 4}],
        }
        res = self.client.post("/api/v1/store/orders/checkout", json=payload_free)
        self.assertEqual(res.status_code, 200, res.text)
        order = self.db.query(Order).filter_by(order_code=res.json()["order_code"]).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.shipping_fee, Decimal("0.0"))
        self.assertEqual(order.total_amount, Decimal("480000.0"))

    def test_10_cors_origin_restriction_hardened(self):
        """CORS middleware does not contain wildcard allow_origin_regex."""
        from fastapi.middleware.cors import CORSMiddleware
        for middleware in app.user_middleware:
            if middleware.cls == CORSMiddleware:
                # verify allow_origin_regex is empty or None
                self.assertFalse(middleware.kwargs.get("allow_origin_regex"))

    # -------------------------------------------------------------------------
    # PRIORITY 5: RETURN EVIDENCE PRIVACY, STATIC URL RESTRICTION & MAGIC BYTES
    # -------------------------------------------------------------------------
    def test_11_return_evidence_security_and_privacy(self):
        """Return evidence files are strictly protected from static access and fake uploads."""
        # 1. Direct static access to /storage/returns must be blocked (HTTP 403)
        res_static = self.client.get("/storage/returns/secret_evidence.jpg")
        self.assertEqual(res_static.status_code, 403, res_static.text)
        self.assertIn("bị từ chối vì lý do bảo mật", res_static.json()["detail"])

        # 2. Upload dangerous extension (.exe, .sh) must be rejected with HTTP 400
        import io
        fake_exe = io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00")
        res_exe = self.client.post(
            "/api/v1/returns/upload-evidence",
            files={"file": ("exploit.exe", fake_exe, "application/octet-stream")},
        )
        self.assertEqual(res_exe.status_code, 400)
        self.assertIn("nguy hiểm bị từ chối", res_exe.json()["detail"])

        # 3. Upload file with mismatched magic bytes (text disguised as .jpg) must be rejected with HTTP 400
        fake_jpg = io.BytesIO(b"Plain text payload pretending to be a jpeg image")
        res_fake_jpg = self.client.post(
            "/api/v1/returns/upload-evidence",
            files={"file": ("fake_proof.jpg", fake_jpg, "image/jpeg")},
        )
        self.assertEqual(res_fake_jpg.status_code, 400)
        self.assertIn("Chữ ký tệp không hợp lệ", res_fake_jpg.json()["detail"])

        # 4. Upload valid JPEG binary (starts with \xff\xd8\xff) succeeds
        valid_jpg_content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"
        valid_jpg = io.BytesIO(valid_jpg_content)
        res_valid = self.client.post(
            "/api/v1/returns/upload-evidence",
            files={"file": ("legit_photo.jpg", valid_jpg, "image/jpeg")},
        )
        self.assertEqual(res_valid.status_code, 200, res_valid.text)
        evid_data = res_valid.json()
        self.assertTrue(evid_data["success"])
        filename = evid_data["file_name"]

        # 5. Accessing evidence via secure API without ownership or token must return 403 Forbidden
        res_unauth = self.client.get(evid_data["file_url"])
        self.assertEqual(res_unauth.status_code, 403)

    def test_12_atomic_rollback_on_failed_checkout_transaction(self):
        """Checkout transaction cleanly rolls back when an error occurs during stock allocation."""
        order_count_before = self.db.query(Order).count()
        import uuid
        failing_payload = {
            "customer_name": "Test Rollback",
            "customer_phone": "0988776652",
            "shipping_address": "77 Đường Cách Mạng, Q.1, TP.HCM",
            "shipping_city": "TP. Hồ Chí Minh",
            "province_code": "79",
            "district_code": "760",
            "ward_code": "26734",
            "lat": 10.7769,
            "lng": 106.7009,
            "is_verified": True,
            "payment_method": "COD",
            "idempotency_key": f"IDEM-ROLLBACK-{uuid.uuid4().hex[:8]}",
            # Requesting product 99999 that has no stock / does not exist
            "items": [{"product_id": 99999, "quantity": 1}],
        }
        res = self.client.post("/api/v1/store/orders/checkout", json=failing_payload)
        self.assertIn(res.status_code, [400, 404])
        # Verify no half-baked Order record was committed
        order_count_after = self.db.query(Order).count()
        self.assertEqual(order_count_after, order_count_before)


if __name__ == "__main__":
    unittest.main()

