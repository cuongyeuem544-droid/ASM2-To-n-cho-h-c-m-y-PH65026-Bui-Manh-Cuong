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

        # Signed guest token in query string is disallowed -> 403 Forbidden
        token = create_guest_order_token(order.order_code, order.customer_phone)
        res_query_token = self.client.get(f"/api/v1/store/orders/{order.order_code}?token={token}")
        self.assertEqual(res_query_token.status_code, 403)

        # Signed guest token via X-Order-Token header -> 200 OK
        res_token = self.client.get(
            f"/api/v1/store/orders/{order.order_code}",
            headers={"X-Order-Token": token},
        )
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

        # Status check with query token -> 403 (query token removed)
        token = create_guest_order_token(order.order_code, order.customer_phone)
        r_status_query = self.client.get(f"/api/v1/payments/orders/{order.order_code}/status?token={token}")
        self.assertEqual(r_status_query.status_code, 403)

        # Status check with X-Order-Token header -> 200
        r_status_ok = self.client.get(
            f"/api/v1/payments/orders/{order.order_code}/status",
            headers={"X-Order-Token": token},
        )
        self.assertEqual(r_status_ok.status_code, 200)

        # 2. Cancel order with phone only -> 403
        r_cancel = self.client.post(f"/api/v1/payments/orders/{order.order_code}/cancel", json={
            "reason": "Test cancel without token",
            "phone_verify": order.customer_phone,
        })
        self.assertEqual(r_cancel.status_code, 403)

        # Cancel order with token -> 200
        r_cancel_ok = self.client.post(
            f"/api/v1/payments/orders/{order.order_code}/cancel",
            json={
                "reason": "Test cancel with valid token",
                "phone_verify": order.customer_phone,
                "order_token": token,
            },
            headers={"X-Order-Token": token},
        )
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

        import io
        import uuid
        ret_order = Order(
            order_code=f"PT-EVID-{uuid.uuid4().hex[:6]}",
            customer_name="Khách Hàng Test Evidence",
            customer_phone="0911556677",
            shipping_address="123 Lê Duẩn, Q.1, TP.HCM",
            payment_method="COD",
            payment_status="PENDING",
            order_status="DELIVERED",
            total_amount=Decimal("120000.0"),
        )
        self.db.add(ret_order)
        self.db.commit()

        from app.models.returns import ReturnRequest, ReturnRequestType, ReturnStatus
        ret_req = ReturnRequest(
            return_code=f"RET-EVID-{uuid.uuid4().hex[:6]}",
            order_id=ret_order.id,
            request_type=ReturnRequestType.RETURN,
            status=ReturnStatus.REQUESTED,
            reason_code="WRONG_ITEM",
            reason_text="Giao nhầm thuốc",
            customer_name=ret_order.customer_name,
            customer_phone=ret_order.customer_phone,
        )
        self.db.add(ret_req)
        self.db.commit()

        order_token = create_guest_order_token(ret_order.order_code, ret_order.customer_phone)

        # 2. Upload without return_code (prevent orphan files) must be rejected with HTTP 422 or 400
        fake_jpg = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00")
        res_no_code = self.client.post(
            "/api/v1/returns/upload-evidence",
            files={"file": ("legit.jpg", fake_jpg, "image/jpeg")},
        )
        self.assertIn(res_no_code.status_code, [400, 422])

        # 3. Upload dangerous extension (.exe) must be rejected with HTTP 400
        fake_exe = io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00")
        res_exe = self.client.post(
            "/api/v1/returns/upload-evidence",
            data={"return_code": ret_req.return_code},
            files={"file": ("exploit.exe", fake_exe, "application/octet-stream")},
            headers={"X-Order-Token": order_token},
        )
        self.assertEqual(res_exe.status_code, 400)
        self.assertIn("nguy hiểm bị từ chối", res_exe.json()["detail"])

        # 4. Upload file with mismatched magic bytes (text disguised as .jpg) must be rejected with HTTP 400
        fake_jpg_spoof = io.BytesIO(b"Plain text payload pretending to be a jpeg image")
        res_fake_jpg = self.client.post(
            "/api/v1/returns/upload-evidence",
            data={"return_code": ret_req.return_code},
            files={"file": ("fake_proof.jpg", fake_jpg_spoof, "image/jpeg")},
            headers={"X-Order-Token": order_token},
        )
        self.assertEqual(res_fake_jpg.status_code, 400)
        self.assertIn("Chữ ký tệp không hợp lệ", res_fake_jpg.json()["detail"])

        # 5. Upload without valid token/ownership must be rejected with HTTP 403
        valid_jpg_content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"
        res_unauth_upload = self.client.post(
            "/api/v1/returns/upload-evidence",
            data={"return_code": ret_req.return_code},
            files={"file": ("legit_photo.jpg", io.BytesIO(valid_jpg_content), "image/jpeg")},
        )
        self.assertEqual(res_unauth_upload.status_code, 403)

        # 6. Upload valid JPEG binary with X-Order-Token header succeeds
        res_valid = self.client.post(
            "/api/v1/returns/upload-evidence",
            data={"return_code": ret_req.return_code},
            files={"file": ("legit_photo.jpg", io.BytesIO(valid_jpg_content), "image/jpeg")},
            headers={"X-Order-Token": order_token},
        )
        self.assertEqual(res_valid.status_code, 200, res_valid.text)
        evid_data = res_valid.json()
        self.assertTrue(evid_data["success"])
        filename = evid_data["file_name"]

        # 7. Accessing evidence via secure API without ownership or token must return 403 Forbidden
        res_unauth = self.client.get(evid_data["file_url"])
        self.assertEqual(res_unauth.status_code, 403)

        # 8. Accessing evidence with query string token is disallowed -> 403 Forbidden
        res_query = self.client.get(f"{evid_data['file_url']}?token={order_token}")
        self.assertEqual(res_query.status_code, 403)

        # 9. Accessing evidence with X-Order-Token header succeeds (200 OK)
        res_authorized = self.client.get(
            evid_data["file_url"],
            headers={"X-Order-Token": order_token},
        )
        self.assertEqual(res_authorized.status_code, 200)
        self.assertEqual(res_authorized.content, valid_jpg_content)

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

    def test_13_admin_order_status_cannot_tamper_payment_status(self):
        """PATCH /admin/orders/{id}/status strictly rejects tampering payment_status."""
        from app.core.security import create_access_token
        admin_token = create_access_token("1", "ADMIN")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        import uuid
        test_order = Order(
            order_code=f"PT-STATUS-{uuid.uuid4().hex[:6]}",
            customer_name="Test Payment Tamper",
            customer_phone="0911889900",
            shipping_address="100 Hai Bà Trưng, Q.1, TP.HCM",
            payment_method="COD",
            payment_status="PENDING",
            order_status="PENDING",
            total_amount=Decimal("150000.0"),
        )
        self.db.add(test_order)
        self.db.commit()

        # 1. Attempt to change payment_status from PENDING -> PAID via order status update
        res_paid = self.client.patch(
            f"/api/v1/admin/orders/{test_order.id}/status",
            json={"order_status": "CONFIRMED", "payment_status": "PAID"},
            headers=admin_headers,
        )
        self.assertEqual(res_paid.status_code, 400)
        self.assertIn("Không được phép thay đổi trực tiếp payment_status", res_paid.json()["detail"])

        # 2. Attempt to change payment_status to FAILED
        res_failed = self.client.patch(
            f"/api/v1/admin/orders/{test_order.id}/status",
            json={"order_status": "CONFIRMED", "payment_status": "FAILED"},
            headers=admin_headers,
        )
        self.assertEqual(res_failed.status_code, 400)

        # 3. Legitimate order status change (PENDING -> CONFIRMED) without payment_status succeeds
        res_ok = self.client.patch(
            f"/api/v1/admin/orders/{test_order.id}/status",
            json={"order_status": "CONFIRMED"},
            headers=admin_headers,
        )
        self.assertEqual(res_ok.status_code, 200)
        self.db.refresh(test_order)
        self.assertEqual(test_order.order_status, "CONFIRMED")
        self.assertEqual(test_order.payment_status, "PENDING")

    def test_14_admin_warehouse_receive_and_multi_item_gsp_inspection(self):
        """Admin Warehouse Receive & Multi-Item GSP Inspection strictly enforce pharmacy standards."""
        from app.core.security import create_access_token
        from app.models.returns import ReturnRequest, ReturnItem, ReturnRequestType, ReturnStatus, ItemCondition, RestockDestination
        from app.models.inventory import OrderItemBatchAllocation
        admin_token = create_access_token("1", "ADMIN")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        import uuid
        order = Order(
            order_code=f"PT-GSP-{uuid.uuid4().hex[:6]}",
            customer_name="Nguyễn GSP Test",
            customer_phone="0944556677",
            shipping_address="50 Hai Bà Trưng, TP.HCM",
            payment_method="COD",
            payment_status="PAID",
            order_status="DELIVERED",
            total_amount=Decimal("240000.0"),
        )
        self.db.add(order)
        self.db.commit()

        order_item = OrderItem(
            order_id=order.id,
            product_id=self.prod.id,
            product_name=self.prod.canonical_name,
            product_sku=self.sku.sku_code,
            price=Decimal("120000.0"),
            quantity=2,
            subtotal=Decimal("240000.0"),
        )
        self.db.add(order_item)
        self.db.commit()

        alloc = OrderItemBatchAllocation(
            order_item_id=order_item.id,
            batch_id=self.batch.id,
            warehouse_id=self.wh.id,
            allocated_quantity=2,
        )
        self.db.add(alloc)
        self.db.commit()

        ret = ReturnRequest(
            return_code=f"RET-GSP-{uuid.uuid4().hex[:6]}",
            order_id=order.id,
            request_type=ReturnRequestType.RETURN,
            status=ReturnStatus.APPROVED,
            reason_code="DAMAGED_DELIVERY",
            reason_text="Hàng bị móp rách khi vận chuyển",
            customer_name=order.customer_name,
            customer_phone=order.customer_phone,
        )
        self.db.add(ret)
        self.db.commit()

        # Item 1: Good condition
        it1 = ReturnItem(
            return_request_id=ret.id,
            order_item_id=order_item.id,
            product_id=self.prod.id,
            sku_id=self.sku.id,
            product_name="Thuốc Kháng Sinh P0 Test 500mg - Hộp 1",
            original_quantity=1,
            requested_quantity=1,
            unit_price_at_purchase=Decimal("120000.0"),
            allocated_discount=Decimal("0.0"),
            net_paid_amount=Decimal("120000.0"),
            requested_refund_amount=Decimal("120000.0"),
            condition=ItemCondition.GOOD_CONDITION,
        )
        # Item 2: Damaged
        it2 = ReturnItem(
            return_request_id=ret.id,
            order_item_id=order_item.id,
            product_id=self.prod.id,
            sku_id=self.sku.id,
            product_name="Thuốc Kháng Sinh P0 Test 500mg - Hộp 2",
            original_quantity=1,
            requested_quantity=1,
            unit_price_at_purchase=Decimal("120000.0"),
            allocated_discount=Decimal("0.0"),
            net_paid_amount=Decimal("120000.0"),
            requested_refund_amount=Decimal("120000.0"),
            condition=ItemCondition.DAMAGED,
        )
        self.db.add_all([it1, it2])
        self.db.commit()
        self.db.refresh(it1)
        self.db.refresh(it2)

        # 1. Warehouse receives return via POST /admin/returns/{return_code}/receive
        res_receive = self.client.post(
            f"/api/v1/admin/returns/{ret.return_code}/receive",
            json={"note": "Kho tiếp nhận kiện hàng hoàn trả từ bưu tá."},
            headers=admin_headers,
        )
        self.assertEqual(res_receive.status_code, 200, res_receive.text)
        self.db.refresh(ret)
        self.assertEqual(ret.status, ReturnStatus.RECEIVED)

        # 2. Strict status check: Cannot receive again
        res_receive_again = self.client.post(
            f"/api/v1/admin/returns/{ret.return_code}/receive",
            json={"note": "Thử nhận lần 2"},
            headers=admin_headers,
        )
        self.assertEqual(res_receive_again.status_code, 400)

        # 3. GSP Law Violation check: Damaged medicine cannot be restocked into SELLABLE_STOCK
        illegal_gsp_payload = {
            "general_inspection_note": "Vi phạm GSP: Cố tình nhập thuốc hỏng vào kho bán",
            "items": [
                {
                    "return_item_id": it2.id,
                    "condition": "DAMAGED",
                    "restock_destination": "SELLABLE_STOCK",  # VIOLATION!
                    "accepted_quantity": 1,
                    "rejected_quantity": 0,
                    "restock_quantity": 1,
                    "notes": "Hộp móp rách",
                }
            ],
        }
        res_illegal = self.client.post(
            f"/api/v1/admin/returns/{ret.return_code}/inspect",
            json=illegal_gsp_payload,
            headers=admin_headers,
        )
        self.assertEqual(res_illegal.status_code, 400)
        self.assertIn("không đáp ứng tiêu chuẩn chất lượng GSP", res_illegal.json()["detail"])

        # 4. Multi-item GSP Inspection compliant submission
        stock_before = self.db.query(WarehouseBatchStock).filter_by(warehouse_id=self.wh.id, batch_id=self.batch.id).first()
        qty_before = stock_before.quantity_on_hand

        compliant_payload = {
            "general_inspection_note": "Kiểm định Dược GSP hoàn tất: 1 hộp đạt chuẩn nhập kho bán, 1 hộp hỏng cách ly tiêu hủy",
            "items": [
                {
                    "return_item_id": it1.id,
                    "condition": "GOOD_CONDITION",
                    "restock_destination": "SELLABLE_STOCK",
                    "accepted_quantity": 1,
                    "rejected_quantity": 0,
                    "restock_quantity": 1,
                    "notes": "Đạt chuẩn GSP",
                },
                {
                    "return_item_id": it2.id,
                    "condition": "DAMAGED",
                    "restock_destination": "QUARANTINE",
                    "accepted_quantity": 0,
                    "rejected_quantity": 1,
                    "restock_quantity": 0,
                    "notes": "Vỏ hộp rách, chuyển biệt trữ",
                },
            ],
        }
        res_inspect = self.client.post(
            f"/api/v1/admin/returns/{ret.return_code}/inspect",
            json=compliant_payload,
            headers=admin_headers,
        )
        self.assertEqual(res_inspect.status_code, 200, res_inspect.text)
        self.db.refresh(ret)
        self.assertIn(ret.status, [ReturnStatus.INSPECTION_COMPLETED.value, ReturnStatus.REFUND_PENDING.value, "REFUND_PENDING"])

        # Verify exactly 1 unit was restocked to sellable stock
        self.db.refresh(stock_before)
        self.assertEqual(stock_before.quantity_on_hand, qty_before + 1)

        # 5. Strict transition prevents double inspection and duplicate restock
        res_reinspect = self.client.post(
            f"/api/v1/admin/returns/{ret.return_code}/inspect",
            json=compliant_payload,
            headers=admin_headers,
        )
        self.assertEqual(res_reinspect.status_code, 400)
        # Ensure stock was not doubled
        self.db.refresh(stock_before)
        self.assertEqual(stock_before.quantity_on_hand, qty_before + 1)

    def test_15_idempotency_replay_privacy_sanitization(self):
        """Idempotency replay without verified token strips sensitive customer and order info."""
        import uuid
        idem_key = f"IDEM-SEC-{uuid.uuid4().hex[:8]}"
        payload = {
            "customer_name": "Nguyễn Bí Mật",
            "customer_phone": "0966778899",
            "shipping_address": "Số 999 Đường Tuyệt Mật, Q.3, TP.HCM",
            "shipping_city": "TP. Hồ Chí Minh",
            "province_code": "79",
            "district_code": "760",
            "ward_code": "26734",
            "lat": 10.7769,
            "lng": 106.7009,
            "is_verified": True,
            "payment_method": "COD",
            "idempotency_key": idem_key,
            "items": [{"product_id": 9901, "sku_id": self.sku.id, "quantity": 1}],
        }
        res_first = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(res_first.status_code, 200)
        token = res_first.json()["order_token"]
        order_code = res_first.json()["order_code"]

        # Attacker replays with idempotency key and phone only, NO token
        replay_unauth = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(replay_unauth.status_code, 200)
        data_unauth = replay_unauth.json()

        # Sensitive fulfillment, address, and item data must NOT be exposed
        self.assertFalse(data_unauth.get("has_verified_token"))
        self.assertNotIn("order_token", data_unauth)
        self.assertNotIn("shipping_address", data_unauth)
        self.assertNotIn("fulfillments", data_unauth)
        self.assertNotIn("items", data_unauth)
        self.assertEqual(data_unauth["order_code"], order_code)
        self.assertTrue(data_unauth["is_idempotent_replay"])


if __name__ == "__main__":
    unittest.main()

