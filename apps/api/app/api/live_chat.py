from __future__ import annotations

import json
import os
import re
import secrets
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_current_user
from app.core.config import settings
from app.core.security import decode_token
from app.db.session import SessionLocal, get_db
from app.models import LiveChatAttachment, LiveChatMessage, LiveChatSession, User
from app.models.enums import UserRole
from app.services.live_chat_service import chat_manager

router = APIRouter(prefix="/live-chat", tags=["Live Chat Người Thật H4CARE"])


def utcnow() -> datetime:
    return datetime.now(UTC)


def authenticate_user_token(token_str: str, db: Session) -> User | None:
    """
    Xác thực JWT access token nghiêm ngặt:
    - Kiểm tra chữ ký và hạn dùng.
    - Bắt buộc type == 'access'.
    - Bắt buộc người dùng tồn tại và is_active == True.
    - Bắt buộc token_version trong payload bằng User.token_version.
    """
    if not token_str or not str(token_str).strip():
        return None
    try:
        payload = decode_token(str(token_str).strip(), "access")
        if payload.get("type") != "access":
            return None
        user_id = int(payload.get("sub", 0))
        if not user_id:
            return None
        user = db.get(User, user_id)
        if not user or not user.is_active:
            return None
        token_ver = payload.get("token_version")
        if token_ver is None:
            return None
        if getattr(user, "token_version", 1) != token_ver:
            return None
        return user
    except Exception:
        return None



CHAT_UPLOAD_DIR = settings.storage_root / "uploads" / "chat"
CHAT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ===================== SCHEMAS =====================

class InitSessionRequest(BaseModel):
    customer_name: Optional[str] = Field(default=None, max_length=100)
    customer_email: Optional[str] = Field(default=None, max_length=150)
    customer_phone: Optional[str] = Field(default=None, max_length=20)
    subject: Optional[str] = Field(default=None, max_length=255)
    initial_context: Optional[str] = Field(default=None, max_length=5000)
    shared_ai_history: bool = Field(default=True)
    lat: Optional[float] = Field(default=None, description="Vĩ độ của khách hàng")
    lng: Optional[float] = Field(default=None, description="Kinh độ của khách hàng")
    address: Optional[str] = Field(default=None, max_length=500, description="Địa chỉ nhận hàng của khách")
    city: Optional[str] = Field(default=None, max_length=100, description="Tỉnh/Thành phố của khách")


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    attachment_url: Optional[str] = Field(default=None, max_length=1000)
    attachment_type: Optional[str] = Field(default=None, max_length=50)
    client_msg_id: Optional[str] = Field(default=None, max_length=64)


class CloseSessionRequest(BaseModel):
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    feedback: Optional[str] = Field(default=None, max_length=1000)


class AssignStaffRequest(BaseModel):
    staff_id: int


class MessageResponse(BaseModel):
    id: int
    session_id: int
    sender_type: str
    sender_name: str
    sender_role_title: Optional[str]
    content: str
    attachment_url: Optional[str]
    attachment_type: Optional[str]
    client_msg_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SessionDetailResponse(BaseModel):
    id: int
    session_code: str
    customer_name: str
    customer_email: Optional[str]
    customer_phone: Optional[str]
    customer_id: Optional[int]
    guest_session_token: Optional[str]
    assigned_staff_id: Optional[int]
    assigned_staff_name: Optional[str]
    assigned_staff_title: Optional[str]
    status: str
    subject: Optional[str]
    initial_context: Optional[str]
    rating: Optional[int]
    feedback: Optional[str]
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]
    last_message_at: datetime
    messages: List[MessageResponse] = []


class StaffInfo(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    role_title: str


# ===================== HELPER AUTH =====================

def get_current_staff_user(user: User = Depends(get_current_user)) -> User:
    if user.role not in [UserRole.ADMIN, UserRole.PHARMACIST, UserRole.WAREHOUSE_MANAGER, UserRole.WAREHOUSE_STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập cổng nhân viên Live Chat",
        )
    return user


def get_role_title(user: Optional[User]) -> str:
    if not user:
        return "Khách hàng"
    if user.role == UserRole.PHARMACIST:
        return "Dược sĩ chuyên môn"
    if user.role == UserRole.ADMIN:
        return "Quản trị viên H4CARE"
    if user.role in [UserRole.WAREHOUSE_MANAGER, UserRole.WAREHOUSE_STAFF]:
        return "Chuyên viên hỗ trợ H4CARE"
    return "Khách hàng"


def verify_session_access(
    session: LiveChatSession,
    user: Optional[User],
    guest_token: Optional[str],
) -> None:
    """Xác minh quyền truy cập phiên chat của khách hàng (chống IDOR)."""
    # Nếu là nhân viên / admin thì cho phép
    if user and user.role in [UserRole.ADMIN, UserRole.PHARMACIST, UserRole.WAREHOUSE_MANAGER, UserRole.WAREHOUSE_STAFF]:
        return

    # Nếu là khách đã đăng nhập
    if user and session.customer_id and session.customer_id == user.id:
        return

    # Nếu là khách vãng lai khớp guest_token
    if guest_token and session.guest_session_token and guest_token == session.guest_session_token:
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền truy cập phiên trò chuyện này")


# ===================== ENDPOINTS KHÁCH HÀNG =====================

def find_nearest_warehouse_staff(
    db: Session,
    customer_lat: Optional[float] = None,
    customer_lng: Optional[float] = None,
    customer_city: Optional[str] = None,
    current_user: Optional[User] = None,
) -> tuple[Optional[User], Optional[Any]]:
    """
    Tự động tìm nhân viên tại chi nhánh kho gần nhất với vị trí khách hàng.
    Ưu tiên:
    1. Nhân viên thuộc kho gần nhất đang trực tuyến (online trên chat WebSocket).
    2. Nhân viên thuộc kho gần nhất đang hoạt động.
    """
    from app.models import CustomerAddress, Order, Warehouse
    from app.services.geo_service import calculate_haversine_distance

    target_lat = customer_lat
    target_lng = customer_lng
    target_city = customer_city

    if (target_lat is None or target_lng is None) and current_user:
        addr = db.scalar(
            select(CustomerAddress)
            .where(CustomerAddress.user_id == current_user.id)
            .order_by(CustomerAddress.is_default.desc(), CustomerAddress.id.desc())
        )
        if addr:
            if addr.latitude is not None and addr.longitude is not None:
                target_lat = float(addr.latitude)
                target_lng = float(addr.longitude)
            if not target_city:
                target_city = addr.city

        if target_lat is None or target_lng is None:
            last_order = db.scalar(
                select(Order)
                .where(Order.user_id == current_user.id)
                .order_by(Order.created_at.desc())
            )
            if last_order:
                if last_order.lat is not None and last_order.lng is not None:
                    target_lat = float(last_order.lat)
                    target_lng = float(last_order.lng)
                if not target_city:
                    target_city = last_order.shipping_city

    warehouses = db.scalars(
        select(Warehouse).where(Warehouse.is_active.is_(True))
    ).all()
    if not warehouses:
        return None, None

    if target_lat is not None and target_lng is not None:
        sorted_warehouses = []
        for wh in warehouses:
            if wh.lat is not None and wh.lng is not None:
                dist = calculate_haversine_distance(target_lat, target_lng, wh.lat, wh.lng)
            else:
                dist = 99999.0
            sorted_warehouses.append((dist, wh))
        sorted_warehouses.sort(key=lambda x: x[0])
        ordered_whs = [w[1] for w in sorted_warehouses]
    elif target_city:
        norm_city = target_city.lower()
        same_city_whs = [
            w for w in warehouses
            if (w.province and (norm_city in w.province.lower() or w.province.lower() in norm_city))
            or (w.address and norm_city in w.address.lower())
        ]
        other_whs = [w for w in warehouses if w not in same_city_whs]
        ordered_whs = same_city_whs + other_whs
    else:
        return None, None

    valid_roles = [UserRole.WAREHOUSE_STAFF, UserRole.WAREHOUSE_MANAGER, UserRole.PHARMACIST]

    # Vòng 1: Nhân viên online tại kho gần nhất
    for wh in ordered_whs:
        staff_list = db.scalars(
            select(User).where(
                User.warehouse_id == wh.id,
                User.role.in_(valid_roles),
                User.is_active.is_(True),
            )
        ).all()
        online_staff = [s for s in staff_list if chat_manager.is_staff_online(s.id)]
        if online_staff:
            return online_staff[0], wh

    # Vòng 2: Nhân viên active bất kỳ tại kho gần nhất
    for wh in ordered_whs:
        staff_list = db.scalars(
            select(User).where(
                User.warehouse_id == wh.id,
                User.role.in_(valid_roles),
                User.is_active.is_(True),
            )
        ).all()
        if staff_list:
            return staff_list[0], wh

    # Fallback: Bất kỳ nhân viên nào online trên toàn hệ thống
    for u_id in chat_manager.staff_connections.keys():
        u = db.get(User, u_id)
        if u and u.is_active and u.role in valid_roles:
            wh = db.get(Warehouse, u.warehouse_id) if u.warehouse_id else None
            return u, wh

    return None, None


@router.get("/staff-status")
def check_staff_status():
    """Kiểm tra thực tế trạng thái online của đội ngũ nhân viên tư vấn."""
    is_online = chat_manager.is_any_staff_online()
    count = chat_manager.get_online_staff_count()
    return {
        "is_online": is_online,
        "online_count": count,
        "support_hours": "08:00 - 21:00 hàng ngày",
        "hotline": "1800 6828",
    }


@router.post("/sessions")
async def create_or_resume_session(
    payload: InitSessionRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    x_chat_guest_token: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Tạo phiên Live Chat mới giữa khách hàng và nhân viên.
    Nếu khách có phiên WAITING/ACTIVE gần nhất chưa đóng, cho phép tiếp tục phiên đó.
    """
    # 1. Kiểm tra xem có phiên cũ còn mở không
    existing_session = None
    if current_user:
        existing_session = db.scalar(
            select(LiveChatSession)
            .where(
                LiveChatSession.customer_id == current_user.id,
                LiveChatSession.status.in_(["WAITING", "ACTIVE"]),
            )
            .order_by(LiveChatSession.created_at.desc())
        )
    elif x_chat_guest_token:
        existing_session = db.scalar(
            select(LiveChatSession)
            .where(
                LiveChatSession.guest_session_token == x_chat_guest_token,
                LiveChatSession.status.in_(["WAITING", "ACTIVE"]),
            )
            .order_by(LiveChatSession.created_at.desc())
        )

    if existing_session:
        # Nếu có tin nhắn mới hoặc yêu cầu mới, cập nhật context nếu có
        if payload.initial_context and payload.shared_ai_history and not existing_session.initial_context:
            existing_session.initial_context = payload.initial_context
            db.commit()
            db.refresh(existing_session)

        return _build_session_detail(existing_session)

    # 2. Tạo phiên mới
    date_prefix = datetime.now(UTC).strftime("%y%m%d")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    session_code = f"CHAT-{date_prefix}-{unique_suffix}"
    guest_token = x_chat_guest_token or str(uuid.uuid4())

    customer_name = payload.customer_name
    if not customer_name and current_user:
        customer_name = current_user.full_name
    if not customer_name:
        customer_name = f"Khách #{unique_suffix[:4]}"

    customer_email = payload.customer_email or (current_user.email if current_user else None)
    customer_phone = payload.customer_phone or (current_user.phone if current_user else None)

    context_str = payload.initial_context if payload.shared_ai_history else None

    # Tự động tìm và điều phối đến nhân viên kho gần nhất với vị trí khách hàng
    assigned_staff, nearest_wh = find_nearest_warehouse_staff(
        db=db,
        customer_lat=payload.lat,
        customer_lng=payload.lng,
        customer_city=payload.city,
        current_user=current_user,
    )

    initial_status = "WAITING"
    assigned_staff_id = assigned_staff.id if assigned_staff else None

    new_session = LiveChatSession(
        session_code=session_code,
        customer_id=current_user.id if current_user else None,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        guest_session_token=guest_token,
        assigned_staff_id=assigned_staff_id,
        status=initial_status,
        subject=payload.subject or "Tư vấn sức khỏe & đơn thuốc",
        initial_context=context_str,
        created_at=utcnow(),
        updated_at=utcnow(),
        last_message_at=utcnow(),
    )
    db.add(new_session)
    db.flush()

    # Thêm tin nhắn hệ thống chào mừng & thông báo trạng thái
    welcome_msg = (
        "Xin chào quý khách! Hệ thống đã kết nối bạn tới kênh **Tư vấn trực tiếp H4CARE**.\n\n"
        "Nhân viên tư vấn đang được thông báo để tiếp nhận cuộc trò chuyện. Quý khách vui lòng gửi câu hỏi hoặc mô tả triệu chứng/đơn thuốc tại đây nhé!"
    )
    if assigned_staff:
        staff_title = get_role_title(assigned_staff)
        wh_suffix = f" tại **{nearest_wh.name}**" if nearest_wh else ""
        welcome_msg += f"\n\n📍 Cuộc trò chuyện đã được tự động kết nối tới **{staff_title} {assigned_staff.full_name}**{wh_suffix} (kho gần nhất với vị trí của bạn)."
    elif not chat_manager.is_any_staff_online():
        welcome_msg += (
            "\n\n*⚠️ Hiện tại không có nhân viên trực tuyến (khung giờ trực: 08:00 - 21:00). "
            "Quý khách vui lòng để lại lời nhắn cùng số điện thoại, nhân viên H4CARE sẽ liên hệ lại ngay khi vào ca.*"
        )

    sys_msg = LiveChatMessage(
        session_id=new_session.id,
        sender_type="SYSTEM",
        sender_id=assigned_staff.id if assigned_staff else None,
        sender_name="H4CARE System",
        sender_role_title="Hệ thống",
        content=welcome_msg,
        created_at=utcnow(),
    )
    db.add(sys_msg)

    # Nếu có tóm tắt từ AI mà khách đồng ý chia sẻ, tạo thêm tin nhắn tóm tắt để nhân viên nắm bắt
    if context_str:
        summary_msg = LiveChatMessage(
            session_id=new_session.id,
            sender_type="SYSTEM",
            sender_id=None,
            sender_name="Tóm tắt câu hỏi AI",
            sender_role_title="Ngữ cảnh chuyển tiếp",
            content=f"📋 **Khách hàng đã đồng ý chuyển tiếp tóm tắt từ Trợ lý AI:**\n{context_str}",
            created_at=utcnow(),
        )
        db.add(summary_msg)

    db.commit()
    db.refresh(new_session)

    # Thông báo cho tất cả nhân viên online qua WebSocket
    await chat_manager.broadcast_to_staff(
        "NEW_SESSION",
        {
            "session_code": new_session.session_code,
            "customer_name": new_session.customer_name,
            "subject": new_session.subject,
            "assigned_staff_id": new_session.assigned_staff_id,
            "created_at": new_session.created_at.isoformat(),
        },
    )
    if assigned_staff:
        await chat_manager.broadcast_to_session(
            session_code=new_session.session_code,
            message_data={
                "type": "SESSION_CLAIMED",
                "session_code": new_session.session_code,
                "assigned_staff_id": assigned_staff.id,
                "assigned_staff_name": assigned_staff.full_name,
                "assigned_staff_title": get_role_title(assigned_staff),
            },
            assigned_staff_id=assigned_staff.id,
        )

    return _build_session_detail(new_session)


@router.get("/sessions/{session_code}")
def get_session_detail(
    session_code: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    x_chat_guest_token: Optional[str] = Header(None),
    guest_token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Lấy chi tiết phiên chat và lịch sử tin nhắn."""
    session = db.scalar(
        select(LiveChatSession).where(LiveChatSession.session_code == session_code)
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên trò chuyện")

    effective_guest_token = x_chat_guest_token or guest_token
    verify_session_access(session, current_user, effective_guest_token)

    return _build_session_detail(session)


@router.post("/sessions/{session_code}/messages")
async def send_message_as_customer(
    session_code: str,
    payload: SendMessageRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    x_chat_guest_token: Optional[str] = Header(None),
    guest_token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Khách hàng gửi tin nhắn vào phiên chat."""
    session = db.scalar(
        select(LiveChatSession).where(LiveChatSession.session_code == session_code)
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên trò chuyện")

    effective_guest_token = x_chat_guest_token or guest_token
    verify_session_access(session, current_user, effective_guest_token)

    if session.status == "CLOSED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cuộc trò chuyện này đã kết thúc")

    # Idempotency check: nếu trùng client_msg_id thì trả về tin cũ
    if payload.client_msg_id:
        existing_msg = db.scalar(
            select(LiveChatMessage).where(
                LiveChatMessage.session_id == session.id,
                LiveChatMessage.client_msg_id == payload.client_msg_id,
            )
        )
        if existing_msg:
            return _build_message_response(existing_msg)

    sender_name = current_user.full_name if current_user else session.customer_name
    sender_id = current_user.id if current_user else None

    msg = LiveChatMessage(
        session_id=session.id,
        sender_type="CUSTOMER",
        sender_id=sender_id,
        sender_name=sender_name,
        sender_role_title="Khách hàng",
        content=payload.content.strip(),
        attachment_url=payload.attachment_url,
        attachment_type=payload.attachment_type,
        client_msg_id=payload.client_msg_id,
        created_at=utcnow(),
    )
    session.last_message_at = utcnow()
    session.updated_at = utcnow()
    db.add(msg)
    db.commit()
    db.refresh(msg)

    resp_data = _build_message_response(msg)

    # Realtime broadcast qua WebSocket
    await chat_manager.broadcast_to_session(
        session_code=session.session_code,
        message_data={
            "type": "NEW_MESSAGE",
            "session_code": session.session_code,
            "message": resp_data,
        },
        assigned_staff_id=session.assigned_staff_id,
    )

    return resp_data


@router.post("/sessions/{session_code}/close")
async def close_session_by_customer(
    session_code: str,
    payload: CloseSessionRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    x_chat_guest_token: Optional[str] = Header(None),
    guest_token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Khách hàng kết thúc phiên trò chuyện và gửi đánh giá (rating/feedback)."""
    session = db.scalar(
        select(LiveChatSession).where(LiveChatSession.session_code == session_code)
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên trò chuyện")

    effective_guest_token = x_chat_guest_token or guest_token
    verify_session_access(session, current_user, effective_guest_token)

    session.status = "CLOSED"
    session.closed_at = utcnow()
    session.closed_by_id = current_user.id if current_user else None
    if payload.rating:
        session.rating = payload.rating
    if payload.feedback:
        session.feedback = payload.feedback
    session.updated_at = utcnow()

    # Thêm tin nhắn hệ thống thông báo kết thúc
    end_msg = LiveChatMessage(
        session_id=session.id,
        sender_type="SYSTEM",
        sender_id=None,
        sender_name="H4CARE System",
        sender_role_title="Hệ thống",
        content="Khách hàng đã kết thúc cuộc trò chuyện. Cảm ơn bạn đã tin tưởng dịch vụ H4CARE!",
        created_at=utcnow(),
    )
    db.add(end_msg)
    db.commit()

    # Broadcast sự kiện phiên đã đóng
    await chat_manager.broadcast_to_session(
        session_code=session.session_code,
        message_data={
            "type": "SESSION_CLOSED",
            "session_code": session.session_code,
            "closed_by": "CUSTOMER",
            "rating": session.rating,
        },
        assigned_staff_id=session.assigned_staff_id,
    )

    return {"status": "success", "message": "Đã kết thúc cuộc trò chuyện thành công"}


# ===================== ENDPOINTS NHÂN VIÊN / ADMIN =====================

@router.get("/staff/sessions")
def list_staff_sessions(
    status_filter: Optional[str] = Query(None, description="WAITING | ACTIVE | CLOSED | ALL | MY_CHATS"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    staff_user: User = Depends(get_current_staff_user),
    db: Session = Depends(get_db),
):
    """
    Danh sách phiên chat cho nhân viên / Admin:
    - Admin: xem được tất cả.
    - Staff/Manager: xem các phiên WAITING (chưa ai nhận) và các phiên được gán cho chính mình.
    """
    query = select(LiveChatSession)

    # Phân quyền truy cập
    if staff_user.role != UserRole.ADMIN:
        # Nhân viên chỉ thấy phiên chưa gán (WAITING) hoặc phiên được gán cho chính họ
        query = query.where(
            or_(
                LiveChatSession.assigned_staff_id == staff_user.id,
                LiveChatSession.assigned_staff_id.is_(None),
            )
        )

    # Lọc trạng thái
    if status_filter == "MY_CHATS":
        query = query.where(LiveChatSession.assigned_staff_id == staff_user.id, LiveChatSession.status == "ACTIVE")
    elif status_filter and status_filter != "ALL":
        query = query.where(LiveChatSession.status == status_filter)

    # Tìm kiếm
    if search:
        s = f"%{search.strip()}%"
        query = query.where(
            or_(
                LiveChatSession.session_code.ilike(s),
                LiveChatSession.customer_name.ilike(s),
                LiveChatSession.customer_phone.ilike(s),
                LiveChatSession.customer_email.ilike(s),
                LiveChatSession.subject.ilike(s),
            )
        )

    # Đếm tổng số bản ghi
    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    # Sắp xếp: WAITING lên đầu, sau đó theo last_message_at giảm dần
    query = query.order_by(
        LiveChatSession.status.desc(),
        LiveChatSession.last_message_at.desc(),
    )

    offset = (page - 1) * page_size
    sessions = db.scalars(query.offset(offset).limit(page_size)).all()

    items = [_build_session_detail(s) for s in sessions]

    # Thống kê nhanh badge
    waiting_count = db.scalar(
        select(func.count(LiveChatSession.id)).where(LiveChatSession.status == "WAITING")
    ) or 0
    my_active_count = db.scalar(
        select(func.count(LiveChatSession.id)).where(
            LiveChatSession.assigned_staff_id == staff_user.id,
            LiveChatSession.status == "ACTIVE",
        )
    ) or 0

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "waiting_count": waiting_count,
        "my_active_count": my_active_count,
    }


@router.post("/staff/sessions/{session_code}/claim")
async def claim_session(
    session_code: str,
    staff_user: User = Depends(get_current_staff_user),
    db: Session = Depends(get_db),
):
    """Nhân viên tiếp nhận (claim) cuộc trò chuyện đang chờ."""
    session = db.scalar(
        select(LiveChatSession).where(LiveChatSession.session_code == session_code)
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên trò chuyện")

    if session.status == "CLOSED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phiên trò chuyện đã kết thúc")

    # Chống giành phiên đang do nhân viên khác phụ trách (trừ ADMIN)
    if session.assigned_staff_id and session.assigned_staff_id != staff_user.id and staff_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuộc trò chuyện này đang được nhân viên khác phụ trách. Bạn không thể giành phiên.",
        )

    session.assigned_staff_id = staff_user.id
    session.status = "ACTIVE"
    session.updated_at = utcnow()

    staff_title = get_role_title(staff_user)

    # Ghi tin nhắn hệ thống thông báo nhân viên đã tiếp nhận
    join_msg = LiveChatMessage(
        session_id=session.id,
        sender_type="SYSTEM",
        sender_id=staff_user.id,
        sender_name="H4CARE System",
        sender_role_title="Hệ thống",
        content=f"**{staff_title} {staff_user.full_name}** đã tiếp nhận cuộc trò chuyện và sẽ hỗ trợ quý khách ngay bây giờ.",
        created_at=utcnow(),
    )
    db.add(join_msg)
    db.commit()
    db.refresh(session)

    # Realtime broadcast thông báo đã gán cho cả khách và nhân viên
    await chat_manager.broadcast_to_session(
        session_code=session.session_code,
        message_data={
            "type": "SESSION_CLAIMED",
            "session_code": session.session_code,
            "assigned_staff_id": staff_user.id,
            "assigned_staff_name": staff_user.full_name,
            "assigned_staff_title": staff_title,
        },
        assigned_staff_id=staff_user.id,
    )

    return _build_session_detail(session)


@router.post("/staff/sessions/{session_code}/assign")
async def assign_session(
    session_code: str,
    payload: AssignStaffRequest,
    staff_user: User = Depends(get_current_staff_user),
    db: Session = Depends(get_db),
):
    """Phân công cuộc trò chuyện cho nhân viên khác."""
    session = db.scalar(
        select(LiveChatSession).where(LiveChatSession.session_code == session_code)
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên trò chuyện")

    # Kiểm tra quyền: Chỉ nhân viên đang phụ trách hoặc ADMIN mới được chuyển phiên
    if session.assigned_staff_id and session.assigned_staff_id != staff_user.id and staff_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền chuyển cuộc trò chuyện đang do nhân viên khác phụ trách.",
        )

    target_staff = db.get(User, payload.staff_id)
    if not target_staff or not target_staff.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nhân viên được chọn không tồn tại hoặc đã bị vô hiệu hóa.")

    valid_staff_roles = {UserRole.ADMIN, UserRole.PHARMACIST, UserRole.WAREHOUSE_MANAGER, UserRole.WAREHOUSE_STAFF}
    if target_staff.role not in valid_staff_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản đích không có vai trò nhân viên hợp lệ để tiếp nhận phiên tư vấn.",
        )

    session.assigned_staff_id = target_staff.id
    session.status = "ACTIVE"
    session.updated_at = utcnow()

    target_title = get_role_title(target_staff)

    transfer_msg = LiveChatMessage(
        session_id=session.id,
        sender_type="SYSTEM",
        sender_id=staff_user.id,
        sender_name="H4CARE System",
        sender_role_title="Hệ thống",
        content=f"Cuộc trò chuyện đã được chuyển tiếp tới **{target_title} {target_staff.full_name}**.",
        created_at=utcnow(),
    )
    db.add(transfer_msg)
    db.commit()
    db.refresh(session)

    # Broadcast tới cả hai phía
    await chat_manager.broadcast_to_session(
        session_code=session.session_code,
        message_data={
            "type": "SESSION_ASSIGNED",
            "session_code": session.session_code,
            "assigned_staff_id": target_staff.id,
            "assigned_staff_name": target_staff.full_name,
            "assigned_staff_title": target_title,
        },
        assigned_staff_id=target_staff.id,
    )

    return _build_session_detail(session)


@router.post("/staff/sessions/{session_code}/messages")
async def send_message_as_staff(
    session_code: str,
    payload: SendMessageRequest,
    staff_user: User = Depends(get_current_staff_user),
    db: Session = Depends(get_db),
):
    """Nhân viên gửi tin nhắn trả lời khách hàng."""
    session = db.scalar(
        select(LiveChatSession).where(LiveChatSession.session_code == session_code)
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên trò chuyện")

    # Kiểm tra quyền: Chỉ nhân viên đang phụ trách hoặc ADMIN mới được gửi tin nhắn
    if session.assigned_staff_id and session.assigned_staff_id != staff_user.id and staff_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền gửi tin nhắn trong cuộc trò chuyện do nhân viên khác đang phụ trách.",
        )

    # Tự động gán nếu chưa ai nhận
    if not session.assigned_staff_id:
        session.assigned_staff_id = staff_user.id
        session.status = "ACTIVE"

    # Idempotency check
    if payload.client_msg_id:
        existing = db.scalar(
            select(LiveChatMessage).where(
                LiveChatMessage.session_id == session.id,
                LiveChatMessage.client_msg_id == payload.client_msg_id,
            )
        )
        if existing:
            return _build_message_response(existing)

    staff_title = get_role_title(staff_user)

    msg = LiveChatMessage(
        session_id=session.id,
        sender_type="STAFF",
        sender_id=staff_user.id,
        sender_name=staff_user.full_name,
        sender_role_title=staff_title,
        content=payload.content.strip(),
        attachment_url=payload.attachment_url,
        attachment_type=payload.attachment_type,
        client_msg_id=payload.client_msg_id,
        created_at=utcnow(),
    )
    session.last_message_at = utcnow()
    session.updated_at = utcnow()
    db.add(msg)
    db.commit()
    db.refresh(msg)

    resp_data = _build_message_response(msg)

    # Realtime broadcast
    await chat_manager.broadcast_to_session(
        session_code=session.session_code,
        message_data={
            "type": "NEW_MESSAGE",
            "session_code": session.session_code,
            "message": resp_data,
        },
        assigned_staff_id=session.assigned_staff_id,
    )

    return resp_data


@router.post("/staff/sessions/{session_code}/close")
async def close_session_by_staff(
    session_code: str,
    staff_user: User = Depends(get_current_staff_user),
    db: Session = Depends(get_db),
):
    """Nhân viên kết thúc phiên trò chuyện sau khi đã tư vấn xong."""
    session = db.scalar(
        select(LiveChatSession).where(LiveChatSession.session_code == session_code)
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên trò chuyện")

    # Kiểm tra quyền: Chỉ nhân viên đang phụ trách hoặc ADMIN mới được đóng phiên
    if session.assigned_staff_id and session.assigned_staff_id != staff_user.id and staff_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền đóng cuộc trò chuyện do nhân viên khác đang phụ trách.",
        )

    session.status = "CLOSED"
    session.closed_at = utcnow()
    session.closed_by_id = staff_user.id
    session.updated_at = utcnow()

    end_msg = LiveChatMessage(
        session_id=session.id,
        sender_type="SYSTEM",
        sender_id=staff_user.id,
        sender_name="H4CARE System",
        sender_role_title="Hệ thống",
        content=f"Nhân viên **{staff_user.full_name}** đã kết thúc phiên tư vấn. Nếu cần hỗ trợ thêm, bạn có thể tạo phiên trò chuyện mới bất kỳ lúc nào.",
        created_at=utcnow(),
    )
    db.add(end_msg)
    db.commit()

    await chat_manager.broadcast_to_session(
        session_code=session.session_code,
        message_data={
            "type": "SESSION_CLOSED",
            "session_code": session.session_code,
            "closed_by": "STAFF",
        },
        assigned_staff_id=session.assigned_staff_id,
    )

    return {"status": "success", "message": "Đã kết thúc cuộc trò chuyện"}


@router.get("/staff/staff-list", response_model=List[StaffInfo])
def get_available_staff_list(
    staff_user: User = Depends(get_current_staff_user),
    db: Session = Depends(get_db),
):
    """Danh sách nhân viên khả dụng để phân công cuộc trò chuyện."""
    staffs = db.scalars(
        select(User).where(
            User.is_active == True,
            User.role.in_([UserRole.ADMIN, UserRole.PHARMACIST, UserRole.WAREHOUSE_MANAGER, UserRole.WAREHOUSE_STAFF]),
        ).order_by(User.full_name.asc())
    ).all()

    return [
        StaffInfo(
            id=s.id,
            full_name=s.full_name,
            email=s.email,
            role=str(s.role),
            role_title=get_role_title(s),
        )
        for s in staffs
    ]


# ===================== UPLOAD FILE AN TOÀN =====================

ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/upload")
async def upload_chat_attachment(
    file: UploadFile = File(...),
    session_code: Optional[str] = Form(None),
    guest_token: Optional[str] = Form(None),
    x_chat_guest_token: Optional[str] = Header(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload hình ảnh đính kèm trong tin nhắn chat.
    Bảo vệ theo phiên nghiêm ngặt (chống upload ẩn danh không thuộc phiên chat nào):
    - Bắt buộc phải có session_code.
    - Xác minh quyền sở hữu phiên TRƯỚC KHI lưu file:
      + Nhân viên có quyền live chat hợp lệ.
      + Khách hàng đã đăng nhập sở hữu phiên.
      + Khách vãng lai có guest_session_token chính xác.
    - Không cho upload vào phiên đã CLOSED.
    - Lưu metadata vào LiveChatAttachment ngay khi upload.
    - Không tạo file rác hay bản ghi database nếu request bị từ chối.
    """
    # 1. Bắt buộc có session_code
    if not session_code or not str(session_code).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp session_code của phiên chat để tải tệp đính kèm.",
        )

    clean_session_code = str(session_code).strip()
    session = db.scalar(
        select(LiveChatSession).where(LiveChatSession.session_code == clean_session_code)
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phiên chat tương ứng.",
        )

    if session.status == "CLOSED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên chat đã kết thúc, không thể tải tệp lên.",
        )

    # 2. Xác minh quyền sở hữu TRƯỚC KHI đọc nội dung tệp
    eff_guest_token = guest_token or x_chat_guest_token
    is_staff = (
        current_user is not None
        and current_user.role in [UserRole.ADMIN, UserRole.PHARMACIST, UserRole.WAREHOUSE_MANAGER, UserRole.WAREHOUSE_STAFF]
    )

    authorized = False
    if is_staff:
        authorized = True
    elif session.customer_id is not None:
        # Phiên của khách có tài khoản: bắt buộc current_user là chính khách hàng sở hữu phiên
        if current_user and current_user.id == session.customer_id:
            authorized = True
    else:
        # Phiên của khách vãng lai: bắt buộc có guest_session_token khớp
        if session.guest_session_token and eff_guest_token:
            if secrets.compare_digest(str(eff_guest_token).strip(), session.guest_session_token.strip()):
                authorized = True

    if not authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền tải tệp lên phiên chat này.",
        )

    # 3. Kiểm tra định dạng và kích thước tệp
    content_type = (file.content_type or "").lower().strip()
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Định dạng tệp không được hỗ trợ. Chỉ chấp nhận ảnh: JPG, PNG, WEBP, GIF.",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp ảnh tải lên có dung lượng rỗng (0 bytes).",
        )
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dung lượng tệp quá lớn. Giới hạn tối đa là 5MB.",
        )

    # 4. Lưu tệp lên đĩa và tạo bản ghi LiveChatAttachment
    ext = ALLOWED_MIME_TYPES[content_type]
    file_uuid = uuid.uuid4().hex
    attachment_code = f"att-live-{file_uuid[:12]}"
    stored_filename = f"{attachment_code}{ext}"
    target_path = CHAT_UPLOAD_DIR / stored_filename

    with open(target_path, "wb") as f:
        f.write(content)

    attachment = LiveChatAttachment(
        attachment_code=attachment_code,
        session_id=session.id,
        user_id=current_user.id if current_user else None,
        original_filename=file.filename or stored_filename,
        stored_filename=stored_filename,
        file_path=str(target_path),
        mime_type=content_type,
        file_size=len(content),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    url = f"/api/v1/live-chat/attachments/{attachment.attachment_code}"
    return {
        "url": url,
        "attachment_code": attachment.attachment_code,
        "content_type": content_type,
        "filename": stored_filename,
        "size": len(content),
    }


@router.get("/attachments/{identifier}")
def serve_chat_attachment(
    identifier: str,
    token: Optional[str] = Query(None),
    x_chat_guest_token: Optional[str] = Header(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Phục vụ file ảnh đính kèm an toàn.
    - Tìm kiếm bản ghi attachment trong database bằng mã hoặc tên tệp chính xác (không dùng LIKE hay tiền tố).
    - Từ chối mọi file không có bản ghi sở hữu (tuyệt đối không fail-open).
    - Xác minh quyền truy cập theo phiên chat:
      + Nhân viên hợp lệ hoặc khách hàng sở hữu phiên (JWT kiểm tra token_version).
      + Khách vãng lai sở hữu phiên (so sánh secrets.compare_digest với guest_session_token).
    - Chặn path traversal.
    """
    # Chống path traversal
    safe_name = os.path.basename(identifier).strip()
    if not safe_name:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mã tệp đính kèm không hợp lệ")

    # Tìm chính xác theo attachment_code hoặc stored_filename
    att = db.scalar(
        select(LiveChatAttachment).where(
            or_(
                LiveChatAttachment.attachment_code == safe_name,
                LiveChatAttachment.stored_filename == safe_name,
            )
        )
    )
    if not att:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bản ghi tệp đính kèm trong hệ thống",
        )

    session = att.session
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phiên chat liên kết với tệp đính kèm",
        )

    file_path = Path(att.file_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tệp ảnh vật lý không tồn tại hoặc đã bị xóa",
        )

    # Xác thực quyền truy cập
    authorized = False
    effective_token = str(token).strip() if token else ""
    effective_guest_token = str(x_chat_guest_token).strip() if x_chat_guest_token else ""

    # 1. Thử xác thực với tài khoản người dùng
    actor = current_user
    if not actor and effective_token:
        actor = authenticate_user_token(effective_token, db)

    if actor:
        # Nhân viên hỗ trợ hợp lệ
        if actor.role in [UserRole.ADMIN, UserRole.PHARMACIST, UserRole.WAREHOUSE_MANAGER, UserRole.WAREHOUSE_STAFF]:
            authorized = True
        # Khách hàng sở hữu phiên
        elif session.customer_id is not None and actor.id == session.customer_id:
            authorized = True
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền truy cập vào tệp đính kèm này",
            )
    else:
        # Khách vãng lai: kiểm tra guest_session_token
        guest_candidate = effective_guest_token or effective_token
        if session.customer_id is None and session.guest_session_token and guest_candidate:
            if secrets.compare_digest(guest_candidate, session.guest_session_token):
                authorized = True

    if not authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập vào tệp đính kèm này",
        )

    return FileResponse(
        str(file_path),
        media_type=att.mime_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
            "Cache-Control": "private, max-age=3600",
        },
    )


# ===================== WEBSOCKET ENDPOINTS =====================

@router.websocket("/ws/client/{session_code}")
async def client_websocket(
    websocket: WebSocket,
    session_code: str,
    token: Optional[str] = Query(None),
    guest_token: Optional[str] = Query(None),
):
    """
    WebSocket kết nối realtime cho khách hàng.
    Bắt buộc xác thực hoàn toàn trước khi gọi accept hoặc đưa vào chat_manager.
    - 4401: thiếu token.
    - 4404: không tìm thấy phiên.
    - 4403: token sai, hết hạn, bị thu hồi, sai chủ phiên hoặc phiên đã đóng.
    """
    effective_token = token or guest_token
    if not effective_token or not str(effective_token).strip():
        await websocket.close(code=4401)
        return

    raw_token = str(effective_token).strip()

    db = SessionLocal()
    try:
        session = db.scalar(
            select(LiveChatSession).where(LiveChatSession.session_code == session_code)
        )
        if not session:
            await websocket.close(code=4404)
            return

        if session.status == "CLOSED":
            await websocket.close(code=4403)
            return

        authenticated = False

        if session.customer_id is not None:
            # Phiên của khách đăng nhập: chỉ được kết nối bằng JWT access token của đúng session.customer_id
            user = authenticate_user_token(raw_token, db)
            if user and user.id == session.customer_id:
                authenticated = True
        else:
            # Phiên khách vãng lai: chỉ được kết nối khi guest_session_token khớp chính xác
            if session.guest_session_token and secrets.compare_digest(raw_token, session.guest_session_token):
                authenticated = True

        if not authenticated:
            await websocket.close(code=4403)
            return
    finally:
        db.close()

    # Đăng ký kết nối an toàn vào connection manager
    await chat_manager.connect_client(session_code, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg_json = json.loads(data)
                if msg_json.get("type") == "PING":
                    await websocket.send_text(json.dumps({"type": "PONG", "timestamp": datetime.now(UTC).isoformat()}))
            except Exception:
                pass
    except WebSocketDisconnect:
        chat_manager.disconnect_client(session_code, websocket)
    except Exception:
        chat_manager.disconnect_client(session_code, websocket)


@router.websocket("/ws/staff")
async def staff_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """WebSocket kết nối realtime cho nhân viên / Admin."""
    if not token or not str(token).strip():
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    db = SessionLocal()
    try:
        user = authenticate_user_token(str(token).strip(), db)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        if user.role not in [UserRole.ADMIN, UserRole.PHARMACIST, UserRole.WAREHOUSE_MANAGER, UserRole.WAREHOUSE_STAFF]:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    finally:
        db.close()

    await chat_manager.connect_staff(user.id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg_json = json.loads(data)
                if msg_json.get("type") == "PING":
                    await websocket.send_text(json.dumps({"type": "PONG", "timestamp": datetime.now(UTC).isoformat()}))
            except Exception:
                pass
    except WebSocketDisconnect:
        chat_manager.disconnect_staff(user.id, websocket)
        await chat_manager.broadcast_staff_status_to_all()
    except Exception:
        chat_manager.disconnect_staff(user.id, websocket)
        await chat_manager.broadcast_staff_status_to_all()



# ===================== INTERNAL BUILDERS =====================

def _build_message_response(msg: LiveChatMessage) -> dict[str, Any]:
    return {
        "id": msg.id,
        "session_id": msg.session_id,
        "sender_type": msg.sender_type,
        "sender_name": msg.sender_name,
        "sender_role_title": msg.sender_role_title,
        "content": msg.content,
        "attachment_url": msg.attachment_url,
        "attachment_type": msg.attachment_type,
        "client_msg_id": msg.client_msg_id,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def _build_session_detail(session: LiveChatSession) -> dict[str, Any]:
    messages_data = [_build_message_response(m) for m in session.messages]
    assigned_staff_title = get_role_title(session.assigned_staff) if session.assigned_staff else None

    return {
        "id": session.id,
        "session_code": session.session_code,
        "customer_name": session.customer_name,
        "customer_email": session.customer_email,
        "customer_phone": session.customer_phone,
        "customer_id": session.customer_id,
        "guest_session_token": session.guest_session_token,
        "assigned_staff_id": session.assigned_staff_id,
        "assigned_staff_name": session.assigned_staff.full_name if session.assigned_staff else None,
        "assigned_staff_title": assigned_staff_title,
        "status": session.status,
        "subject": session.subject,
        "initial_context": session.initial_context,
        "rating": session.rating,
        "feedback": session.feedback,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "closed_at": session.closed_at.isoformat() if session.closed_at else None,
        "last_message_at": session.last_message_at.isoformat() if session.last_message_at else None,
        "messages": messages_data,
    }
