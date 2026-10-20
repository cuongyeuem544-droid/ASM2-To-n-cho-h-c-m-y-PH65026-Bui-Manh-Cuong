import os
import sys
import unittest
import time
import random
from decimal import Decimal
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models import (
    AuditLog,
    CanonicalProduct,
    InventoryBatch,
    Order,
    OrderFulfillment,
    OrderItem,
    PaymentTransaction,
    ProductSku,
    Warehouse,
    WarehouseBatchStock,
    StockReservation,
    PayosOrderCode,
)
from app.models.enums import PublishStatus, RegulatoryStatus, RxOtcStatus
from app.services.payos_service import PayOSPaymentService
from app.services.momo_service import MomoPaymentService
from payos.types.v2.payment_requests import CreatePaymentLinkResponse
from payos.types.webhooks.webhook import WebhookData
from tests.test_db_config import setup_isolated_test_db, teardown_isolated_test_db, TestSessionLocal


class TestPaymentGatewaysE2EFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_isolated_test_db()
        cls.SessionClass = TestSessionLocal

    @classmethod
    def tearDownClass(cls):
        teardown_isolated_test_db()

    def setUp(self):
        self.client = TestClient(app)
        self.db = self.SessionClass()

        # 1. Kho hàng
        self.wh = self.db.query(Warehouse).filter_by(code="KHO-E2E-01").first()
        if not self.wh:
            self.wh = Warehouse(
                code="KHO-E2E-01",
                name="Kho Dược E2E Test",
                address="123 Điện Biên Phủ, TP.HCM",
                lat=10.7990,
                lng=106.7110,
                is_active=True,
                is_central=True,
            )
            self.db.add(self.wh)
            self.db.commit()
            self.db.refresh(self.wh)

        # 2. Sản phẩm & Lô
        ts = int(time.time() * 1000) % 1000000
        pid = random.randint(400000, 499999)
        self.prod = CanonicalProduct(
            id=pid,
            canonical_name=f"Thuốc E2E {ts}",
            registration_number=f"VD-{pid}-26",
            regulatory_status=RegulatoryStatus.ACTIVE,
            rx_otc_status=RxOtcStatus.OTC,
            publish_status=PublishStatus.PUBLISHED,
        )
        self.db.add(self.prod)
        self.db.commit()

        from datetime import date, timedelta
        self.sku = ProductSku(
            canonical_product_id=pid,
            sku_code=f"SKU-E2E-{pid}",
            base_price=Decimal("120000.0"),
            is_default=True,
            is_active=True,
        )
        self.db.add(self.sku)
        self.db.commit()
        self.db.refresh(self.sku)

        self.batch = InventoryBatch(
            sku_id=self.sku.id,
            batch_number=f"LOT-E2E-{ts}",
            expiry_date=date.today() + timedelta(days=365),
            initial_quantity=500,
            status="ACTIVE",
        )
        self.db.add(self.batch)
        self.db.commit()
        self.db.refresh(self.batch)

        self.stock = WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=self.batch.id,
            quantity_on_hand=500,
            quantity_reserved=0,
            quantity_available=500,
        )
        self.db.add(self.stock)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    @patch("app.services.payos_service.PayOS")
    def test_complete_payos_e2e_simulation(self, MockPayOS):
        """Kịch bản E2E kiểm chứng chuỗi vòng đời payOS hoàn chỉnh."""
        mock_instance = MockPayOS.return_value

        order_code = f"ORD-E2E-PAYOS-{random.randint(100000, 999999)}"
        order = Order(
            order_code=order_code,
            customer_name="Khach Hang E2E payOS",
            customer_phone="0911223344",
            shipping_address="789 To Hien Thanh, Q10, TP.HCM",
            total_amount=Decimal("240000.0"),
            payment_method="PAYOS",
            payment_status="PENDING",
            order_status="PENDING",
            fulfillment_status="PENDING",
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)

        item = OrderItem(
            order_id=order.id,
            product_id=self.prod.id,
            product_name=self.prod.canonical_name,
            product_sku=self.sku.sku_code,
            quantity=2,
            price=Decimal("120000.0"),
            subtotal=Decimal("240000.0"),
        )
        self.db.add(item)

        resv = StockReservation(
            order_id=order.id,
            warehouse_id=self.wh.id,
            batch_id=self.batch.id,
            quantity=2,
            status="RESERVED",
        )
        self.db.add(resv)
        self.db.commit()

        from app.core.security import create_guest_order_token
        order_token = create_guest_order_token(order.order_code, order.customer_phone)

        # BƯỚC 1: Xác nhận đơn chưa thanh toán KHÔNG được coi là sẵn sàng xử lý kho
        self.assertEqual(order.payment_status, "PENDING")
        self.assertNotEqual(order.fulfillment_status, "READY_TO_PICK")

        # BƯỚC 2: Tạo link 1
        mock_link_1 = CreatePaymentLinkResponse(
            bin="970403",
            accountNumber="9990001",
            accountName="H4CARE PHARMA",
            amount=240000,
            description=f"DH {order_code}",
            orderCode=1111111,
            currency="VND",
            paymentLinkId="plink_e2e_01",
            status="PENDING",
            checkoutUrl="https://pay.payos.vn/web/test1",
            qrCode="000201...",
        )
        mock_instance.payment_requests.create.return_value = mock_link_1

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            res1 = self.client.post(
                "/api/v1/payments/payos/create",
                json={
                    "order_code": order.order_code,
                    "return_url": "http://localhost:3000/checkout/result",
                    "phone_verify": order.customer_phone,
                    "order_token": order_token,
                },
            )
            self.assertEqual(res1.status_code, 200)
            data1 = res1.json()
            code_1 = data1["payos_order_code"]
            self.assertTrue(code_1 > 0)

        # BƯỚC 3: Tạo tiếp Link 2 (Khách bấm tạo lại link / mở lại trang)
        mock_link_2 = CreatePaymentLinkResponse(
            bin="970403",
            accountNumber="9990001",
            accountName="H4CARE PHARMA",
            amount=240000,
            description=f"DH {order_code}",
            orderCode=2222222,
            currency="VND",
            paymentLinkId="plink_e2e_02",
            status="PENDING",
            checkoutUrl="https://pay.payos.vn/web/test2",
            qrCode="000201...",
        )
        mock_instance.payment_requests.create.return_value = mock_link_2

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            res2 = self.client.post(
                "/api/v1/payments/payos/create",
                json={
                    "order_code": order.order_code,
                    "return_url": "http://localhost:3000/checkout/result",
                    "phone_verify": order.customer_phone,
                    "order_token": order_token,
                },
            )
            self.assertEqual(res2.status_code, 200)
            data2 = res2.json()
            code_2 = data2["payos_order_code"]
            self.assertTrue(code_2 > 0)
            self.assertNotEqual(code_1, code_2)

        # BƯỚC 4: Kiểm tra cả hai link đều tồn tại trong PaymentTransaction
        txns = self.db.query(PaymentTransaction).filter_by(order_id=order.id).all()
        self.assertEqual(len(txns), 2)
        trans_codes = [t.provider_trans_id for t in txns]
        self.assertIn(str(code_1), trans_codes)
        self.assertIn(str(code_2), trans_codes)

        # BƯỚC 5: Webhook thanh toán thành công cho Link 1
        fake_webhook_1 = WebhookData(
            order_code=code_1,
            amount=240000,
            description=f"DH {order_code}",
            account_number="9990001",
            reference="FT_E2E_01",
            transaction_date_time="2026-10-20 14:10:00",
            currency="VND",
            payment_link_id="plink_e2e_01",
            code="00",
            desc="Thanh toan thanh cong link 1",
        )
        mock_instance.webhooks.verify.return_value = fake_webhook_1

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            wh_res1 = self.client.post(
                "/api/v1/payments/payos/webhook",
                json={"code": "00", "data": {"orderCode": code_1, "amount": 240000}},
            )
            self.assertEqual(wh_res1.status_code, 200)
            wh_data1 = wh_res1.json()
            self.assertEqual(wh_data1.get("payment_status"), "PAID")

        # Đơn hàng phải chuyển sang PAID và ALLOCATED (sẵn sàng xử lý kho)
        self.db.expire_all()
        refreshed_order = self.db.get(Order, order.id)
        self.assertEqual(refreshed_order.payment_status, "PAID")
        self.assertIn(refreshed_order.fulfillment_status, ["ALLOCATED", "READY_TO_PICK"])

        # BƯỚC 6: Chặn khách hàng hủy đơn hàng khi đã thanh toán (Trả HTTP 400)
        cancel_res = self.client.post(
            f"/api/v1/payments/orders/{order.order_code}/cancel",
            json={
                "order_code": order.order_code,
                "reason": "Khách muốn hủy sau khi đã thanh toán",
                "phone_verify": order.customer_phone,
                "order_token": order_token,
            },
        )
        self.assertEqual(cancel_res.status_code, 400)
        self.assertIn("PAID", cancel_res.json().get("detail", ""))

        # BƯỚC 7: Webhook thanh toán cho Link 2 (Khách chuyển trùng tiền)
        fake_webhook_2 = WebhookData(
            order_code=code_2,
            amount=240000,
            description=f"DH {order_code}",
            account_number="9990001",
            reference="FT_E2E_02",
            transaction_date_time="2026-10-20 14:15:00",
            currency="VND",
            payment_link_id="plink_e2e_02",
            code="00",
            desc="Thanh toan nham link 2",
        )
        mock_instance.webhooks.verify.return_value = fake_webhook_2

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            wh_res2 = self.client.post(
                "/api/v1/payments/payos/webhook",
                json={"code": "00", "data": {"orderCode": code_2, "amount": 240000}},
            )
            self.assertEqual(wh_res2.status_code, 200)
            wh_data2 = wh_res2.json()
            self.assertTrue(wh_data2.get("duplicate_payment"))
            self.assertTrue(wh_data2.get("refund_required"))

        # Giao dịch 2 phải mang trạng thái OVERPAID
        txn_2 = self.db.query(PaymentTransaction).filter_by(order_id=order.id, provider_trans_id=str(code_2)).first()
        self.assertIsNotNone(txn_2)
        self.assertEqual(txn_2.status, "OVERPAID")

        # Tồn kho không được phép bị trừ gấp đôi
        reservations = self.db.query(StockReservation).filter_by(order_id=order.id, status="RESERVED").all()
        total_reserved = sum(r.quantity for r in reservations)
        self.assertEqual(total_reserved, 2)

    def test_complete_momo_e2e_simulation(self):
        """Kịch bản E2E kiểm chứng chuỗi vòng đời MoMo hoàn chỉnh:
        1. Khách đặt đơn MOMO (PENDING).
        2. Tạo transaction MoMo.
        3. Webhook thiếu amount -> bị chặn HTTP 400.
        4. Webhook sai amount -> bị chặn HTTP 400.
        5. Webhook hợp lệ -> đơn chuyển sang PAID, kho sẵn sàng lấy hàng.
        6. Chặn hủy đơn khi đã thanh toán.
        """
        from app.core.security import create_guest_order_token

        order_code = f"ORD-E2E-MOMO-{random.randint(100000, 999999)}"
        order = Order(
            order_code=order_code,
            customer_name="Khach Hang E2E MoMo",
            customer_phone="0988112233",
            shipping_address="456 Ly Thuong Kiet, Tan Binh, TP.HCM",
            total_amount=Decimal("360000.0"),
            payment_method="MOMO",
            payment_status="PENDING",
            order_status="PENDING",
            fulfillment_status="PENDING",
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)

        order_token = create_guest_order_token(order.order_code, order.customer_phone)

        # Tạo transaction PENDING
        txn = PaymentTransaction(
            order_id=order.id,
            transaction_code=f"TXN-MOMO-{order.order_code}",
            provider="MOMO",
            amount=Decimal("360000.0"),
            currency="VND",
            status="PENDING",
            provider_trans_id="MOMO-REQ-001",
        )
        self.db.add(txn)

        resv = StockReservation(
            order_id=order.id,
            warehouse_id=self.wh.id,
            batch_id=self.batch.id,
            quantity=3,
            status="RESERVED",
        )
        self.db.add(resv)
        self.db.commit()

        # BƯỚC 1: Webhook MoMo thiếu amount hoàn toàn -> Bị từ chối HTTP 400
        with patch.object(MomoPaymentService, "verify_ipn_signature", return_value=True):
            res_no_amount = self.client.post(
                "/api/v1/payments/momo/ipn",
                json={
                    "partnerCode": "MOMO",
                    "orderId": order.order_code,
                    "requestId": "MOMO-REQ-001",
                    "transId": "23456789",
                    "resultCode": 0,
                    "message": "Success",
                    # amount missing
                },
            )
            self.assertEqual(res_no_amount.status_code, 400)
            self.assertIn("amount", res_no_amount.json()["detail"].lower())

        # BƯỚC 2: Webhook MoMo sai amount (nhận 100k thay vì 360k) -> Bị từ chối HTTP 400
        with patch.object(MomoPaymentService, "verify_ipn_signature", return_value=True):
            res_wrong_amount = self.client.post(
                "/api/v1/payments/momo/ipn",
                json={
                    "partnerCode": "MOMO",
                    "orderId": order.order_code,
                    "requestId": "MOMO-REQ-001",
                    "transId": "23456789",
                    "resultCode": 0,
                    "amount": 100000,
                    "message": "Wrong amount",
                },
            )
            self.assertEqual(res_wrong_amount.status_code, 400)
            self.assertIn("khớp", res_wrong_amount.json()["detail"].lower())

        # BƯỚC 3: Webhook MoMo chuẩn xác số tiền 360,000 đ
        with patch.object(MomoPaymentService, "verify_ipn_signature", return_value=True):
            res_valid = self.client.post(
                "/api/v1/payments/momo/ipn",
                json={
                    "partnerCode": "MOMO",
                    "orderId": order.order_code,
                    "requestId": "MOMO-REQ-001",
                    "transId": "23456789",
                    "resultCode": 0,
                    "amount": 360000,
                    "message": "Thanh toan MoMo thanh cong",
                },
            )
            self.assertEqual(res_valid.status_code, 200)

        # Kiểm tra đơn chuyển sang PAID
        self.db.expire_all()
        refreshed_order = self.db.get(Order, order.id)
        self.assertEqual(refreshed_order.payment_status, "PAID")
        self.assertIn(refreshed_order.fulfillment_status, ["ALLOCATED", "READY_TO_PICK"])

        # BƯỚC 4: Chặn hủy đơn trực tuyến
        cancel_res = self.client.post(
            f"/api/v1/payments/orders/{order.order_code}/cancel",
            json={
                "order_code": order.order_code,
                "reason": "Khách muốn hủy đơn MoMo đã trả tiền",
                "phone_verify": order.customer_phone,
                "order_token": order_token,
            },
        )
        self.assertEqual(cancel_res.status_code, 400)
        self.assertIn("PAID", cancel_res.json()["detail"])


    def test_03_checkout_rejects_discontinued_payment_methods(self):
        """Khách hàng cố tình sửa request gửi MOMO hoặc BANK_TRANSFER/VIETQR: Bị chặn ngay lập tức với HTTP 400."""
        payload_base = {
            "customer_name": "Nguyen Van Test",
            "customer_phone": "0912345678",
            "shipping_address": "Số 123 Đường Cầu Giấy, Hà Nội",
            "shipping_city": "Hà Nội",
            "fulfillment_type": "DELIVERY",
            "is_verified": True,
            "province_code": "01",
            "district_code": "009",
            "ward_code": "00142",
            "lat": 21.0362,
            "lng": 105.7906,
            "items": [
                {
                    "product_id": self.prod.id,
                    "sku_id": self.sku.id,
                    "quantity": 1,
                    "client_unit_price": 120000,
                }
            ],
        }

        # 1. Thử gửi MOMO
        payload_momo = {**payload_base, "payment_method": "MOMO"}
        res_momo = self.client.post("/api/v1/store/orders/checkout", json=payload_momo)
        self.assertEqual(res_momo.status_code, 400)
        self.assertIn("ngừng hỗ trợ", res_momo.json()["detail"].lower())

        # 2. Thử gửi BANK_TRANSFER
        payload_bt = {**payload_base, "payment_method": "BANK_TRANSFER"}
        res_bt = self.client.post("/api/v1/store/orders/checkout", json=payload_bt)
        self.assertEqual(res_bt.status_code, 400)
        self.assertIn("ngừng hỗ trợ", res_bt.json()["detail"].lower())

        # 3. Thử gửi VIETQR
        payload_vqr = {**payload_base, "payment_method": "VIETQR"}
        res_vqr = self.client.post("/api/v1/store/orders/checkout", json=payload_vqr)
        self.assertEqual(res_vqr.status_code, 400)
        self.assertIn("ngừng hỗ trợ", res_vqr.json()["detail"].lower())

        # 4. Thử gọi API tạo link MoMo trực tiếp
        res_momo_create = self.client.post("/api/v1/payments/momo/create", json={"order_code": "FAKE-ORD-01"})
        self.assertIn(res_momo_create.status_code, [400, 404])

    def test_04_checkout_allows_supported_payment_methods(self):
        """Khách hàng chọn COD hoặc PAYOS: Được chấp thuận và tạo đơn hàng hợp lệ."""
        payload_base = {
            "customer_name": "Nguyen Van Success",
            "customer_phone": "0912345679",
            "shipping_address": "Số 123 Đường Cầu Giấy, Hà Nội",
            "shipping_city": "Hà Nội",
            "fulfillment_type": "DELIVERY",
            "is_verified": True,
            "province_code": "01",
            "district_code": "009",
            "ward_code": "00142",
            "lat": 21.0362,
            "lng": 105.7906,
            "items": [
                {
                    "product_id": self.prod.id,
                    "sku_id": self.sku.id,
                    "quantity": 1,
                    "client_unit_price": 120000,
                }
            ],
        }

        # 1. Đặt đơn với COD -> Thành công
        payload_cod = {**payload_base, "payment_method": "COD", "idempotency_key": f"IDEM-COD-{time.time()}"}
        res_cod = self.client.post("/api/v1/store/orders/checkout", json=payload_cod)
        self.assertEqual(res_cod.status_code, 200, res_cod.text)
        data_cod = res_cod.json()
        self.assertEqual(data_cod["status"], "SUCCESS")

        # 2. Đặt đơn với PAYOS -> Thành công
        payload_payos = {**payload_base, "payment_method": "PAYOS", "idempotency_key": f"IDEM-PAYOS-{time.time()}"}
        res_payos = self.client.post("/api/v1/store/orders/checkout", json=payload_payos)
        self.assertEqual(res_payos.status_code, 200, res_payos.text)
        data_payos = res_payos.json()
        self.assertEqual(data_payos["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
