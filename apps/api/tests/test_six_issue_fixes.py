import pytest
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    CanonicalProduct,
    Order,
    OrderItem,
    User,
)
from app.models.inventory import (
    BatchStatus,
    CustomerAddress,
    FulfillmentItem,
    InventoryBatch,
    OrderFulfillment,
    OrderItemBatchAllocation,
    ProductSku,
    StockMovement,
    StockReservation,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import UserRole
from app.models.returns import (
    ReturnInspection,
    ReturnItem,
    ReturnRequest,
    ReturnStatus,
    WarehouseReturnCase,
)
from app.services.fulfillment_service import FulfillmentRoutingService
from app.services.refund_calculation_service import RefundCalculationService
from app.services.warehouse_return_service import WarehouseReturnService
from app.api.live_chat import find_nearest_warehouse_staff
from app.db.session import SessionLocal


@pytest.fixture
def db_session():
    with SessionLocal() as db:
        yield db


# ==============================================================================
# TEST 1: FSM TRANSITION & FEFO STOCK DISPATCH (ITEM 1)
# ==============================================================================

def test_fulfillment_fsm_rejects_skipping_steps_and_enforces_fefo_dispatch(db_session: Session):
    """
    Kiểm tra FSM kiện hàng:
    - Chặn nhảy cóc trực tiếp PENDING -> DELIVERED (HTTP 400)
    - Chặn chuyển lùi trạng thái (HTTP 400)
    - Tuân thủ tuần tự PENDING -> PICKED -> PACKED -> SHIPPED (sinh StockMovement DISPATCH) -> DELIVERED
    """
    wh = db_session.scalar(select(Warehouse).where(Warehouse.is_active == True))
    prod = db_session.scalar(select(CanonicalProduct))
    suffix = uuid.uuid4().hex[:6]
    sku = db_session.scalar(select(ProductSku).where(ProductSku.canonical_product_id == prod.id))
    if not sku:
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code=f"SKU-FSM-{suffix}",
            uom="Hộp",
            base_price=Decimal("100000"),
            is_default=True,
            is_active=True,
        )
        db_session.add(sku)
        db_session.flush()

    batch = InventoryBatch(
        sku_id=sku.id,
        batch_number=f"BFSM{suffix}",
        expiry_date=datetime.now(UTC).date() + timedelta(days=365),
        status=BatchStatus.ACTIVE,
    )
    db_session.add(batch)
    db_session.flush()

    stock = WarehouseBatchStock(
        warehouse_id=wh.id,
        batch_id=batch.id,
        quantity_on_hand=50,
        quantity_reserved=5,
        quantity_available=45,
    )
    db_session.add(stock)
    db_session.flush()

    user = db_session.scalar(select(User).where(User.role == UserRole.ADMIN))

    order = Order(
        order_code=f"ORD-FSM-{suffix}",
        user_id=user.id,
        customer_name="Customer FSM",
        customer_phone="0911223344",
        shipping_address="123 Test Street",
        total_amount=Decimal("100000"),
        order_status="PROCESSING",
        fulfillment_status="PENDING",
        assigned_warehouse_id=wh.id,
    )
    db_session.add(order)
    db_session.flush()

    order_item = OrderItem(
        order_id=order.id,
        product_id=prod.id,
        product_sku=sku.sku_code,
        product_name=prod.canonical_name,
        price=Decimal("100000"),
        quantity=5,
        subtotal=Decimal("500000"),
    )
    db_session.add(order_item)
    db_session.flush()

    ff = OrderFulfillment(
        fulfillment_code=f"FUL-FSM-{suffix}",
        order_id=order.id,
        warehouse_id=wh.id,
        status="PENDING",
    )
    db_session.add(ff)
    db_session.flush()

    ff_item = FulfillmentItem(
        fulfillment_id=ff.id,
        order_item_id=order_item.id,
        quantity=5,
    )
    db_session.add(ff_item)
    db_session.flush()

    alloc = OrderItemBatchAllocation(
        fulfillment_item_id=ff_item.id,
        order_item_id=order_item.id,
        batch_id=batch.id,
        warehouse_id=wh.id,
        allocated_quantity=5,
    )
    db_session.add(alloc)

    res = StockReservation(
        order_id=order.id,
        batch_id=batch.id,
        warehouse_id=wh.id,
        quantity=5,
        status="RESERVED",
    )
    db_session.add(res)
    db_session.commit()

    # 1. Nhảy cóc trực tiếp PENDING -> DELIVERED phải bị chặn 400
    with pytest.raises(HTTPException) as exc1:
        FulfillmentRoutingService.transition_fulfillment_status(
            db=db_session,
            fulfillment_id=ff.id,
            new_status="DELIVERED",
            user_id=user.id,
        )
    assert exc1.value.status_code == 400
    assert "bắt buộc tuần tự" in exc1.value.detail

    # 2. Bước 1: PENDING -> PICKED
    FulfillmentRoutingService.transition_fulfillment_status(
        db=db_session, fulfillment_id=ff.id, new_status="PICKED", user_id=user.id
    )
    db_session.refresh(ff)
    assert ff.status == "PICKED"

    # 3. Bước 2: PICKED -> PACKED
    FulfillmentRoutingService.transition_fulfillment_status(
        db=db_session, fulfillment_id=ff.id, new_status="PACKED", user_id=user.id
    )
    db_session.refresh(ff)
    assert ff.status == "PACKED"

    # Chặn chuyển lùi PACKED -> PICKED
    with pytest.raises(HTTPException) as exc2:
        FulfillmentRoutingService.transition_fulfillment_status(
            db=db_session, fulfillment_id=ff.id, new_status="PICKED", user_id=user.id
        )
    assert exc2.value.status_code == 400

    # 4. Bước 3: PACKED -> SHIPPED (Trigger xuất kho FEFO & StockMovement DISPATCH)
    FulfillmentRoutingService.transition_fulfillment_status(
        db=db_session, fulfillment_id=ff.id, new_status="SHIPPED", user_id=user.id
    )
    db_session.refresh(ff)
    db_session.refresh(stock)
    db_session.refresh(res)
    assert ff.status == "SHIPPED"
    assert stock.quantity_on_hand == 45  # 50 - 5 = 45
    assert stock.quantity_reserved == 0  # 5 - 5 = 0
    assert res.status == "FULFILLED"

    # Kiểm tra bản ghi Thẻ kho StockMovement
    mov = db_session.scalar(
        select(StockMovement).where(
            StockMovement.reference_id == ff.fulfillment_code,
            StockMovement.movement_type == "DISPATCH",
        )
    )
    assert mov is not None
    assert mov.quantity == -5
    assert mov.balance_after == 45

    # 5. Bước 4: SHIPPED -> DELIVERED
    FulfillmentRoutingService.transition_fulfillment_status(
        db=db_session, fulfillment_id=ff.id, new_status="DELIVERED", user_id=user.id
    )
    db_session.refresh(ff)
    assert ff.status == "DELIVERED"


# ==============================================================================
# TEST 2: INSPECTION MISSING DATA REJECTION (ITEM 2)
# ==============================================================================

def test_return_inspection_requires_complete_data_and_prohibits_fake_restock(db_session: Session):
    """
    Kiểm tra kiểm định thuốc:
    - Không có giá trị mặc định True / RESTOCK / SEALED
    - Nộp biên bản thiếu chỉ số kiểm định bị từ chối với HTTP 400
    - Không đạt tiêu chuẩn an toàn (False) tuyệt đối cấm RESTOCK
    """
    wh = db_session.scalar(select(Warehouse).where(Warehouse.is_active == True))
    staff = db_session.scalar(select(User).where(User.role == UserRole.WAREHOUSE_STAFF))
    if not staff:
        staff = User(
            email=f"staff_insp_{uuid.uuid4().hex[:6]}@pharmatrust.vn",
            full_name="Staff Insp",
            role=UserRole.WAREHOUSE_STAFF,
            warehouse_id=wh.id,
            is_active=True,
        )
        db_session.add(staff)
        db_session.flush()
    prod = db_session.scalar(select(CanonicalProduct))
    suffix = uuid.uuid4().hex[:6]

    order = Order(
        order_code=f"ORD-RET-INSP-{suffix}",
        user_id=staff.id,
        customer_name="Customer Insp",
        customer_phone="0988776655",
        shipping_address="Inspection Address",
        total_amount=Decimal("200000"),
        order_status="COMPLETED",
        fulfillment_status="DELIVERED",
        assigned_warehouse_id=wh.id,
    )
    db_session.add(order)
    db_session.flush()

    oit = OrderItem(
        order_id=order.id,
        product_id=prod.id,
        product_name=prod.canonical_name,
        price=Decimal("100000"),
        quantity=2,
        subtotal=Decimal("200000"),
    )
    db_session.add(oit)
    db_session.flush()

    ret_req = ReturnRequest(
        return_code=f"RET-INSP-{suffix}",
        order_id=order.id,
        user_id=staff.id,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        reason_code="DAMAGED_DELIVERY",
        reason_text="Hàng lỗi",
        status=ReturnStatus.INSPECTING.value,
    )
    db_session.add(ret_req)
    db_session.flush()

    ret_item = ReturnItem(
        return_request_id=ret_req.id,
        order_item_id=oit.id,
        product_id=prod.id,
        product_name=prod.canonical_name,
        requested_quantity=2,
        original_quantity=2,
        unit_price_at_purchase=oit.price,
        net_paid_amount=oit.subtotal,
        requested_refund_amount=oit.subtotal,
    )
    db_session.add(ret_item)
    db_session.flush()

    case = WarehouseReturnCase(
        case_code=f"WRC-INSP-{suffix}",
        return_request_id=ret_req.id,
        warehouse_id=wh.id,
        status=ReturnStatus.INSPECTING.value,
    )
    db_session.add(case)
    db_session.flush()

    ret_item.warehouse_return_case_id = case.id
    ret_item.warehouse_id = wh.id
    db_session.commit()

    # 1. Model ReturnInspection không có default True / RESTOCK
    insp_empty = ReturnInspection(case_id=case.id, return_item_id=ret_item.id)
    assert insp_empty.seal_intact is None
    assert insp_empty.batch_matched is None
    assert insp_empty.expiry_matched is None
    assert insp_empty.storage_condition_ok is None
    assert insp_empty.suggested_action is None

    # 2. Nộp biên bản kiểm tra khi chưa có bản ghi kiểm định -> Chặn 400
    with pytest.raises(HTTPException) as exc1:
        WarehouseReturnService.staff_submit_inspection(
            db=db_session, case_code=case.case_code, staff_user=staff, warehouse_id=wh.id
        )
    assert exc1.value.status_code == 400
    assert "đầy đủ" in exc1.value.detail

    # 3. Ghi nhận kiểm định nhưng thiếu trường storage_condition_ok
    insp_incomplete = ReturnInspection(
        case_id=case.id,
        return_item_id=ret_item.id,
        package_condition="DAMAGED",
        seal_intact=False,
        batch_matched=True,
        expiry_matched=True,
        storage_condition_ok=None,  # Thiếu chỉ số
        suggested_action="RESTOCK",
    )
    db_session.add(insp_incomplete)
    db_session.commit()
    db_session.expire_all()

    with pytest.raises(HTTPException) as exc2:
        WarehouseReturnService.staff_submit_inspection(
            db=db_session, case_code=case.case_code, staff_user=staff, warehouse_id=wh.id
        )
    assert exc2.value.status_code == 400
    assert "thiếu chỉ số an toàn bắt buộc" in exc2.value.detail

    # 4. Tem rách (seal_intact=False) mà đề xuất RESTOCK -> Chặn 400
    insp = db_session.scalar(select(ReturnInspection).where(ReturnInspection.id == insp_incomplete.id))
    insp.storage_condition_ok = True
    insp.suggested_action = "RESTOCK"
    db_session.commit()
    db_session.expire_all()

    with pytest.raises(HTTPException) as exc3:
        WarehouseReturnService.staff_submit_inspection(
            db=db_session, case_code=case.case_code, staff_user=staff, warehouse_id=wh.id
        )
    assert exc3.value.status_code == 400
    assert "Nghiêm cấm đề xuất hoặc nhập lại kho bán (RESTOCK)" in exc3.value.detail


# ==============================================================================
# TEST 3: NO AUTO-RAISING APPROVED QUANTITY (ITEM 3)
# ==============================================================================

def test_manager_approve_does_not_auto_raise_approved_quantity(db_session: Session):
    """
    Kiểm tra Quản lý duyệt ca hoàn:
    - Không tự động gán approved_quantity = requested_quantity khi duyệt mặc định
    - Khi approved_quantity = 0 trên tất cả các mặt hàng, cấm duyệt hoàn tiền
    - RefundCalculationService không fallback sang requested_quantity khi accepted_quantity = 0
    """
    wh = db_session.scalar(select(Warehouse).where(Warehouse.is_active == True))
    mgr = db_session.scalar(select(User).where(User.role == UserRole.WAREHOUSE_MANAGER))
    if not mgr:
        mgr = User(
            email=f"mgr_test_{uuid.uuid4().hex[:6]}@pharmatrust.vn",
            full_name="Manager Test",
            role=UserRole.WAREHOUSE_MANAGER,
            warehouse_id=wh.id,
            is_active=True,
        )
        db_session.add(mgr)
        db_session.flush()
    prod = db_session.scalar(select(CanonicalProduct))
    suffix = uuid.uuid4().hex[:6]

    order = Order(
        order_code=f"ORD-RET-MGR-{suffix}",
        user_id=mgr.id,
        customer_name="Customer Mgr",
        customer_phone="0933445566",
        shipping_address="Manager Test Address",
        total_amount=Decimal("300000"),
        order_status="COMPLETED",
        fulfillment_status="DELIVERED",
        assigned_warehouse_id=wh.id,
    )
    db_session.add(order)
    db_session.flush()

    oit = OrderItem(
        order_id=order.id,
        product_id=prod.id,
        product_name=prod.canonical_name,
        price=Decimal("150000"),
        quantity=2,
        subtotal=Decimal("300000"),
    )
    db_session.add(oit)
    db_session.flush()

    ret_req = ReturnRequest(
        return_code=f"RET-MGR-{suffix}",
        order_id=order.id,
        user_id=mgr.id,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        reason_code="WRONG_ITEM",
        reason_text="Giao sai thuốc",
        status=ReturnStatus.WAITING_MANAGER_APPROVAL.value,
    )
    db_session.add(ret_req)
    db_session.flush()

    ret_item = ReturnItem(
        return_request_id=ret_req.id,
        order_item_id=oit.id,
        product_id=prod.id,
        product_name=prod.canonical_name,
        requested_quantity=2,
        original_quantity=2,
        approved_quantity=0,
        unit_price_at_purchase=oit.price,
        net_paid_amount=oit.subtotal,
        requested_refund_amount=oit.subtotal,
    )
    db_session.add(ret_item)
    db_session.flush()

    case = WarehouseReturnCase(
        case_code=f"WRC-MGR-{suffix}",
        return_request_id=ret_req.id,
        warehouse_id=wh.id,
        status=ReturnStatus.WAITING_MANAGER_APPROVAL.value,
    )
    db_session.add(case)
    db_session.flush()

    ret_item.warehouse_return_case_id = case.id
    ret_item.warehouse_id = wh.id
    db_session.commit()

    # Thêm biên bản kiểm tra: Hàng hỏng, loại bỏ toàn bộ (accepted_quantity = 0)
    insp = ReturnInspection(
        case_id=case.id,
        return_item_id=ret_item.id,
        received_quantity=2,
        accepted_quantity=0,  # 0 mặt hàng được chấp thuận
        rejected_quantity=2,
        package_condition="DAMAGED",
        seal_intact=False,
        batch_matched=True,
        expiry_matched=True,
        storage_condition_ok=False,
        suggested_action="DISPOSE",
    )
    db_session.add(insp)
    db_session.commit()

    # 1. Duyệt không truyền items_approval: Bắt buộc fail-closed yêu cầu Quản lý kho duyệt chi tiết
    with pytest.raises(HTTPException) as exc1:
        WarehouseReturnService.manager_approve_case(
            db=db_session, case_code=case.case_code, manager_user=mgr, warehouse_id=wh.id
        )
    assert exc1.value.status_code == 400
    assert any(msg in exc1.value.detail for msg in ["Tổng số lượng sản phẩm được duyệt là 0", "Vui lòng cung cấp danh sách phê duyệt chi tiết"])

    # Khi tổng approved = 0, phải chặn không cho duyệt hoàn tiền
    with pytest.raises(HTTPException) as exc1_zero:
        WarehouseReturnService.manager_approve_case(
            db=db_session,
            case_code=case.case_code,
            manager_user=mgr,
            warehouse_id=wh.id,
            items_approval=[{
                "return_item_id": ret_item.id,
                "approved_quantity": 0,
                "rejected_quantity": 2,
                "rejection_reason": "Hàng hỏng hoàn toàn",
            }],
        )
    assert exc1_zero.value.status_code == 400
    assert "Tổng số lượng sản phẩm được duyệt là 0" in exc1_zero.value.detail

    # Đảm bảo ret_item.approved_quantity KHÔNG bị nâng lên requested_quantity (2)
    db_session.refresh(ret_item)
    assert ret_item.approved_quantity == 0

    # 2. RefundCalculationService không fallback sang requested_quantity khi accepted_quantity = 0
    calc_res = RefundCalculationService.calculate_return_refund(
        db=db_session,
        order=order,
        return_items=[ret_item],
        reason_code="DAMAGED_DELIVERY",
        include_shipping_fee=False,
    )
    assert calc_res["items_refund_amount"] == Decimal("0.0")


# ==============================================================================
# TEST 4: STAFF SESSION OWNERSHIP & ROLE PROTECTION (ITEM 4)
# ==============================================================================

@pytest.mark.asyncio
async def test_live_chat_staff_ownership_and_role_protection(db_session: Session):
    """
    Kiểm tra bảo vệ phiên chat nhân viên:
    - Nhân viên B không thể giành (claim) phiên của Nhân viên A
    - Nhân viên B không thể chuyển (assign) phiên của Nhân viên A
    - Chuyển phiên tới tài khoản CUSTOMER bị chặn (vai trò không hợp lệ)
    - Nhân viên B không thể gửi tin nhắn hoặc đóng phiên của Nhân viên A
    """
    from app.api.live_chat import (
        claim_session,
        assign_session,
        send_message_as_staff,
        close_session_by_staff,
        AssignStaffRequest,
        SendMessageRequest,
    )
    from app.models.chat_models import LiveChatSession

    staff_a = db_session.scalar(select(User).where(User.role == UserRole.WAREHOUSE_STAFF, User.is_active == True))
    if not staff_a:
        staff_a = User(
            email=f"staff_a_{uuid.uuid4().hex[:6]}@pharmatrust.vn",
            full_name="Staff A",
            role=UserRole.WAREHOUSE_STAFF,
            is_active=True,
        )
        db_session.add(staff_a)
        db_session.flush()

    staff_b = db_session.scalar(select(User).where(User.id != staff_a.id, User.role == UserRole.WAREHOUSE_STAFF, User.is_active == True))
    if not staff_b:
        staff_b = User(
            email=f"staff_b_{uuid.uuid4().hex[:6]}@pharmatrust.vn",
            full_name="Staff B",
            role=UserRole.WAREHOUSE_STAFF,
            is_active=True,
        )
        db_session.add(staff_b)
        db_session.flush()

    customer = db_session.scalar(select(User).where(User.role == UserRole.CUSTOMER, User.is_active == True))
    if not customer:
        customer = User(
            email=f"cust_{uuid.uuid4().hex[:6]}@pharmatrust.vn",
            full_name="Customer Test",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
        db_session.add(customer)
        db_session.flush()

    session = LiveChatSession(
        session_code=f"CHAT-OWNERSHIP-{uuid.uuid4().hex[:6]}",
        customer_name="Test Customer",
        assigned_staff_id=staff_a.id,
        status="ACTIVE",
    )
    db_session.add(session)
    db_session.commit()

    # 1. Staff B cố claim phiên của Staff A -> Bị chặn 403
    with pytest.raises(HTTPException) as exc_claim:
        await claim_session(session_code=session.session_code, staff_user=staff_b, db=db_session)
    assert exc_claim.value.status_code == 403
    assert "đang được nhân viên khác phụ trách" in exc_claim.value.detail

    # 2. Staff B cố chuyển phiên của Staff A -> Bị chặn 403
    with pytest.raises(HTTPException) as exc_assign1:
        await assign_session(
            session_code=session.session_code,
            payload=AssignStaffRequest(staff_id=staff_b.id),
            staff_user=staff_b,
            db=db_session,
        )
    assert exc_assign1.value.status_code == 403

    # 3. Staff A chuyển phiên cho tài khoản CUSTOMER -> Bị chặn 400 (vai trò không hợp lệ)
    with pytest.raises(HTTPException) as exc_assign2:
        await assign_session(
            session_code=session.session_code,
            payload=AssignStaffRequest(staff_id=customer.id),
            staff_user=staff_a,
            db=db_session,
        )
    assert exc_assign2.value.status_code == 400
    assert "vai trò nhân viên hợp lệ" in exc_assign2.value.detail

    # 4. Staff B cố gửi tin nhắn trong phiên của Staff A -> Bị chặn 403
    with pytest.raises(HTTPException) as exc_msg:
        await send_message_as_staff(
            session_code=session.session_code,
            payload=SendMessageRequest(content="Tin nhắn xâm phạm"),
            staff_user=staff_b,
            db=db_session,
        )
    assert exc_msg.value.status_code == 403

    # 5. Staff B cố đóng phiên của Staff A -> Bị chặn 403
    with pytest.raises(HTTPException) as exc_close:
        await close_session_by_staff(session_code=session.session_code, staff_user=staff_b, db=db_session)
    assert exc_close.value.status_code == 403


# ==============================================================================
# TEST 5: NEAREST WAREHOUSE STAFF ROUTING (ITEM 5)
# ==============================================================================

def test_nearest_warehouse_staff_routing(db_session: Session):
    """
    Kiểm tra tự động chuyển chat đến nhân viên thuộc kho gần nhất với vị trí khách hàng.
    """
    wh1 = db_session.scalar(select(Warehouse).where(Warehouse.id == 1))
    wh2 = db_session.scalar(select(Warehouse).where(Warehouse.id == 2))

    if wh1 and wh2 and wh1.lat and wh2.lat:
        staff_wh1 = db_session.scalar(
            select(User).where(User.warehouse_id == wh1.id, User.role == UserRole.WAREHOUSE_STAFF)
        )
        if not staff_wh1:
            staff_wh1 = User(
                email="staff_wh1_test@pharmatrust.vn",
                full_name="Staff Kho 1",
                role=UserRole.WAREHOUSE_STAFF,
                warehouse_id=wh1.id,
                is_active=True,
            )
            db_session.add(staff_wh1)
            db_session.commit()

        # Giả lập vị trí khách hàng rất gần kho 1
        found_staff, found_wh = find_nearest_warehouse_staff(
            db=db_session,
            customer_lat=wh1.lat + 0.001,
            customer_lng=wh1.lng + 0.001,
            customer_city=wh1.province,
        )
        assert found_staff is not None
        assert found_wh is not None
        assert found_wh.id == wh1.id


# ==============================================================================
# TEST 6: CUSTOMER ORDER HISTORY SEARCH & PAGINATION (ITEM 6)
# ==============================================================================

def test_get_my_orders_supports_search_and_pagination(db_session: Session):
    """
    Kiểm tra API lịch sử đơn hàng của khách hàng:
    - Phân trang page, page_size
    - Tính đúng total và total_pages
    - Tìm kiếm theo mã đơn hàng hoặc tên thuốc
    """
    from app.api.orders import get_my_orders

    cust = db_session.scalar(select(User).where(User.role == UserRole.CUSTOMER))
    if not cust:
        cust = User(
            email=f"cust_pg_{uuid.uuid4().hex[:6]}@pharmatrust.vn",
            full_name="Customer Orders",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
        db_session.add(cust)
        db_session.flush()

    prod = db_session.scalar(select(CanonicalProduct))
    suffix = uuid.uuid4().hex[:6]
    code1 = f"ORD-PG-001-{suffix}"
    code2 = f"ORD-PG-002-{suffix}"
    code3 = f"ORD-PG-003-{suffix}"

    # Tạo 3 đơn hàng cho khách này
    order1 = Order(
        order_code=code1,
        user_id=cust.id,
        customer_name=cust.full_name,
        customer_phone=cust.phone or "0900112233",
        shipping_address="Address 1",
        total_amount=Decimal("100000"),
        order_status="PENDING",
    )
    order2 = Order(
        order_code=code2,
        user_id=cust.id,
        customer_name=cust.full_name,
        customer_phone=cust.phone or "0900112233",
        shipping_address="Address 2",
        total_amount=Decimal("200000"),
        order_status="COMPLETED",
    )
    order3 = Order(
        order_code=code3,
        user_id=cust.id,
        customer_name=cust.full_name,
        customer_phone=cust.phone or "0900112233",
        shipping_address="Address 3",
        total_amount=Decimal("300000"),
        order_status="COMPLETED",
    )
    db_session.add_all([order1, order2, order3])
    db_session.flush()

    it1 = OrderItem(order_id=order1.id, product_id=prod.id, product_name=f"Panadol Extra {suffix}", price=Decimal("50000"), quantity=2, subtotal=Decimal("100000"))
    it2 = OrderItem(order_id=order2.id, product_id=prod.id, product_name=f"Berberin {suffix}", price=Decimal("100000"), quantity=2, subtotal=Decimal("200000"))
    it3 = OrderItem(order_id=order3.id, product_id=prod.id, product_name=f"Vitamin C {suffix}", price=Decimal("150000"), quantity=2, subtotal=Decimal("300000"))
    db_session.add_all([it1, it2, it3])
    db_session.commit()

    # 1. Phân trang 2 đơn / trang
    res_p1 = get_my_orders(page=1, page_size=2, current_user=cust, db=db_session)
    assert len(res_p1["items"]) <= 2
    assert res_p1["total"] >= 3
    assert res_p1["total_pages"] >= 2

    # 2. Tìm kiếm theo mã đơn code1
    res_s1 = get_my_orders(search=code1, current_user=cust, db=db_session)
    assert any(o["order_code"] == code1 for o in res_s1["items"])
    assert not any(o["order_code"] == code2 for o in res_s1["items"])

    # 3. Tìm kiếm theo tên thuốc "Berberin"
    res_s2 = get_my_orders(search=f"Berberin {suffix}", current_user=cust, db=db_session)
    assert any(o["order_code"] == code2 for o in res_s2["items"])
    assert not any(o["order_code"] == code1 for o in res_s2["items"])
