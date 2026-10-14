"""
apps/api/tests/test_returns_exchanges_refunds.py

Bộ kiểm thử tự động toàn diện cho Phase 2:
Returns, Exchanges, Refunds, Reverse Logistics, FEFO Inspection, and Financial Reconciliation.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    CanonicalProduct,
    EmailOutbox,
    InventoryBatch,
    Order,
    OrderItem,
    ProductSku,
    StockMovement,
    User,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import RxOtcStatus, UserRole
from app.models.returns import (
    ExchangeOrder,
    ExchangeStatus,
    ItemCondition,
    ReconciliationStatus,
    Refund,
    RefundMethod,
    RefundStatus,
    RestockDestination,
    ReturnItem,
    ReturnRequest,
    ReturnRequestType,
    ReturnStatus,
)
from app.services.refund_calculation_service import RefundCalculationService
from app.services.return_policy_service import ReturnPolicyService


@pytest.fixture
def setup_aftersales_data(client, admin_headers):
    """
    Tạo dữ liệu kho hàng, lô thuốc, đơn hàng thử nghiệm cho suite test đổi/trả.
    """
    with SessionLocal() as db:
        # 1. Tìm hoặc tạo Warehouse
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HN-01"))
        if not wh:
            wh = Warehouse(
                code="KHO-HN-01",
                name="Kho Dược Tổng Hà Nội GSP",
                address="Số 123 Đường Nguyễn Trãi, Thanh Xuân, Hà Nội",
                phone="0243888999",
                lat=21.0253,
                lng=105.8552,
                is_active=True,
            )
            db.add(wh)
            db.flush()

        # 2. Tìm hoặc tạo sản phẩm và SKU
        prod = db.scalar(select(CanonicalProduct).order_by(CanonicalProduct.id.asc()))
        if not prod:
            prod = CanonicalProduct(
                canonical_name="Panadol Extra Đỏ 500mg",
                registration_number="VN-12345-21",
                dosage_form="Viên nén",
                rx_otc_status=RxOtcStatus.OTC,
            )
            db.add(prod)
            db.flush()

        sku = db.scalar(select(ProductSku).where(ProductSku.canonical_product_id == prod.id))
        if not sku:
            sku = ProductSku(
                canonical_product_id=prod.id,
                sku_code="SKU-PANADOL-EXTRA",
                barcode="893123456789",
                base_price=Decimal("65000.0"),
                is_default=True,
                is_active=True,
            )
            db.add(sku)
            db.flush()

        # 3. Tạo InventoryBatch & WarehouseBatchStock
        batch = db.scalar(select(InventoryBatch).where(InventoryBatch.sku_id == sku.id))
        if not batch:
            batch = InventoryBatch(
                sku_id=sku.id,
                batch_number="LOT-PAN-2026-01",
                expiry_date=datetime.now(UTC).date() + timedelta(days=365),
                initial_quantity=500,
                status="ACTIVE",
            )
            db.add(batch)
            db.flush()

            wh_stock = WarehouseBatchStock(
                warehouse_id=wh.id,
                batch_id=batch.id,
                quantity_on_hand=100,
                quantity_available=100,
                quantity_reserved=0,
            )
            db.add(wh_stock)
            db.flush()

        # 4. Tạo User Customer thử nghiệm
        customer_user = db.scalar(select(User).where(User.email == "customer_test@h4care.vn"))
        if not customer_user:
            from app.core.security import hash_password
            customer_user = User(
                email="customer_test@h4care.vn",
                password_hash=hash_password("Customer@123"),
                full_name="Nguyễn Văn Khách Hàng",
                role=UserRole.CUSTOMER,
                is_active=True,
            )
            db.add(customer_user)
            db.flush()

        # 5. Tạo Đơn hàng đã giao thành công (DELIVERED)
        import uuid
        uid = uuid.uuid4().hex[:8]
        order_delivered = Order(
            order_code=f"ORD-DELIV-{uid}",
            user_id=customer_user.id,
            customer_name="Nguyễn Văn Khách Hàng",
            customer_phone="0912345678",
            customer_email="customer_test@h4care.vn",
            shipping_address="Số 45 Lê Văn Lương, Nhân Chính, Thanh Xuân, Hà Nội",
            order_status="DELIVERED",
            payment_status="PAID",
            payment_method="COD",
            total_amount=Decimal("195000.0"),
            shipping_fee=Decimal("15000.0"),
        )
        db.add(order_delivered)
        db.flush()

        order_item = OrderItem(
            order_id=order_delivered.id,
            product_id=prod.id,
            product_name=prod.canonical_name,
            product_sku=sku.sku_code,
            price=Decimal("60000.0"),
            quantity=3,
            subtotal=Decimal("180000.0"),
        )
        db.add(order_item)
        db.flush()

        # 6. Tạo Đơn hàng đang xử lý (PENDING)
        order_pending = Order(
            order_code=f"ORD-PEND-{uid}",
            user_id=customer_user.id,
            customer_name="Nguyễn Văn Khách Hàng",
            customer_phone="0912345678",
            shipping_address="Số 45 Lê Văn Lương, Nhân Chính, Thanh Xuân, Hà Nội",
            order_status="PENDING",
            payment_status="PENDING",
            total_amount=Decimal("65000.0"),
            shipping_fee=Decimal("15000.0"),
        )
        db.add(order_pending)
        db.flush()

        order_item_pending = OrderItem(
            order_id=order_pending.id,
            product_id=prod.id,
            product_name=prod.canonical_name,
            product_sku=sku.sku_code,
            price=Decimal("65000.0"),
            quantity=1,
            subtotal=Decimal("65000.0"),
        )
        db.add(order_item_pending)

        db.commit()

        return {
            "warehouse_id": wh.id,
            "product_id": prod.id,
            "sku_id": sku.id,
            "batch_id": batch.id,
            "customer_id": customer_user.id,
            "order_delivered_code": order_delivered.order_code,
            "order_delivered_id": order_delivered.id,
            "order_item_id": order_item.id,
            "order_pending_code": order_pending.order_code,
        }


def test_return_eligibility_delivered_vs_pending(client: TestClient, setup_aftersales_data):
    """
    Kiểm tra điều kiện đổi trả: Đơn DELIVERED đủ điều kiện, đơn PENDING không đủ điều kiện.
    """
    deliv_code = setup_aftersales_data["order_delivered_code"]
    pend_code = setup_aftersales_data["order_pending_code"]

    # 1. Đơn DELIVERED
    resp = client.get(f"/api/v1/returns/eligibility/{deliv_code}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_code"] == deliv_code
    assert data["can_request_return"] is True
    assert len(data["items"]) == 1
    assert data["items"][0]["returnable_quantity"] == 3
    assert data["items"][0]["is_eligible"] is True

    # 2. Đơn PENDING
    resp_pend = client.get(f"/api/v1/returns/eligibility/{pend_code}")
    assert resp_pend.status_code == 200
    data_pend = resp_pend.json()
    assert data_pend["can_request_return"] is False
    assert "chưa giao thành công" in data_pend["rejection_reason"]


def test_create_return_request_and_partial_quantity(client: TestClient, setup_aftersales_data, admin_headers):
    """
    Tạo yêu cầu đổi trả một phần số lượng (trả 1 trên 3 hộp), kiểm tra số lượng còn lại.
    """
    deliv_code = setup_aftersales_data["order_delivered_code"]
    item_id = setup_aftersales_data["order_item_id"]

    # 1. Khách gửi yêu cầu trả 1 hộp
    payload = {
        "order_code": deliv_code,
        "request_type": "RETURN",
        "reason_code": "WRONG_ITEM",
        "reason_text": "Giao nhầm quy cách đóng gói",
        "customer_note": "Hộp thuốc còn nguyên seal tem chống giả",
        "items": [
            {
                "order_item_id": item_id,
                "requested_quantity": 1,
                "customer_reason": "Sai quy cách",
                "condition_reported": "SEALED",
            }
        ],
        "customer_phone_verify": "0912345678",
    }
    resp = client.post("/api/v1/returns", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    return_code = data["return_code"]
    assert return_code.startswith("RET-")

    # 2. Kiểm tra lại điều kiện đổi trả: số lượng còn lại phải là 3 - 1 = 2
    resp_check = client.get(f"/api/v1/returns/eligibility/{deliv_code}")
    assert resp_check.status_code == 200
    check_data = resp_check.json()
    assert check_data["items"][0]["returned_quantity"] == 1
    assert check_data["items"][0]["returnable_quantity"] == 2

    # 3. Cố gắng yêu cầu vượt quá số lượng còn lại (yêu cầu 3 hộp trong khi chỉ còn 2) -> Bị chặn lỗi 400
    invalid_payload = {
        "order_code": deliv_code,
        "request_type": "RETURN",
        "reason_code": "DEFECTIVE",
        "reason_text": "Hộp móp méo",
        "items": [
            {
                "order_item_id": item_id,
                "requested_quantity": 3,
            }
        ],
        "customer_phone_verify": "0912345678",
    }
    resp_invalid = client.post("/api/v1/returns", json=invalid_payload)
    assert resp_invalid.status_code == 400
    assert "Số lượng còn có thể đổi trả: 2" in resp_invalid.json()["detail"]


def test_full_return_workflow_with_inspection_and_restock(client: TestClient, setup_aftersales_data, admin_headers):
    """
    Toàn bộ vòng đời Đổi Trả:
    Tạo request -> Admin Review -> Duyệt -> Khách gửi hàng -> Kho nhận -> Dược sĩ kiểm định & Nhập kho bán -> Refund Pending.
    """
    deliv_code = setup_aftersales_data["order_delivered_code"]
    item_id = setup_aftersales_data["order_item_id"]

    # 1. Tạo request
    create_payload = {
        "order_code": deliv_code,
        "request_type": "RETURN",
        "reason_code": "WRONG_ITEM",
        "reason_text": "Giao sai màu vỏ hộp",
        "items": [
            {"order_item_id": item_id, "requested_quantity": 1}
        ],
        "customer_phone_verify": "0912345678",
    }
    res_create = client.post("/api/v1/returns", json=create_payload)
    return_code = res_create.json()["return_code"]

    # 2. Admin xem xét (REVIEWING)
    res_review = client.post(
        f"/api/v1/admin/returns/{return_code}/review",
        headers=admin_headers,
        json={"status": "REVIEWING", "admin_note": "Dược sĩ đang kiểm tra thông tin đơn thuốc."},
    )
    assert res_review.status_code == 200
    assert res_review.json()["status"] == "REVIEWING"

    # 3. Admin duyệt yêu cầu (APPROVE -> WAITING_CUSTOMER_RETURN)
    res_approve = client.post(
        f"/api/v1/admin/returns/{return_code}/approve",
        headers=admin_headers,
        json={"admin_note": "Đã phê duyệt, gửi hướng dẫn đóng gói cho khách."},
    )
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] == "WAITING_CUSTOMER_RETURN"

    # 4. Khách hàng gửi hàng & cập nhật mã vận đơn (SHIPPING -> RETURN_IN_TRANSIT)
    res_ship = client.post(
        f"/api/v1/returns/{return_code}/shipping",
        json={"carrier_name": "GHTK Fast", "tracking_code": "GHTK-RET-998877"},
    )
    assert res_ship.status_code == 200
    assert res_ship.json()["status"] == "RETURN_IN_TRANSIT"

    # 5. Kho xác nhận nhận hàng (RECEIVE -> RECEIVED)
    res_receive = client.post(
        f"/api/v1/admin/returns/{return_code}/receive",
        headers=admin_headers,
        json={"note": "Kho đã nhận nguyên vẹn kiện hàng."},
    )
    assert res_receive.status_code == 200
    assert res_receive.json()["status"] == "RECEIVED"

    # Lấy thông tin return để lấy return_item_id
    detail_res = client.get(f"/api/v1/admin/returns/{return_code}", headers=admin_headers)
    return_item_id = detail_res.json()["items"][0]["id"]

    # 6. Dược sĩ kiểm định & Nhập lại kho bán (INSPECT -> INSPECTION_COMPLETED -> REFUND_PENDING)
    inspect_payload = {
        "general_inspection_note": "Hộp thuốc còn nguyên seal niêm phong, đủ điều kiện nhập lại kho bán.",
        "items": [
            {
                "return_item_id": return_item_id,
                "condition": "GOOD_CONDITION",
                "restock_destination": "SELLABLE_STOCK",
                "accepted_quantity": 1,
                "rejected_quantity": 0,
                "restock_quantity": 1,
                "notes": "Đạt chuẩn GSP",
            }
        ],
    }
    res_inspect = client.post(
        f"/api/v1/admin/returns/{return_code}/inspect",
        headers=admin_headers,
        json=inspect_payload,
    )
    assert res_inspect.status_code == 200
    assert res_inspect.json()["status"] == "REFUND_PENDING"

    # 7. Kiểm tra đã có StockMovement loại RETURN_RESTOCK ghi nhận
    with SessionLocal() as db:
        movement = db.scalar(
            select(StockMovement).where(
                StockMovement.reference_id == return_code,
                StockMovement.movement_type == "RETURN_RESTOCK",
            )
        )
        assert movement is not None
        assert movement.quantity == 1


def test_refund_creation_and_manual_bank_reconciliation(client: TestClient, setup_aftersales_data, admin_headers):
    """
    Kiểm thử quy trình Hoàn tiền & Đối soát tài chính (Manual Bank Transfer & Idempotency).
    """
    deliv_code = setup_aftersales_data["order_delivered_code"]

    # 1. Kế toán tạo phiếu hoàn tiền 60.000 đ
    idempotency_key = f"IDEM-REF-{datetime.now().timestamp()}"
    create_ref_payload = {
        "order_code": deliv_code,
        "refund_amount": 60000.0,
        "refund_method": "BANK_TRANSFER",
        "reason": "Hoàn tiền trả 1 hộp thuốc Panadol",
        "beneficiary_bank": "Vietcombank",
        "beneficiary_account_number": "001100223344",
        "beneficiary_account_name": "NGUYEN VAN KHACH HANG",
        "idempotency_key": idempotency_key,
    }
    res_refund = client.post("/api/v1/admin/refunds", headers=admin_headers, json=create_ref_payload)
    assert res_refund.status_code == 200
    refund_code = res_refund.json()["refund_code"]
    assert refund_code.startswith("REF-")

    # 2. Thử gửi lại đúng idempotency_key -> Trả về đúng phiếu đã tạo, không nhân bản
    res_dup = client.post("/api/v1/admin/refunds", headers=admin_headers, json=create_ref_payload)
    assert res_dup.status_code == 200
    assert res_dup.json()["refund_code"] == refund_code

    # 3. Kế toán thực hiện chuyển khoản thành công với mã UNC
    res_bank = client.post(
        f"/api/v1/admin/refunds/{refund_code}/manual-bank",
        headers=admin_headers,
        json={
            "bank_transfer_ref": "VCB-UNC-99228811",
            "proof_document_url": "/api/v1/returns/evidence/proof_vcb_unc.png",
            "notes": "Đã chuyển khoản qua Internet Banking Vietcombank",
        },
    )
    assert res_bank.status_code == 200
    assert res_bank.json()["status"] == "SUCCEEDED"

    # 4. Kiểm tra đối soát tài chính
    res_detail = client.get(f"/api/v1/admin/refunds/{refund_code}", headers=admin_headers)
    assert res_detail.status_code == 200
    ref_detail = res_detail.json()
    assert ref_detail["reconciliation_status"] == "MATCHED"
    assert ref_detail["bank_transfer_ref"] == "VCB-UNC-99228811"


def test_over_refund_protection(client: TestClient, setup_aftersales_data, admin_headers):
    """
    Kiểm tra bất biến tài chính: Ngăn chặn hoàn tiền vượt quá tổng giá trị đơn hàng (Over-refund Blocking).
    """
    deliv_code = setup_aftersales_data["order_delivered_code"]

    # Đơn hàng tổng giá trị 195.000 đ, cố gắng hoàn 500.000 đ -> Bị chặn lỗi 400
    over_payload = {
        "order_code": deliv_code,
        "refund_amount": 500000.0,
        "refund_method": "BANK_TRANSFER",
        "reason": "Hoàn tiền vượt mức",
    }
    res = client.post("/api/v1/admin/refunds", headers=admin_headers, json=over_payload)
    assert res.status_code == 400
    assert "vượt quá hạn mức tối đa" in res.json()["detail"]


def test_exchange_workflow_price_difference(client: TestClient, setup_aftersales_data, admin_headers):
    """
    Kiểm tra toàn bộ quy trình Đổi Hàng (Exchange):
    Tạo exchange request -> Duyệt & nhận hàng -> Tạo đơn đổi hàng mới -> Tính chênh lệch giá -> Xuất kho giao hàng mới.
    """
    deliv_code = setup_aftersales_data["order_delivered_code"]
    item_id = setup_aftersales_data["order_item_id"]
    prod_id = setup_aftersales_data["product_id"]

    # 1. Khách gửi yêu cầu ĐỔI HÀNG (request_type = EXCHANGE)
    ex_payload = {
        "order_code": deliv_code,
        "request_type": "EXCHANGE",
        "reason_code": "ORDERED_WRONG",
        "reason_text": "Khách muốn đổi sang hộp lớn hơn",
        "items": [{"order_item_id": item_id, "requested_quantity": 1}],
        "customer_phone_verify": "0912345678",
    }
    res_ex_req = client.post("/api/v1/returns", json=ex_payload)
    assert res_ex_req.status_code == 200
    return_code = res_ex_req.json()["return_code"]

    # Duyệt & nhận hàng & kiểm định
    client.post(f"/api/v1/admin/returns/{return_code}/approve", headers=admin_headers, json={})
    client.post(f"/api/v1/returns/{return_code}/shipping", json={"carrier_name": "GHTK", "tracking_code": "GHTK-EX-123"})
    client.post(f"/api/v1/admin/returns/{return_code}/receive", headers=admin_headers, json={})

    detail_res = client.get(f"/api/v1/admin/returns/{return_code}", headers=admin_headers)
    ret_item_id = detail_res.json()["items"][0]["id"]

    client.post(
        f"/api/v1/admin/returns/{return_code}/inspect",
        headers=admin_headers,
        json={
            "items": [
                {
                    "return_item_id": ret_item_id,
                    "condition": "SEALED",
                    "restock_destination": "SELLABLE_STOCK",
                    "accepted_quantity": 1,
                }
            ]
        },
    )

    # 2. Tạo đơn đổi hàng mới (ExchangeOrder) với sản phẩm thay thế giá 80.000 đ
    # Giá hàng cũ hoàn trả ~60.000 đ -> Chênh lệch giá = +20.000 đ (Khách phải trả thêm)
    create_ex_payload = {
        "return_code": return_code,
        "items": [
            {
                "product_id": prod_id,
                "quantity": 1,
                "unit_price": 80000.0,
            }
        ],
    }
    res_create_ex = client.post("/api/v1/admin/exchanges", headers=admin_headers, json=create_ex_payload)
    assert res_create_ex.status_code == 200
    ex_data = res_create_ex.json()
    exchange_code = ex_data["exchange_code"]
    assert exchange_code.startswith("EXC-")
    assert ex_data["status"] == "WAITING_PAYMENT"
    assert ex_data["price_difference"] > 0

    # 3. Xác nhận khách đã thanh toán chênh lệch
    res_pay = client.post(
        f"/api/v1/admin/exchanges/{exchange_code}/confirm-payment",
        headers=admin_headers,
        json={"payment_method": "COD", "transaction_ref": "COD-EXCHANGE-20K"},
    )
    assert res_pay.status_code == 200
    assert res_pay.json()["status"] == "ALLOCATING_STOCK"

    # 4. Xuất kho gửi hàng đổi mới
    res_dispatch = client.post(
        f"/api/v1/admin/exchanges/{exchange_code}/dispatch",
        headers=admin_headers,
        json={"carrier_name": "ViettelPost", "tracking_code": "VTP-NEW-556677"},
    )
    assert res_dispatch.status_code == 200
    assert res_dispatch.json()["status"] == "SHIPPING"

    # 5. Hoàn tất đơn đổi hàng
    res_complete = client.post(
        f"/api/v1/admin/exchanges/{exchange_code}/complete",
        headers=admin_headers,
    )
    assert res_complete.status_code == 200
    assert res_complete.json()["status"] == "COMPLETED"


def test_return_rejection_workflow(client: TestClient, setup_aftersales_data, admin_headers):
    """
    Kiểm tra luồng từ chối yêu cầu đổi/trả với lý do bắt buộc.
    """
    deliv_code = setup_aftersales_data["order_delivered_code"]
    item_id = setup_aftersales_data["order_item_id"]

    res_create = client.post(
        "/api/v1/returns",
        json={
            "order_code": deliv_code,
            "request_type": "RETURN",
            "reason_code": "CHANGED_MIND",
            "reason_text": "Không còn nhu cầu sử dụng",
            "items": [{"order_item_id": item_id, "requested_quantity": 1}],
            "customer_phone_verify": "0912345678",
        },
    )
    assert res_create.status_code == 200
    return_code = res_create.json()["return_code"]

    # Admin từ chối yêu cầu
    reject_reason = "Sản phẩm đã bị bóc seal bảo vệ nhiệt độ không đạt chuẩn đổi trả."
    res_reject = client.post(
        f"/api/v1/admin/returns/{return_code}/reject",
        headers=admin_headers,
        json={"rejection_reason": reject_reason, "admin_note": "Kiểm tra hình ảnh thấy seal rách"},
    )
    assert res_reject.status_code == 200
    assert res_reject.json()["status"] == "REJECTED"

    # Kiểm tra chi tiết
    res_detail = client.get(f"/api/v1/returns/{return_code}?phone_verify=0912345678")
    assert res_detail.status_code == 200
    data = res_detail.json()
    assert data["status"] == "REJECTED"
    assert reject_reason in data["rejection_reason"]


def test_customer_cancel_return_request(client: TestClient, setup_aftersales_data):
    """
    Khách hàng chủ động hủy yêu cầu khi ở trạng thái REQUESTED.
    """
    deliv_code = setup_aftersales_data["order_delivered_code"]
    item_id = setup_aftersales_data["order_item_id"]

    res_create = client.post(
        "/api/v1/returns",
        json={
            "order_code": deliv_code,
            "request_type": "RETURN",
            "reason_code": "ORDERED_WRONG",
            "reason_text": "Đặt nhầm",
            "items": [{"order_item_id": item_id, "requested_quantity": 1}],
            "customer_phone_verify": "0912345678",
        },
    )
    return_code = res_create.json()["return_code"]

    # Khách hủy
    res_cancel = client.post(
        f"/api/v1/returns/{return_code}/cancel",
        json={"reason": "Tôi tìm thấy đơn thuốc cũ rồi nên không trả nữa"},
    )
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "CANCELLED"


def test_customer_ownership_security(client: TestClient, setup_aftersales_data):
    """
    Bảo mật truy cập: Không thể xem chi tiết hoặc tạo yêu cầu khi số điện thoại xác thực sai.
    """
    deliv_code = setup_aftersales_data["order_delivered_code"]
    item_id = setup_aftersales_data["order_item_id"]

    # Sai SĐT khi tạo -> 403
    res_bad_phone = client.post(
        "/api/v1/returns",
        json={
            "order_code": deliv_code,
            "request_type": "RETURN",
            "reason_code": "WRONG_ITEM",
            "reason_text": "Sai hàng",
            "items": [{"order_item_id": item_id, "requested_quantity": 1}],
            "customer_phone_verify": "0999999999",  # Sai SĐT
        },
    )
    assert res_bad_phone.status_code == 403


def test_momo_refund_attempt_logging(client: TestClient, setup_aftersales_data, admin_headers):
    """
    Kiểm tra kích hoạt hoàn tiền MoMo và ghi nhận lịch sử thử (RefundAttempt).
    """
    deliv_code = setup_aftersales_data["order_delivered_code"]

    res_ref = client.post(
        "/api/v1/admin/refunds",
        headers=admin_headers,
        json={
            "order_code": deliv_code,
            "refund_amount": 50000.0,
            "refund_method": "MOMO_ONLINE",
            "reason": "Hoàn tiền ví MoMo",
        },
    )
    assert res_ref.status_code == 200
    refund_code = res_ref.json()["refund_code"]

    # Kích hoạt MoMo refund (trong test offline sẽ ghi attempt thành công hoặc needs_review)
    res_momo = client.post(f"/api/v1/admin/refunds/{refund_code}/momo", headers=admin_headers)
    assert res_momo.status_code == 200

    # Kiểm tra đã có RefundAttempt trong chi tiết
    res_detail = client.get(f"/api/v1/admin/refunds/{refund_code}", headers=admin_headers)
    assert res_detail.status_code == 200
    attempts = res_detail.json()["attempts"]
    assert len(attempts) >= 1
    assert attempts[0]["gateway_provider"] == "MOMO"


def test_guest_missing_phone_rejected(client: TestClient, setup_aftersales_data):
    """
    Khách vãng lai không truyền SĐT xác thực -> 403 Bị từ chối.
    """
    deliv_code = setup_aftersales_data["order_delivered_code"]
    item_id = setup_aftersales_data["order_item_id"]

    res = client.post(
        "/api/v1/returns",
        json={
            "order_code": deliv_code,
            "request_type": "RETURN",
            "reason_code": "WRONG_ITEM",
            "reason_text": "Không cung cấp SĐT",
            "items": [{"order_item_id": item_id, "requested_quantity": 1}],
            "customer_phone_verify": None,
        },
    )
    assert res.status_code == 403
    assert "xác minh quyền sở hữu" in res.json()["detail"].lower() or "số điện thoại" in res.json()["detail"].lower()


def test_return_excessive_quantity_rejected(client: TestClient, setup_aftersales_data):
    """
    Yêu cầu trả số lượng vượt quá số lượng mua -> 400 Bị từ chối.
    """
    deliv_code = setup_aftersales_data["order_delivered_code"]
    item_id = setup_aftersales_data["order_item_id"]

    res = client.post(
        "/api/v1/returns",
        json={
            "order_code": deliv_code,
            "request_type": "RETURN",
            "reason_code": "WRONG_ITEM",
            "reason_text": "Số lượng vượt mức",
            "items": [{"order_item_id": item_id, "requested_quantity": 9999}],
            "customer_phone_verify": "0912345678",
        },
    )
    assert res.status_code == 400
    assert "không hợp lệ" in res.json()["detail"].lower() or "số lượng" in res.json()["detail"].lower()


def test_email_outbox_created_on_return(client: TestClient, setup_aftersales_data):
    """
    Xác minh EmailOutbox được tạo với đúng schema (reference_type=RETURN_REQUEST, status=PENDING).
    """
    deliv_code = setup_aftersales_data["order_delivered_code"]
    item_id = setup_aftersales_data["order_item_id"]

    res = client.post(
        "/api/v1/returns",
        json={
            "order_code": deliv_code,
            "request_type": "RETURN",
            "reason_code": "WRONG_ITEM",
            "reason_text": "Kiểm tra EmailOutbox",
            "items": [{"order_item_id": item_id, "requested_quantity": 1}],
            "customer_phone_verify": "0912345678",
        },
    )
    assert res.status_code == 200
    ret_code = res.json()["return_code"]

    with SessionLocal() as db:
        outbox = db.scalar(
            select(EmailOutbox).where(
                EmailOutbox.reference_type == "RETURN_REQUEST",
                EmailOutbox.reference_id == ret_code,
            )
        )
        assert outbox is not None
        assert outbox.status == "PENDING"
        assert ret_code in outbox.subject


