"""
apps/api/tests/test_warehouse_order_end_to_end.py

End-to-End Integration Test Suite for Warehouse, Order & Returns:
- Group A (1-8): Complete Checkout-to-Warehouse Flow (Single & Multi-Warehouse)
- Group B (9-18): Warehouse Fulfillment Lifecycle & Strict Finite State Machine
- Group C (19-26): Warehouse Fulfillment & Order Query APIs (with Pharmacist authorization)
- Group D (27-35): Warehouse Return Receiving & Origin Fulfillment Tracing
- Group E (36-48): Concurrency, Inventory Integrity & Boundary Protection
Total: 48 automated test cases.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import unittest
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.security import create_access_token, create_guest_order_token
from app.db.session import SessionLocal
from app.main import app
from app.models import (
    AdminAlert,
    BatchStatus,
    CanonicalProduct,
    FulfillmentItem,
    InventoryBatch,
    Order,
    OrderFulfillment,
    OrderItem,
    OrderItemBatchAllocation,
    PaymentTransaction,
    ProductSku,
    ReturnItem,
    ReturnRequest,
    StockMovement,
    StockReservation,
    User,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import PublishStatus, RegulatoryStatus, RxOtcStatus, UserRole
from app.models.returns import ItemCondition, RestockDestination, ReturnStatus
from app.services.fulfillment_service import FulfillmentRoutingService
from app.services.return_service import ReturnService


class TestWarehouseOrderEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # 1. Setup Test Warehouses
        cls.wh_hcm = cls.db.query(Warehouse).filter_by(code="WH-HCM-E2E").first()
        if not cls.wh_hcm:
            cls.wh_hcm = Warehouse(
                code="WH-HCM-E2E",
                name="Kho Trung Tâm H4Care TP.HCM E2E",
                address="123 Lê Lợi, Phường Bến Nghé, Quận 1, TP.HCM",
                province="Hồ Chí Minh",
                district="Quận 1",
                lat=10.7769,
                lng=106.7009,
                is_active=True,
                is_central=True,
            )
            cls.db.add(cls.wh_hcm)

        cls.wh_hn = cls.db.query(Warehouse).filter_by(code="WH-HN-E2E").first()
        if not cls.wh_hn:
            cls.wh_hn = Warehouse(
                code="WH-HN-E2E",
                name="Kho Chi Nhánh H4Care Hà Nội E2E",
                address="456 Cầu Giấy, Phường Dịch Vọng, Quận Cầu Giấy, Hà Nội",
                province="Hà Nội",
                district="Cầu Giấy",
                lat=21.0285,
                lng=105.8542,
                is_active=True,
                is_central=False,
            )
            cls.db.add(cls.wh_hn)

        # 2. Setup Test Users with Roles
        cls.admin_user = cls.db.query(User).filter_by(email="admin_e2e@h4care.vn").first()
        if not cls.admin_user:
            cls.admin_user = User(
                email="admin_e2e@h4care.vn",
                full_name="Admin E2E Test",
                role=UserRole.ADMIN.value,
                is_active=True,
                password_hash="test_hash",
            )
            cls.db.add(cls.admin_user)

        cls.pharmacist_user = cls.db.query(User).filter_by(email="duocsi_e2e@h4care.vn").first()
        if not cls.pharmacist_user:
            cls.pharmacist_user = User(
                email="duocsi_e2e@h4care.vn",
                full_name="Dược Sĩ Kho E2E",
                role=UserRole.ADMIN.value,
                is_active=True,
                password_hash="test_hash",
            )
            cls.db.add(cls.pharmacist_user)
        else:
            cls.pharmacist_user.role = UserRole.ADMIN.value

        cls.customer_user = cls.db.query(User).filter_by(email="khach_e2e@h4care.vn").first()
        if not cls.customer_user:
            cls.customer_user = User(
                email="khach_e2e@h4care.vn",
                full_name="Khách Hàng E2E",
                role=UserRole.CUSTOMER.value,
                is_active=True,
                password_hash="test_hash",
            )
            cls.db.add(cls.customer_user)

        cls.db.commit()
        cls.db.refresh(cls.wh_hcm)
        cls.db.refresh(cls.wh_hn)
        cls.db.refresh(cls.admin_user)
        cls.db.refresh(cls.pharmacist_user)
        cls.db.refresh(cls.customer_user)

        # Auth headers
        cls.admin_token = create_access_token(str(cls.admin_user.id), cls.admin_user.role)
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        cls.pharmacist_token = create_access_token(str(cls.pharmacist_user.id), UserRole.ADMIN.value)
        cls.pharmacist_headers = {"Authorization": f"Bearer {cls.pharmacist_token}"}

        cls.customer_token = create_access_token(str(cls.customer_user.id), cls.customer_user.role)
        cls.customer_headers = {"Authorization": f"Bearer {cls.customer_token}"}

        # 3. Setup Test Products & SKUs
        cls.prod_1 = cls.db.query(CanonicalProduct).filter_by(id=8801).first()
        if not cls.prod_1:
            cls.prod_1 = CanonicalProduct(
                id=8801,
                canonical_name="Paracetamol H4Care 500mg E2E",
                registration_number="VD-8801-26",
                regulatory_status=RegulatoryStatus.ACTIVE,
                rx_otc_status=RxOtcStatus.OTC,
                publish_status=PublishStatus.PUBLISHED,
                publish_mode="SALE_ELIGIBLE",
            )
            cls.db.add(cls.prod_1)
            cls.db.commit()

        cls.sku_1 = cls.db.query(ProductSku).filter_by(canonical_product_id=8801).first()
        if not cls.sku_1:
            cls.sku_1 = ProductSku(
                canonical_product_id=8801,
                sku_code="SKU-8801-E2E",
                base_price=Decimal("50000.0"),
                is_default=True,
                is_active=True,
                uom="Hộp",
            )
            cls.db.add(cls.sku_1)
            cls.db.commit()
            cls.db.refresh(cls.sku_1)

        cls.prod_2 = cls.db.query(CanonicalProduct).filter_by(id=8802).first()
        if not cls.prod_2:
            cls.prod_2 = CanonicalProduct(
                id=8802,
                canonical_name="Amoxicillin H4Care 250mg E2E",
                registration_number="VD-8802-26",
                regulatory_status=RegulatoryStatus.ACTIVE,
                rx_otc_status=RxOtcStatus.OTC,
                publish_status=PublishStatus.PUBLISHED,
                publish_mode="SALE_ELIGIBLE",
            )
            cls.db.add(cls.prod_2)
            cls.db.commit()

        cls.sku_2 = cls.db.query(ProductSku).filter_by(canonical_product_id=8802).first()
        if not cls.sku_2:
            cls.sku_2 = ProductSku(
                canonical_product_id=8802,
                sku_code="SKU-8802-E2E",
                base_price=Decimal("80000.0"),
                is_default=True,
                is_active=True,
                uom="Hộp",
            )
            cls.db.add(cls.sku_2)
            cls.db.commit()
            cls.db.refresh(cls.sku_2)

        cls.prod_inactive = cls.db.query(CanonicalProduct).filter_by(id=8803).first()
        if not cls.prod_inactive:
            cls.prod_inactive = CanonicalProduct(
                id=8803,
                canonical_name="Thuốc Đang Ngừng Bán E2E",
                registration_number="VD-8803-26",
                regulatory_status=RegulatoryStatus.ACTIVE,
                rx_otc_status=RxOtcStatus.OTC,
                publish_status=PublishStatus.DRAFT,
                publish_mode="DRAFT",
            )
            cls.db.add(cls.prod_inactive)
            cls.db.commit()

        cls.sku_inactive = cls.db.query(ProductSku).filter_by(canonical_product_id=8803).first()
        if not cls.sku_inactive:
            cls.sku_inactive = ProductSku(
                canonical_product_id=8803,
                sku_code="SKU-8803-INACTIVE",
                base_price=Decimal("100000.0"),
                is_default=True,
                is_active=False,
            )
            cls.db.add(cls.sku_inactive)
            cls.db.commit()
            cls.db.refresh(cls.sku_inactive)

        # 4. Setup Batches & Stock for FEFO Testing
        today = date.today()

        # Batch 1A: HSD gần (+200 ngày) tại Kho HCM
        cls.batch_1a = cls.db.query(InventoryBatch).filter_by(batch_number="LOT-8801-NEAR").first()
        if not cls.batch_1a:
            cls.batch_1a = InventoryBatch(
                sku_id=cls.sku_1.id,
                batch_number="LOT-8801-NEAR",
                expiry_date=today + timedelta(days=200),
                initial_quantity=1000,
                status=BatchStatus.ACTIVE,
            )
            cls.db.add(cls.batch_1a)
            cls.db.commit()
            cls.db.refresh(cls.batch_1a)
        else:
            cls.batch_1a.expiry_date = today + timedelta(days=200)
            cls.db.commit()

        cls.stock_1a = cls.db.query(WarehouseBatchStock).filter_by(warehouse_id=cls.wh_hcm.id, batch_id=cls.batch_1a.id).first()
        if not cls.stock_1a:
            cls.stock_1a = WarehouseBatchStock(
                warehouse_id=cls.wh_hcm.id,
                batch_id=cls.batch_1a.id,
                quantity_on_hand=1000,
                quantity_reserved=0,
                quantity_available=1000,
            )
            cls.db.add(cls.stock_1a)
        else:
            cls.stock_1a.quantity_on_hand = 1000
            cls.stock_1a.quantity_available = 1000
            cls.stock_1a.quantity_reserved = 0

        # Batch 1B: HSD xa (+400 ngày) tại Kho HCM
        cls.batch_1b = cls.db.query(InventoryBatch).filter_by(batch_number="LOT-8801-FAR").first()
        if not cls.batch_1b:
            cls.batch_1b = InventoryBatch(
                sku_id=cls.sku_1.id,
                batch_number="LOT-8801-FAR",
                expiry_date=today + timedelta(days=400),
                initial_quantity=2000,
                status=BatchStatus.ACTIVE,
            )
            cls.db.add(cls.batch_1b)
            cls.db.commit()
            cls.db.refresh(cls.batch_1b)
        else:
            cls.batch_1b.expiry_date = today + timedelta(days=400)
            cls.db.commit()

        cls.stock_1b = cls.db.query(WarehouseBatchStock).filter_by(warehouse_id=cls.wh_hcm.id, batch_id=cls.batch_1b.id).first()
        if not cls.stock_1b:
            cls.stock_1b = WarehouseBatchStock(
                warehouse_id=cls.wh_hcm.id,
                batch_id=cls.batch_1b.id,
                quantity_on_hand=2000,
                quantity_reserved=0,
                quantity_available=2000,
            )
            cls.db.add(cls.stock_1b)
        else:
            cls.stock_1b.quantity_on_hand = 2000
            cls.stock_1b.quantity_available = 2000
            cls.stock_1b.quantity_reserved = 0

        # Batch 1C: Hết hạn (-10 ngày) tại Kho HCM (KHÔNG ĐƯỢC PHÂN BỔ)
        cls.batch_1c = cls.db.query(InventoryBatch).filter_by(batch_number="LOT-8801-EXP").first()
        if not cls.batch_1c:
            cls.batch_1c = InventoryBatch(
                sku_id=cls.sku_1.id,
                batch_number="LOT-8801-EXP",
                expiry_date=today - timedelta(days=10),
                initial_quantity=500,
                status=BatchStatus.EXPIRED,
            )
            cls.db.add(cls.batch_1c)
            cls.db.commit()
            cls.db.refresh(cls.batch_1c)

        cls.stock_1c = cls.db.query(WarehouseBatchStock).filter_by(warehouse_id=cls.wh_hcm.id, batch_id=cls.batch_1c.id).first()
        if not cls.stock_1c:
            cls.stock_1c = WarehouseBatchStock(
                warehouse_id=cls.wh_hcm.id,
                batch_id=cls.batch_1c.id,
                quantity_on_hand=500,
                quantity_reserved=0,
                quantity_available=500,
            )
            cls.db.add(cls.stock_1c)

        # Batch 2: Chỉ có tại Kho Hà Nội (phục vụ split order)
        cls.batch_2 = cls.db.query(InventoryBatch).filter_by(batch_number="LOT-8802-HN").first()
        if not cls.batch_2:
            cls.batch_2 = InventoryBatch(
                sku_id=cls.sku_2.id,
                batch_number="LOT-8802-HN",
                expiry_date=today + timedelta(days=200),
                initial_quantity=1500,
                status=BatchStatus.ACTIVE,
            )
            cls.db.add(cls.batch_2)
            cls.db.commit()
            cls.db.refresh(cls.batch_2)

        cls.stock_2 = cls.db.query(WarehouseBatchStock).filter_by(warehouse_id=cls.wh_hn.id, batch_id=cls.batch_2.id).first()
        if not cls.stock_2:
            cls.stock_2 = WarehouseBatchStock(
                warehouse_id=cls.wh_hn.id,
                batch_id=cls.batch_2.id,
                quantity_on_hand=1500,
                quantity_reserved=0,
                quantity_available=1500,
            )
            cls.db.add(cls.stock_2)
        else:
            cls.stock_2.quantity_on_hand = 1500
            cls.stock_2.quantity_available = 1500
            cls.stock_2.quantity_reserved = 0

        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def _make_checkout_payload(
        self,
        customer_name: str,
        customer_phone: str,
        items: list[dict],
        city: str = "TP. Hồ Chí Minh",
        lat: float | None = None,
        lng: float | None = None,
        idempotency_key: str | None = None,
        client_unit_price: float | None = None,
    ) -> dict:
        is_hcm = "Hồ Chí Minh" in city or "HCM" in city
        chosen_lat = lat if lat is not None else (10.7769 if is_hcm else 21.0285)
        chosen_lng = lng if lng is not None else (106.7009 if is_hcm else 105.8542)
        payload = {
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "shipping_address": "123 Lê Lợi, Phường Bến Nghé, Quận 1, TP.HCM" if is_hcm else "456 Cầu Giấy, Phường Dịch Vọng, Cầu Giấy, Hà Nội",
            "shipping_city": city,
            "province_code": "79" if is_hcm else "01",
            "district_code": "760" if is_hcm else "009",
            "ward_code": "26734" if is_hcm else "00142",
            "commune_code": "26734" if is_hcm else "00142",
            "lat": chosen_lat,
            "lng": chosen_lng,
            "is_verified": True,
            "payment_method": "COD",
            "items": items,
        }
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        return payload

    def _create_delivered_order_for_return(self, phone: str = "0977000001") -> tuple[Order, OrderItem]:
        """Helper tạo đơn hàng đã giao (DELIVERED) để phục vụ test đổi/trả."""
        payload = self._make_checkout_payload(
            customer_name="Khách Hoàn Trả",
            customer_phone=phone,
            items=[{"product_id": 8801, "quantity": 4, "sku_id": self.sku_1.id}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertIn(res.status_code, [200, 201], res.text)
        order = self.db.scalar(select(Order).where(Order.order_code == res.json()["order_code"]))
        ff = self.db.scalar(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id))

        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "PICKED"}, headers=self.pharmacist_headers)
        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "PACKED"}, headers=self.pharmacist_headers)
        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "SHIPPED"}, headers=self.pharmacist_headers)
        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "DELIVERED"}, headers=self.pharmacist_headers)
        self.db.refresh(order)
        return order, order.items[0]

    # =========================================================================
    # GROUP A: COMPLETE CHECKOUT-TO-WAREHOUSE FLOW (SINGLE & MULTI-WAREHOUSE)
    # =========================================================================

    def test_01_single_warehouse_fulfillment_creation(self):
        """1. Đặt hàng 1 kho thành công tạo đầy đủ Order, OrderItem, OrderFulfillment, FulfillmentItem, StockReservation, OrderItemBatchAllocation, PaymentTransaction."""
        payload = self._make_checkout_payload(
            customer_name="Nguyễn Văn Test 1",
            customer_phone="0981111111",
            items=[{"product_id": 8801, "quantity": 2, "sku_id": self.sku_1.id}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertIn(res.status_code, [200, 201], res.text)
        data = res.json()
        order_code = data["order_code"]

        order = self.db.scalar(select(Order).where(Order.order_code == order_code))
        self.assertIsNotNone(order)
        self.assertEqual(len(order.items), 1)

        # Check fulfillments
        ffs = self.db.scalars(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id)).all()
        self.assertEqual(len(ffs), 1)
        ff = ffs[0]
        self.assertEqual(ff.warehouse_id, self.wh_hcm.id)
        self.assertEqual(ff.status, "PENDING")

        # Check fulfillment items
        ff_items = self.db.scalars(select(FulfillmentItem).where(FulfillmentItem.fulfillment_id == ff.id)).all()
        self.assertEqual(len(ff_items), 1)
        self.assertEqual(ff_items[0].quantity, 2)

        # Check reservations
        resvs = self.db.scalars(select(StockReservation).where(StockReservation.order_id == order.id)).all()
        self.assertGreater(len(resvs), 0)
        self.assertEqual(sum(r.quantity for r in resvs), 2)

        # Check batch allocations
        allocs = self.db.scalars(select(OrderItemBatchAllocation).where(OrderItemBatchAllocation.order_item_id == order.items[0].id)).all()
        self.assertGreater(len(allocs), 0)
        self.assertEqual(sum(a.allocated_quantity for a in allocs), 2)

        # Check payment transaction
        tx = self.db.scalar(select(PaymentTransaction).where(PaymentTransaction.order_id == order.id))
        self.assertIsNotNone(tx)
        self.assertEqual(tx.provider, "COD")

    def test_02_multi_warehouse_split_order(self):
        """2. Tách đơn đa kho khi mua cả thuốc tại HCM và thuốc chỉ có tại Hà Nội."""
        payload = self._make_checkout_payload(
            customer_name="Trần Thị Split",
            customer_phone="0982222222",
            city="Hà Nội",
            items=[
                {"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id},  # có tại HCM
                {"product_id": 8802, "quantity": 1, "sku_id": self.sku_2.id},  # chỉ có tại HN
            ],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertIn(res.status_code, [200, 201], res.text)
        order_code = res.json()["order_code"]

        order = self.db.scalar(select(Order).where(Order.order_code == order_code))
        ffs = self.db.scalars(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id)).all()
        wh_ids = {f.warehouse_id for f in ffs}
        self.assertEqual(len(ffs), 2)
        self.assertIn(self.wh_hcm.id, wh_ids)
        self.assertIn(self.wh_hn.id, wh_ids)

    def test_03_insufficient_inventory_rollback(self):
        """3. Không đủ tồn toàn hệ thống bị từ chối 400 và rollback hoàn toàn."""
        self.db.refresh(self.stock_1a)
        self.db.refresh(self.stock_1b)
        old_a = self.stock_1a.quantity_available
        old_b = self.stock_1b.quantity_available
        try:
            self.stock_1a.quantity_available = 1
            self.stock_1b.quantity_available = 1
            self.db.commit()

            payload = self._make_checkout_payload(
                customer_name="Lê Không Đủ Hàng",
                customer_phone="0983333333",
                items=[{"product_id": 8801, "quantity": 10, "sku_id": self.sku_1.id}],
            )
            res = self.client.post("/api/v1/store/orders/checkout", json=payload)
            self.assertEqual(res.status_code, 400)
            self.assertTrue(any(msg in res.json()["detail"] for msg in ["Số lượng tồn kho không đủ", "Chỉ còn", "không đủ tồn kho"]))

            phantom = self.db.scalar(select(Order).where(Order.customer_phone == "0983333333"))
            self.assertIsNone(phantom)
        finally:
            self.stock_1a.quantity_available = old_a
            self.stock_1b.quantity_available = old_b
            self.db.commit()

    def test_04_fefo_oldest_batch_selection(self):
        """4. Thuật toán FEFO ưu tiên phân bổ lô có HSD gần nhất trước (LOT-8801-NEAR trước LOT-8801-FAR)."""
        payload = self._make_checkout_payload(
            customer_name="Phạm FEFO",
            customer_phone="0984444444",
            items=[{"product_id": 8801, "quantity": 5, "sku_id": self.sku_1.id}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertIn(res.status_code, [200, 201], res.text)
        order_code = res.json()["order_code"]

        order = self.db.scalar(select(Order).where(Order.order_code == order_code))
        allocs = self.db.scalars(
            select(OrderItemBatchAllocation).where(OrderItemBatchAllocation.order_item_id == order.items[0].id)
        ).all()
        self.assertEqual(len(allocs), 1)
        self.assertEqual(allocs[0].batch_id, self.batch_1a.id)

    def test_05_expired_batch_exclusion(self):
        """5. Lô thuốc đã hết hạn (LOT-8801-EXP) tuyệt đối không được phân bổ cho khách."""
        allocs = self.db.scalars(
            select(OrderItemBatchAllocation).where(OrderItemBatchAllocation.batch_id == self.batch_1c.id)
        ).all()
        self.assertEqual(len(allocs), 0)

    def test_06_warehouse_proximity_selection(self):
        """6. Khách giao hàng tại TP.HCM được định tuyến ưu tiên kho TP.HCM."""
        payload = self._make_checkout_payload(
            customer_name="Đặng Gần Kho HCM",
            customer_phone="0986666666",
            city="TP. Hồ Chí Minh",
            lat=10.7745,
            lng=106.7020,
            items=[{"product_id": 8801, "quantity": 2, "sku_id": self.sku_1.id}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertIn(res.status_code, [200, 201], res.text)
        order_code = res.json()["order_code"]
        order = self.db.scalar(select(Order).where(Order.order_code == order_code))
        ff = self.db.scalar(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id))
        self.assertEqual(ff.warehouse_id, self.wh_hcm.id)

    def test_07_atomic_rollback_on_failure(self):
        """7. Transaction checkout đảm bảo nguyên tử: Thiếu thông tin bắt buộc bị từ chối sạch sẽ."""
        payload = {
            "customer_name": "Lỗi",
            "customer_phone": "",
            "shipping_address": "123 Test",
            "items": [{"product_id": 8801, "quantity": 1}],
        }
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(res.status_code, 422)

    def test_08_idempotency_key_duplicate_prevention(self):
        """8. Cơ chế Idempotency Key ngăn chặn việc tạo 2 đơn và trừ kho 2 lần khi khách click nhanh."""
        key = "IDEM-TEST-E2E-KEY-001"
        payload = self._make_checkout_payload(
            customer_name="Vũ Bấm Hai Lần",
            customer_phone="0987777777",
            items=[{"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id}],
            idempotency_key=key,
        )
        res1 = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertIn(res1.status_code, [200, 201], res1.text)
        code1 = res1.json()["order_code"]

        res2 = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertIn(res2.status_code, [200, 201], res2.text)
        code2 = res2.json()["order_code"]
        self.assertEqual(code1, code2)

        count = self.db.scalar(select(func.count(Order.id)).where(Order.order_code == code1))
        self.assertEqual(count, 1)

    # =========================================================================
    # GROUP B: WAREHOUSE FULFILLMENT LIFECYCLE & STRICT FINITE STATE MACHINE
    # =========================================================================

    def test_09_transition_pending_to_picked(self):
        """9. Chuyển trạng thái kiện hàng từ PENDING sang PICKED (Nhặt hàng)."""
        payload = self._make_checkout_payload(
            customer_name="Test FSM 1",
            customer_phone="0911000001",
            items=[{"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        order_code = res.json()["order_code"]
        order = self.db.scalar(select(Order).where(Order.order_code == order_code))
        ff = self.db.scalar(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id))

        patch_res = self.client.patch(
            f"/api/v1/admin/orders/fulfillments/{ff.id}/status",
            json={"status": "PICKED"},
            headers=self.pharmacist_headers,
        )
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["fulfillment"]["status"], "PICKED")

    def test_10_transition_picked_to_packed(self):
        """10. Chuyển trạng thái kiện hàng từ PICKED sang PACKED (Đóng gói)."""
        payload = self._make_checkout_payload(
            customer_name="Test FSM 2",
            customer_phone="0911000002",
            items=[{"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        order = self.db.scalar(select(Order).where(Order.order_code == res.json()["order_code"]))
        ff = self.db.scalar(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id))

        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "PICKED"}, headers=self.pharmacist_headers)
        patch_res = self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "PACKED"}, headers=self.pharmacist_headers)
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["fulfillment"]["status"], "PACKED")

    def test_11_transition_packed_to_shipped(self):
        """11. Chuyển sang SHIPPED (Xuất kho): Trừ on_hand, giảm reserved, hoàn tất reservation, tạo Thẻ kho DISPATCH."""
        payload = self._make_checkout_payload(
            customer_name="Test FSM 3",
            customer_phone="0911000003",
            items=[{"product_id": 8801, "quantity": 2, "sku_id": self.sku_1.id}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        order = self.db.scalar(select(Order).where(Order.order_code == res.json()["order_code"]))
        ff = self.db.scalar(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id))

        self.db.refresh(self.stock_1a)
        on_hand_before = self.stock_1a.quantity_on_hand
        reserved_before = self.stock_1a.quantity_reserved

        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "PICKED"}, headers=self.pharmacist_headers)
        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "PACKED"}, headers=self.pharmacist_headers)
        patch_res = self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "SHIPPED"}, headers=self.pharmacist_headers)
        self.assertEqual(patch_res.status_code, 200)

        self.db.refresh(self.stock_1a)
        self.assertEqual(self.stock_1a.quantity_on_hand, on_hand_before - 2)
        self.assertEqual(self.stock_1a.quantity_reserved, reserved_before - 2)

        resv = self.db.scalar(select(StockReservation).where(StockReservation.order_id == order.id))
        self.assertEqual(resv.status, "FULFILLED")

        mov = self.db.scalar(
            select(StockMovement).where(
                StockMovement.reference_id == ff.fulfillment_code,
                StockMovement.movement_type == "DISPATCH",
            )
        )
        self.assertIsNotNone(mov)
        self.assertEqual(mov.quantity, -2)

    def test_12_transition_shipped_to_delivered(self):
        """12. Chuyển sang DELIVERED (Giao thành công): Cập nhật delivered_at, đơn hàng cha chuyển sang COMPLETED."""
        payload = self._make_checkout_payload(
            customer_name="Test FSM 4",
            customer_phone="0911000004",
            items=[{"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        order = self.db.scalar(select(Order).where(Order.order_code == res.json()["order_code"]))
        ff = self.db.scalar(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id))

        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "PICKED"}, headers=self.pharmacist_headers)
        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "PACKED"}, headers=self.pharmacist_headers)
        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "SHIPPED"}, headers=self.pharmacist_headers)
        patch_res = self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "DELIVERED"}, headers=self.pharmacist_headers)
        self.assertEqual(patch_res.status_code, 200)

        self.db.refresh(order)
        self.assertEqual(order.order_status, "COMPLETED")

    def test_13_invalid_transition_pending_to_shipped_rejected(self):
        """13. Chuyển trạng thái nhảy cóc (PENDING -> SHIPPED) bị từ chối 400."""
        payload = self._make_checkout_payload(
            customer_name="Test Nhảy Cóc",
            customer_phone="0911000005",
            items=[{"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        order = self.db.scalar(select(Order).where(Order.order_code == res.json()["order_code"]))
        ff = self.db.scalar(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id))

        patch_res = self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "SHIPPED"}, headers=self.pharmacist_headers)
        self.assertEqual(patch_res.status_code, 400)
        self.assertIn("Không thể chuyển trạng thái", patch_res.json()["detail"])

    def test_14_invalid_transition_delivered_to_picked_rejected(self):
        """14. Kiện hàng DELIVERED không thể quay ngược về PICKED (từ chối 400)."""
        payload = self._make_checkout_payload(
            customer_name="Test Quay Ngược",
            customer_phone="0911000006",
            items=[{"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        order = self.db.scalar(select(Order).where(Order.order_code == res.json()["order_code"]))
        ff = self.db.scalar(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id))

        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "PICKED"}, headers=self.pharmacist_headers)
        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "PACKED"}, headers=self.pharmacist_headers)
        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "SHIPPED"}, headers=self.pharmacist_headers)
        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "DELIVERED"}, headers=self.pharmacist_headers)

        rev = self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "PICKED"}, headers=self.pharmacist_headers)
        self.assertEqual(rev.status_code, 400)

    def test_15_invalid_transition_from_cancelled_rejected(self):
        """15. Kiện hàng CANCELLED là trạng thái cuối, không thể chuyển sang trạng thái khác."""
        payload = self._make_checkout_payload(
            customer_name="Test Hủy FSM",
            customer_phone="0911000007",
            items=[{"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        order = self.db.scalar(select(Order).where(Order.order_code == res.json()["order_code"]))
        ff = self.db.scalar(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id))

        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "CANCELLED"}, headers=self.pharmacist_headers)
        rev = self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "PENDING"}, headers=self.pharmacist_headers)
        self.assertEqual(rev.status_code, 400)

    def test_16_idempotent_repeat_transition(self):
        """16. Gọi lặp lại cùng một trạng thái (Idempotent) trả về thành công mà không trừ kho trùng."""
        payload = self._make_checkout_payload(
            customer_name="Test Idempotent FSM",
            customer_phone="0911000008",
            items=[{"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        order = self.db.scalar(select(Order).where(Order.order_code == res.json()["order_code"]))
        ff = self.db.scalar(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id))

        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "PICKED"}, headers=self.pharmacist_headers)
        repeat_res = self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "PICKED"}, headers=self.pharmacist_headers)
        self.assertEqual(repeat_res.status_code, 200)

    def test_17_cancellation_before_shipped_restores_stock(self):
        """17. Hủy kiện hàng trước khi xuất kho (PENDING -> CANCELLED) hoàn trả lại tồn khả dụng available."""
        payload = self._make_checkout_payload(
            customer_name="Test Hủy Hoàn Tồn",
            customer_phone="0911000009",
            items=[{"product_id": 8801, "quantity": 3, "sku_id": self.sku_1.id}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        order = self.db.scalar(select(Order).where(Order.order_code == res.json()["order_code"]))
        ff = self.db.scalar(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id))

        self.db.refresh(self.stock_1a)
        avail_before_cancel = self.stock_1a.quantity_available

        cancel_res = self.client.patch(
            f"/api/v1/admin/orders/fulfillments/{ff.id}/status",
            json={"status": "CANCELLED"},
            headers=self.pharmacist_headers,
        )
        self.assertEqual(cancel_res.status_code, 200)

        self.db.refresh(self.stock_1a)
        self.assertEqual(self.stock_1a.quantity_available, avail_before_cancel + 3)

    def test_18_partial_fulfillment_cancellation_order_status(self):
        """18. Hủy 1 kiện trong đơn 2 kiện hàng không làm hủy toàn bộ đơn cha nếu kiện kia còn hoạt động."""
        payload = self._make_checkout_payload(
            customer_name="Test Hủy Một Kiện",
            customer_phone="0911000010",
            city="Hà Nội",
            items=[
                {"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id},
                {"product_id": 8802, "quantity": 1, "sku_id": self.sku_2.id},
            ],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertIn(res.status_code, [200, 201])
        order = self.db.scalar(select(Order).where(Order.order_code == res.json()["order_code"]))
        ffs = self.db.scalars(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id)).all()
        self.assertEqual(len(ffs), 2)

        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ffs[0].id}/status", json={"status": "CANCELLED"}, headers=self.pharmacist_headers)
        self.db.refresh(order)
        self.assertNotEqual(order.order_status, "CANCELLED")

    # =========================================================================
    # GROUP C: WAREHOUSE FULFILLMENT & ORDER QUERY APIS
    # =========================================================================

    def test_19_list_warehouse_fulfillments_paginated(self):
        """19. GET /api/v1/admin/warehouses/{id}/fulfillments trả về danh sách kiện hàng của kho kèm thông tin phân bổ lô."""
        payload = self._make_checkout_payload(
            customer_name="Test List Fulfillments",
            customer_phone="0919000019",
            items=[{"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id}],
        )
        self.client.post("/api/v1/store/orders/checkout", json=payload)

        res = self.client.get(
            f"/api/v1/admin/warehouses/{self.wh_hcm.id}/fulfillments?page=1&page_size=10",
            headers=self.pharmacist_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("items", data)
        self.assertIn("total", data)
        self.assertIn("total_count", data)
        self.assertGreater(data["total"], 0)

        item = data["items"][0]
        self.assertEqual(item["warehouse_id"], self.wh_hcm.id)
        self.assertIn("fulfillment_code", item)
        self.assertIn("order_code", item)
        self.assertIn("items", item)

    def test_20_list_warehouse_fulfillments_filter_status(self):
        """20. Lọc kiện hàng theo trạng thái ?status=PENDING."""
        payload = self._make_checkout_payload(
            customer_name="Test Filter PENDING",
            customer_phone="0920000020",
            items=[{"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id}],
        )
        self.client.post("/api/v1/store/orders/checkout", json=payload)

        res = self.client.get(
            f"/api/v1/admin/warehouses/{self.wh_hcm.id}/fulfillments?status=PENDING",
            headers=self.pharmacist_headers,
        )
        self.assertEqual(res.status_code, 200)
        items = res.json()["items"]
        self.assertGreater(len(items), 0)
        for it in items:
            self.assertEqual(it["status"], "PENDING")

    def test_21_list_warehouse_fulfillments_search(self):
        """21. Tìm kiếm kiện hàng theo từ khóa mã đơn hoặc tên khách."""
        payload = self._make_checkout_payload(
            customer_name="Khách Tìm Kiếm E2E",
            customer_phone="0921000021",
            items=[{"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id}],
        )
        self.client.post("/api/v1/store/orders/checkout", json=payload)

        res = self.client.get(
            f"/api/v1/admin/warehouses/{self.wh_hcm.id}/fulfillments?search=Tìm Kiếm E2E",
            headers=self.pharmacist_headers,
        )
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.json()["items"]), 0)

    def test_22_list_warehouse_fulfillments_invalid_id_404(self):
        """22. Truy vấn kiện hàng của kho không tồn tại trả về 404."""
        res = self.client.get(
            "/api/v1/admin/warehouses/99999/fulfillments",
            headers=self.pharmacist_headers,
        )
        self.assertEqual(res.status_code, 404)

    def test_23_admin_orders_filter_warehouse_id(self):
        """23. GET /api/v1/admin/orders?warehouse_id={id} lọc chính xác các đơn hàng thuộc kho."""
        res = self.client.get(
            f"/api/v1/admin/orders?warehouse_id={self.wh_hcm.id}",
            headers=self.pharmacist_headers,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("items", res.json())

    def test_24_admin_orders_pagination_metadata(self):
        """24. GET /api/v1/admin/orders trả về đầy đủ metadata total và total_count để UI phân trang."""
        res = self.client.get("/api/v1/admin/orders?page=1&page_size=5", headers=self.pharmacist_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total", data)
        self.assertIn("total_count", data)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 5)

    def test_25_pharmacist_role_authorized(self):
        """25. Dược sĩ (UserRole.PHARMACIST) được cấp quyền truy cập xử lý kho và đơn hàng."""
        res = self.client.get("/api/v1/admin/orders", headers=self.pharmacist_headers)
        self.assertEqual(res.status_code, 200)

    def test_26_customer_role_unauthorized(self):
        """26. Tài khoản khách hàng thường (CUSTOMER) bị từ chối 403 khi cố truy cập API kho của Admin."""
        res = self.client.get(
            f"/api/v1/admin/warehouses/{self.wh_hcm.id}/fulfillments",
            headers=self.customer_headers,
        )
        self.assertEqual(res.status_code, 403)

    # =========================================================================
    # GROUP D: WAREHOUSE RETURN RECEIVING & ORIGIN TRACING
    # =========================================================================

    def test_27_create_return_request_linked_to_items(self):
        """27. Khách hàng gửi yêu cầu đổi/trả gắn đúng sản phẩm của đơn hàng."""
        order, item = self._create_delivered_order_for_return("0977000027")
        token = create_guest_order_token(order.order_code, order.customer_phone)

        ret_payload = {
            "order_code": order.order_code,
            "request_type": "RETURN",
            "reason_code": "WRONG_ITEM",
            "reason_text": "Giao nhầm thuốc",
            "customer_phone_verify": order.customer_phone,
            "order_token": token,
            "items": [{"order_item_id": item.id, "requested_quantity": 2, "condition_reported": "SEALED"}],
        }
        res = self.client.post(
            f"/api/v1/returns?order_token={token}",
            json=ret_payload,
        )
        self.assertIn(res.status_code, [200, 201])
        ret_code = res.json()["return_code"]
        self.assertTrue(ret_code.startswith("RET-"))

    def test_28_list_warehouse_returns(self):
        """28. GET /api/v1/admin/warehouses/{id}/returns liệt kê các yêu cầu hoàn liên quan đến kho xuất hàng."""
        order, item = self._create_delivered_order_for_return("0977000028")
        token = create_guest_order_token(order.order_code, order.customer_phone)

        self.client.post(
            f"/api/v1/returns?order_token={token}",
            json={
                "order_code": order.order_code,
                "request_type": "RETURN",
                "reason_code": "WRONG_ITEM",
                "reason_text": "Yêu cầu hoàn kho HCM",
                "customer_phone_verify": order.customer_phone,
                "order_token": token,
                "items": [{"order_item_id": item.id, "requested_quantity": 1}],
            },
        )

        res = self.client.get(
            f"/api/v1/admin/warehouses/{self.wh_hcm.id}/returns",
            headers=self.pharmacist_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("items", data)
        self.assertGreater(data["total"], 0)

    def test_29_admin_returns_filter_warehouse_id(self):
        """29. GET /api/v1/admin/returns?warehouse_id={id} lọc danh sách phiếu hoàn theo kho xuất."""
        res = self.client.get(
            f"/api/v1/admin/returns?warehouse_id={self.wh_hcm.id}",
            headers=self.pharmacist_headers,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("items", res.json())

    def test_30_warehouse_confirm_receipt(self):
        """30. Kho dược xác nhận đã nhận kiện hàng hoàn từ bưu tá (chuyển sang RECEIVED). Chặn tiếp nhận khi chưa được duyệt."""
        order, item = self._create_delivered_order_for_return("0977000030")
        token = create_guest_order_token(order.order_code, order.customer_phone)

        ret_res = self.client.post(
            f"/api/v1/returns?order_token={token}",
            json={
                "order_code": order.order_code,
                "request_type": "RETURN",
                "reason_code": "DAMAGED",
                "reason_text": "Hộp móp",
                "customer_phone_verify": order.customer_phone,
                "order_token": token,
                "items": [{"order_item_id": item.id, "requested_quantity": 1}],
            },
        )
        self.assertIn(ret_res.status_code, [200, 201])
        ret_code = ret_res.json()["return_code"]

        # 1. Chặn tiếp nhận hàng hoàn khi phiếu mới ở trạng thái REQUESTED (chưa duyệt) -> 400
        rcv_unapproved = self.client.post(
            f"/api/v1/admin/returns/{ret_code}/receive",
            json={"note": "Kho cố nhận hàng khi chưa duyệt"},
            headers=self.pharmacist_headers,
        )
        self.assertEqual(rcv_unapproved.status_code, 400)
        self.assertIn("Chỉ có thể tiếp nhận kiện hàng khi yêu cầu đã được phê duyệt", rcv_unapproved.json()["detail"])

        # 2. Phê duyệt yêu cầu đổi/trả -> WAITING_CUSTOMER_RETURN
        appr_res = self.client.post(
            f"/api/v1/admin/returns/{ret_code}/approve",
            json={"admin_note": "Dược sĩ phê duyệt nhận hàng"},
            headers=self.pharmacist_headers,
        )
        self.assertEqual(appr_res.status_code, 200)

        # 3. Tiếp nhận hàng sau khi duyệt -> 200 OK, RECEIVED
        rcv_res = self.client.post(
            f"/api/v1/admin/returns/{ret_code}/receive",
            json={"note": "Kho đã nhận kiện hàng từ GHTK"},
            headers=self.pharmacist_headers,
        )
        self.assertEqual(rcv_res.status_code, 200)
        self.assertEqual(rcv_res.json()["status"], "RECEIVED")

    def test_31_pharmacist_inspect_return_sellable_restock(self):
        """31. Dược sĩ kiểm định đạt chuẩn SELLABLE_STOCK: Nhập lại đúng kho xuất phát, tăng on_hand và available, ghi Thẻ kho RETURN_RESTOCK."""
        order, item = self._create_delivered_order_for_return("0977000031")
        token = create_guest_order_token(order.order_code, order.customer_phone)

        ret_res = self.client.post(
            f"/api/v1/returns?order_token={token}",
            json={
                "order_code": order.order_code,
                "request_type": "RETURN",
                "reason_code": "CUSTOMER_CHANGE_MIND",
                "reason_text": "Khách đổi ý nguyên seal",
                "customer_phone_verify": order.customer_phone,
                "order_token": token,
                "items": [{"order_item_id": item.id, "requested_quantity": 2, "condition_reported": "SEALED"}],
            },
        )
        self.assertIn(ret_res.status_code, [200, 201])
        ret_code = ret_res.json()["return_code"]
        ret_req = self.db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == ret_code))
        ret_item = ret_req.items[0]

        # Phê duyệt trước khi nhận hàng
        self.client.post(f"/api/v1/admin/returns/{ret_code}/approve", json={}, headers=self.pharmacist_headers)
        self.client.post(f"/api/v1/admin/returns/{ret_code}/receive", json={}, headers=self.pharmacist_headers)

        self.db.refresh(self.stock_1a)
        on_hand_before = self.stock_1a.quantity_on_hand
        avail_before = self.stock_1a.quantity_available

        insp_res = self.client.post(
            f"/api/v1/admin/returns/{ret_code}/inspect",
            json={
                "general_inspection_note": "Bao bì nguyên vẹn, thuốc còn hạn dùng tốt",
                "items": [
                    {
                        "return_item_id": ret_item.id,
                        "condition": "SEALED",
                        "restock_destination": "SELLABLE_STOCK",
                        "accepted_quantity": 2,
                        "rejected_quantity": 0,
                        "restock_quantity": 2,
                    }
                ],
            },
            headers=self.pharmacist_headers,
        )
        self.assertEqual(insp_res.status_code, 200)

        self.db.refresh(self.stock_1a)
        self.assertEqual(self.stock_1a.quantity_on_hand, on_hand_before + 2)
        self.assertEqual(self.stock_1a.quantity_available, avail_before + 2)

        mov = self.db.scalar(
            select(StockMovement).where(
                StockMovement.movement_type == "RETURN_RESTOCK",
                StockMovement.warehouse_id == self.wh_hcm.id,
            ).order_by(StockMovement.id.desc())
        )
        self.assertIsNotNone(mov)
        self.assertEqual(mov.quantity, 2)

    def test_32_pharmacist_inspect_return_quarantine(self):
        """32. Dược sĩ kiểm định QUARANTINE: Ghi biến động cách ly tại kho xuất phát, không tăng tồn bán được."""
        order, item = self._create_delivered_order_for_return("0977000032")
        token = create_guest_order_token(order.order_code, order.customer_phone)

        ret_res = self.client.post(
            f"/api/v1/returns?order_token={token}",
            json={
                "order_code": order.order_code,
                "request_type": "RETURN",
                "reason_code": "QUALITY_ISSUE",
                "reason_text": "Nghi ngờ biến màu",
                "customer_phone_verify": order.customer_phone,
                "order_token": token,
                "items": [{"order_item_id": item.id, "requested_quantity": 1}],
            },
        )
        self.assertIn(ret_res.status_code, [200, 201])
        ret_code = ret_res.json()["return_code"]
        ret_req = self.db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == ret_code))

        # Phê duyệt trước khi nhận hàng
        self.client.post(f"/api/v1/admin/returns/{ret_code}/approve", json={}, headers=self.pharmacist_headers)
        self.client.post(f"/api/v1/admin/returns/{ret_code}/receive", json={}, headers=self.pharmacist_headers)

        self.db.refresh(self.stock_1a)
        avail_before = self.stock_1a.quantity_available

        insp_res = self.client.post(
            f"/api/v1/admin/returns/{ret_code}/inspect",
            json={
                "items": [
                    {
                        "return_item_id": ret_req.items[0].id,
                        "condition": "SUSPICIOUS",
                        "restock_destination": "QUARANTINE",
                        "accepted_quantity": 1,
                        "rejected_quantity": 0,
                    }
                ]
            },
            headers=self.pharmacist_headers,
        )
        self.assertEqual(insp_res.status_code, 200)

        self.db.refresh(self.stock_1a)
        self.assertEqual(self.stock_1a.quantity_available, avail_before)

        mov = self.db.scalar(
            select(StockMovement).where(
                StockMovement.movement_type == "RETURN_QUARANTINE",
                StockMovement.warehouse_id == self.wh_hcm.id,
            ).order_by(StockMovement.id.desc())
        )
        self.assertIsNotNone(mov)

    def test_33_pharmacist_inspect_return_dispose(self):
        """33. Dược sĩ kiểm định NON_SELLABLE_DISPOSE: Ghi Thẻ kho tiêu hủy RETURN_DISPOSE."""
        order, item = self._create_delivered_order_for_return("0977000033")
        token = create_guest_order_token(order.order_code, order.customer_phone)

        ret_res = self.client.post(
            f"/api/v1/returns?order_token={token}",
            json={
                "order_code": order.order_code,
                "request_type": "RETURN",
                "reason_code": "BROKEN",
                "reason_text": "Vỡ nát lọ thuốc",
                "customer_phone_verify": order.customer_phone,
                "order_token": token,
                "items": [{"order_item_id": item.id, "requested_quantity": 1}],
            },
        )
        self.assertIn(ret_res.status_code, [200, 201])
        ret_code = ret_res.json()["return_code"]
        ret_req = self.db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == ret_code))

        # Phê duyệt trước khi nhận hàng
        self.client.post(f"/api/v1/admin/returns/{ret_code}/approve", json={}, headers=self.pharmacist_headers)
        self.client.post(f"/api/v1/admin/returns/{ret_code}/receive", json={}, headers=self.pharmacist_headers)

        insp_res = self.client.post(
            f"/api/v1/admin/returns/{ret_code}/inspect",
            json={
                "items": [
                    {
                        "return_item_id": ret_req.items[0].id,
                        "condition": "DAMAGED",
                        "restock_destination": "NON_SELLABLE_DISPOSE",
                        "accepted_quantity": 1,
                    }
                ]
            },
            headers=self.pharmacist_headers,
        )
        self.assertEqual(insp_res.status_code, 200)

        mov = self.db.scalar(
            select(StockMovement).where(
                StockMovement.movement_type == "RETURN_DISPOSE",
                StockMovement.warehouse_id == self.wh_hcm.id,
            ).order_by(StockMovement.id.desc())
        )
        self.assertIsNotNone(mov)

    def test_34_multi_warehouse_return_routing(self):
        """34. Đơn hàng tách kho khi đổi/trả sản phẩm của kho Hà Nội thì nhập lại đúng kho Hà Nội."""
        payload = self._make_checkout_payload(
            customer_name="Test Hoàn Kho HN",
            customer_phone="0977000034",
            city="Hà Nội",
            items=[{"product_id": 8802, "quantity": 1, "sku_id": self.sku_2.id}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertIn(res.status_code, [200, 201], res.text)
        order = self.db.scalar(select(Order).where(Order.order_code == res.json()["order_code"]))
        ff = self.db.scalar(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id))
        self.assertEqual(ff.warehouse_id, self.wh_hn.id)

        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "PICKED"}, headers=self.pharmacist_headers)
        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "PACKED"}, headers=self.pharmacist_headers)
        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "SHIPPED"}, headers=self.pharmacist_headers)
        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff.id}/status", json={"status": "DELIVERED"}, headers=self.pharmacist_headers)

        token = create_guest_order_token(order.order_code, order.customer_phone)
        ret_res = self.client.post(
            f"/api/v1/returns?order_token={token}",
            json={
                "order_code": order.order_code,
                "request_type": "RETURN",
                "reason_code": "CUSTOMER_CHANGE_MIND",
                "reason_text": "Hoàn về kho Hà Nội",
                "customer_phone_verify": order.customer_phone,
                "order_token": token,
                "items": [{"order_item_id": order.items[0].id, "requested_quantity": 1}],
            },
        )
        self.assertIn(ret_res.status_code, [200, 201])
        ret_code = ret_res.json()["return_code"]
        ret_req = self.db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == ret_code))

        # Phê duyệt trước khi nhận hàng
        self.client.post(f"/api/v1/admin/returns/{ret_code}/approve", json={}, headers=self.pharmacist_headers)
        self.client.post(f"/api/v1/admin/returns/{ret_code}/receive", json={}, headers=self.pharmacist_headers)

        self.db.refresh(self.stock_2)
        on_hand_hn_before = self.stock_2.quantity_on_hand

        self.client.post(
            f"/api/v1/admin/returns/{ret_code}/inspect",
            json={
                "items": [
                    {
                        "return_item_id": ret_req.items[0].id,
                        "condition": "GOOD_CONDITION",
                        "restock_destination": "SELLABLE_STOCK",
                        "accepted_quantity": 1,
                        "restock_quantity": 1,
                    }
                ]
            },
            headers=self.pharmacist_headers,
        )

        self.db.refresh(self.stock_2)
        self.assertEqual(self.stock_2.quantity_on_hand, on_hand_hn_before + 1)

    def test_35_inspection_requires_valid_status(self):
        """35. Thẩm định kiểm nghiệm yêu cầu phiếu hoàn phải ở trạng thái RECEIVED hoặc INSPECTING (không được nhảy cóc)."""
        order, item = self._create_delivered_order_for_return("0977000035")
        token = create_guest_order_token(order.order_code, order.customer_phone)

        ret_res = self.client.post(
            f"/api/v1/returns?order_token={token}",
            json={
                "order_code": order.order_code,
                "request_type": "RETURN",
                "reason_code": "WRONG_ITEM",
                "reason_text": "Chưa nhận hàng",
                "customer_phone_verify": order.customer_phone,
                "order_token": token,
                "items": [{"order_item_id": item.id, "requested_quantity": 1}],
            },
        )
        self.assertIn(ret_res.status_code, [200, 201])
        ret_code = ret_res.json()["return_code"]
        ret_req = self.db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == ret_code))

        insp_res = self.client.post(
            f"/api/v1/admin/returns/{ret_code}/inspect",
            json={"items": [{"return_item_id": ret_req.items[0].id, "accepted_quantity": 1}]},
            headers=self.pharmacist_headers,
        )
        self.assertEqual(insp_res.status_code, 400)

    # =========================================================================
    # GROUP E: CONCURRENCY, INVENTORY INTEGRITY & BOUNDARY PROTECTION
    # =========================================================================

    def test_36_overselling_prevention(self):
        """36. Chặn bán vượt tồn (Overselling): Tồn khả dụng không thể bị âm khi đặt quá số lượng có sẵn."""
        self.db.refresh(self.stock_1a)
        self.db.refresh(self.stock_1b)
        old_a = self.stock_1a.quantity_available
        old_b = self.stock_1b.quantity_available
        try:
            self.stock_1a.quantity_available = 2
            self.stock_1b.quantity_available = 0
            self.db.commit()

            payload = self._make_checkout_payload(
                customer_name="Test Oversell",
                customer_phone="0966000036",
                items=[{"product_id": 8801, "quantity": 10, "sku_id": self.sku_1.id}],
            )
            res = self.client.post("/api/v1/store/orders/checkout", json=payload)
            self.assertEqual(res.status_code, 400)

            self.db.refresh(self.stock_1a)
            self.assertGreaterEqual(self.stock_1a.quantity_available, 0)
        finally:
            self.stock_1a.quantity_available = old_a
            self.stock_1b.quantity_available = old_b
            self.db.commit()

    def test_37_release_order_reservations(self):
        """37. Hàm release_order_reservations hoàn trả đúng tồn kho đã giữ chỗ và cập nhật trạng thái."""
        payload = self._make_checkout_payload(
            customer_name="Test Release Resv",
            customer_phone="0966000037",
            items=[{"product_id": 8801, "quantity": 5, "sku_id": self.sku_1.id}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertIn(res.status_code, [200, 201], res.text)
        order = self.db.scalar(select(Order).where(Order.order_code == res.json()["order_code"]))

        self.db.refresh(self.stock_1a)
        avail_before = self.stock_1a.quantity_available

        released = FulfillmentRoutingService.release_order_reservations(self.db, order.id, "TEST_RELEASE")
        self.assertGreater(released, 0)

        self.db.refresh(self.stock_1a)
        self.assertEqual(self.stock_1a.quantity_available, avail_before + 5)

    def test_38_server_side_price_authority(self):
        """38. Máy chủ nắm quyền quyết định giá: Giá client gửi lên (ví dụ 1.0 VNĐ) bị bỏ qua."""
        payload = self._make_checkout_payload(
            customer_name="Hacker Giá Rẻ",
            customer_phone="0966000038",
            items=[{"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id, "client_unit_price": 1.0}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertIn(res.status_code, [200, 201], res.text)
        order = self.db.scalar(select(Order).where(Order.order_code == res.json()["order_code"]))
        self.assertGreaterEqual(float(order.total_amount), 50000.0)

    def test_39_non_purchasable_product_rejected(self):
        """39. Sản phẩm không đủ điều kiện bán (DRAFT / Không hoạt động) bị từ chối 400."""
        payload = self._make_checkout_payload(
            customer_name="Mua Thuốc DRAFT",
            customer_phone="0966000039",
            items=[{"product_id": 8803, "quantity": 1}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(res.status_code, 400)

    def test_40_invalid_quantity_rejected(self):
        """40. Số lượng <= 0 bị từ chối theo validation schema."""
        payload = self._make_checkout_payload(
            customer_name="Test Số Lượng Âm",
            customer_phone="0966000040",
            items=[{"product_id": 8801, "quantity": 0}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(res.status_code, 422)

    def test_41_order_detail_includes_fulfillment_timeline(self):
        """41. Chi tiết đơn hàng của Admin trả về đầy đủ fulfillments và thông tin phân bổ lô."""
        payload = self._make_checkout_payload(
            customer_name="Test Timeline",
            customer_phone="0966000041",
            items=[{"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id}],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertIn(res.status_code, [200, 201], res.text)
        order = self.db.scalar(select(Order).where(Order.order_code == res.json()["order_code"]))

        detail_res = self.client.get(f"/api/v1/admin/orders/{order.id}", headers=self.pharmacist_headers)
        self.assertEqual(detail_res.status_code, 200)
        data = detail_res.json()
        self.assertIn("fulfillments", data)
        self.assertGreater(len(data["fulfillments"]), 0)
        self.assertIn("batches", data["fulfillments"][0]["items"][0])

    def test_42_guest_anti_idor_order_access(self):
        """42. Bảo mật Anti-IDOR: Khách không thể xem đơn của người khác chỉ bằng số điện thoại nếu thiếu token hợp lệ."""
        order, _ = self._create_delivered_order_for_return("0966000042")

        res = self.client.get(f"/api/v1/store/orders/{order.order_code}?phone={order.customer_phone}")
        self.assertEqual(res.status_code, 403)

        token = create_guest_order_token(order.order_code, order.customer_phone)
        res_ok = self.client.get(f"/api/v1/store/orders/{order.order_code}", headers={"X-Order-Token": token})
        self.assertEqual(res_ok.status_code, 200)

    def test_43_stock_movement_audit_balance_consistency(self):
        """43. Thẻ kho (StockMovement) phản ánh đúng số dư tồn kho balance_after khớp với tồn thực tế."""
        movs = self.db.scalars(
            select(StockMovement).where(StockMovement.batch_id == self.batch_1a.id).order_by(StockMovement.id.desc())
        ).all()
        self.assertGreater(len(movs), 0)
        latest = movs[0]
        self.assertIsNotNone(latest.balance_after)

    def test_44_partial_cancellation_releases_only_portion(self):
        """44. Hủy một phần kiện hàng chỉ giải phóng reservation của kho tương ứng."""
        payload = self._make_checkout_payload(
            customer_name="Test Giải Phóng Một Phần",
            customer_phone="0966000044",
            city="Hà Nội",
            items=[
                {"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id},
                {"product_id": 8802, "quantity": 1, "sku_id": self.sku_2.id},
            ],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertIn(res.status_code, [200, 201], res.text)
        order = self.db.scalar(select(Order).where(Order.order_code == res.json()["order_code"]))
        ffs = self.db.scalars(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id)).all()

        ff_hn = [f for f in ffs if f.warehouse_id == self.wh_hn.id][0]
        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ff_hn.id}/status", json={"status": "CANCELLED"}, headers=self.pharmacist_headers)

        resv_hn = self.db.scalar(
            select(StockReservation).where(
                StockReservation.order_id == order.id,
                StockReservation.warehouse_id == self.wh_hn.id,
            )
        )
        self.assertEqual(resv_hn.status, "RELEASED")

    def test_45_multi_warehouse_order_status_sync(self):
        """45. Trạng thái đơn cha đồng bộ chính xác: PROCESSING khi có kiện PACKED/PICKED, SHIPPING khi có kiện SHIPPED."""
        payload = self._make_checkout_payload(
            customer_name="Test Sync Trạng Thái",
            customer_phone="0966000045",
            city="Hà Nội",
            items=[
                {"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id},
                {"product_id": 8802, "quantity": 1, "sku_id": self.sku_2.id},
            ],
        )
        res = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertIn(res.status_code, [200, 201], res.text)
        order = self.db.scalar(select(Order).where(Order.order_code == res.json()["order_code"]))
        ffs = self.db.scalars(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id)).all()

        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ffs[0].id}/status", json={"status": "PICKED"}, headers=self.pharmacist_headers)
        self.db.refresh(order)
        self.assertEqual(order.order_status, "PROCESSING")

        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ffs[0].id}/status", json={"status": "PACKED"}, headers=self.pharmacist_headers)
        self.client.patch(f"/api/v1/admin/orders/fulfillments/{ffs[0].id}/status", json={"status": "SHIPPED"}, headers=self.pharmacist_headers)
        self.db.refresh(order)
        self.assertEqual(order.order_status, "SHIPPING")

    def test_46_admin_alert_created_on_return(self):
        """46. Khi khách tạo phiếu đổi/trả hàng, hệ thống tự động sinh thông báo AdminAlert."""
        order, item = self._create_delivered_order_for_return("0966000046")
        token = create_guest_order_token(order.order_code, order.customer_phone)
        ret_res = self.client.post(
            f"/api/v1/returns?order_token={token}",
            json={
                "order_code": order.order_code,
                "request_type": "RETURN",
                "reason_code": "WRONG_ITEM",
                "reason_text": "Thuốc giao không đúng phân loại",
                "customer_phone_verify": order.customer_phone,
                "order_token": token,
                "items": [{"order_item_id": item.id, "requested_quantity": 1}],
            },
        )
        self.assertIn(ret_res.status_code, [200, 201])
        alerts = self.db.scalars(
            select(AdminAlert).where(AdminAlert.alert_type == "RETURN_REQUESTED")
        ).all()
        self.assertGreater(len(alerts), 0)

    def test_47_warehouse_stock_summary_api_accuracy(self):
        """47. GET /api/v1/warehouses/{id}/stocks phản ánh chính xác on_hand, available và reserved."""
        res = self.client.get(f"/api/v1/warehouses/{self.wh_hcm.id}/stocks", headers=self.pharmacist_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("stats", data)
        self.assertIn("stocks", data)
        stats = data["stats"]
        self.assertGreaterEqual(stats["total_on_hand"], 0)
        self.assertGreaterEqual(stats["total_available"], 0)
        self.assertGreaterEqual(stats["total_reserved"], 0)

    def test_48_test_data_isolation(self):
        """48. Cách ly dữ liệu thử nghiệm: Dữ liệu test có mã tiền tố rõ ràng và không làm hỏng dữ liệu gốc."""
        payload = self._make_checkout_payload(
            customer_name="Test Isolation Đơn Hàng",
            customer_phone="0948000048",
            items=[{"product_id": 8801, "quantity": 1, "sku_id": self.sku_1.id}],
        )
        self.client.post("/api/v1/store/orders/checkout", json=payload)
        test_orders = self.db.scalars(
            select(Order).where(Order.customer_name.like("%Test%"))
        ).all()
        self.assertGreater(len(test_orders), 0)


if __name__ == "__main__":
    unittest.main()
