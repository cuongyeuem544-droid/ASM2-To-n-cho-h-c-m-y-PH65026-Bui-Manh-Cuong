"""Shared admin action availability and order transition validation.

These are the existing order rules, exposed to the UI without granting new roles
or skipping fulfillment requirements. The mutation always checks fresh DB data.
"""

from collections.abc import Mapping, Sequence
from typing import Any


ORDER_TRANSITIONS = {
    "PENDING": {"CONFIRMED", "PROCESSING", "CANCELLED"},
    "CONFIRMED": {"PROCESSING", "SHIPPING", "CANCELLED"},
    "PROCESSING": {"SHIPPING", "CANCELLED"},
    "SHIPPING": {"COMPLETED", "CANCELLED"},
}

ORDER_ACTION_LABELS = {
    "CONFIRMED": "Xác nhận đơn",
    "SHIPPING": "Đang giao hàng",
    "COMPLETED": "Hoàn thành",
    "CANCELLED": "Hủy đơn",
}


def order_transition_error(
    current_status: str,
    target_status: str,
    fulfillments: Sequence[Mapping[str, Any]],
) -> str | None:
    if current_status in {"COMPLETED", "CANCELLED"}:
        return f"Không thể thay đổi trạng thái của đơn hàng đã ở trạng thái kết thúc '{current_status}'."
    if target_status not in ORDER_TRANSITIONS.get(current_status, set()):
        return (
            f"Không thể chuyển đổi trực tiếp trạng thái đơn hàng từ '{current_status}' sang '{target_status}'. "
            "Luồng xử lý đơn hàng không hợp lệ."
        )
    if target_status == "COMPLETED":
        non_delivered = [f for f in fulfillments if f["status"] != "DELIVERED"]
        if non_delivered:
            states = [f"{f['fulfillment_code']}: {f['status']}" for f in non_delivered]
            return (
                "Không thể hoàn tất đơn hàng khi vẫn còn kiện hàng chưa giao thành công (DELIVERED). "
                f"Trạng thái hiện tại: {states}"
            )
    elif target_status == "SHIPPING":
        if fulfillments and not any(f["status"] in {"SHIPPED", "DELIVERED"} for f in fulfillments):
            return (
                "Không thể chuyển đơn sang SHIPPING khi chưa có kiện hàng nào được xuất kho (SHIPPED). "
                "Vui lòng cập nhật trạng thái kiện hàng trước."
            )
    elif target_status == "CANCELLED":
        already_shipped = [f for f in fulfillments if f["status"] in {"SHIPPED", "DELIVERED"}]
        if already_shipped:
            return (
                f"Không thể hủy đơn hàng đã xuất kho hoặc đã giao hàng ({len(already_shipped)} kiện). "
                "Vui lòng sử dụng quy trình Đổi / Trả hàng."
            )
    return None


def get_order_status_actions(
    current_status: str, fulfillments: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    current_status = (current_status or "").upper().strip()
    actions = []
    for target, label in ORDER_ACTION_LABELS.items():
        reason = (
            f"Đơn hàng đã ở trạng thái {current_status}."
            if current_status == target
            else order_transition_error(current_status, target, fulfillments)
        )
        actions.append({"target_status": target, "label": label, "allowed": reason is None, "reason": reason})
    return actions
