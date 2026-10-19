"""
apps/api/app/services/refund_calculation_service.py

Dịch vụ tính toán số tiền hoàn trả (Refund Calculation) cho H4CARE:
- Phân bổ chiết khấu theo tỷ lệ (Proportionate Discount Allocation) cho từng sản phẩm.
- Tính giá thực trả ròng (Net Price Per Unit) sau khuyến mãi / voucher.
- Tính toán hoàn phí vận chuyển khi đủ điều kiện (lỗi từ nhà thuốc).
- Đảm bảo bất biến tài chính: Tổng tiền hoàn <= Tổng tiền khách đã thanh toán cho đơn hàng.
- Ngăn chặn hoàn tiền vượt mức (Over-refund Blocking).
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import Order, OrderItem
from app.models.returns import Refund, RefundStatus, ReturnItem, ReturnRequest
from app.services.return_policy_service import ReturnPolicyService


class RefundCalculationService:
    """
    Service tính toán và xác thực số tiền hoàn.
    """

    @classmethod
    def calculate_net_unit_price(
        cls,
        order: Order | None = None,
        item: OrderItem | None = None,
        *,
        listed_unit_price: Decimal | None = None,
        total_paid_goods_amount: Decimal | None = None,
        total_listed_goods_amount: Decimal | None = None,
    ) -> Decimal:
        """
        Tính đơn giá ròng thực trả (Net Unit Price) của 1 sản phẩm trong đơn,
        sau khi đã phân bổ đều chiết khấu / giảm giá đơn hàng theo tỷ lệ giá trị.
        """
        if listed_unit_price is not None:
            if not total_listed_goods_amount or total_listed_goods_amount <= Decimal("0"):
                return listed_unit_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            paid = total_paid_goods_amount or Decimal("0")
            ratio = min(Decimal("1.0"), paid / total_listed_goods_amount)
            return (listed_unit_price * ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if not order or not item or item.quantity <= 0:
            return Decimal("0.0")

        # Tổng giá trị niêm yết của tất cả sản phẩm trong đơn
        total_items_subtotal = sum(Decimal(str(it.subtotal)) for it in order.items)
        if total_items_subtotal <= Decimal("0.0"):
            return Decimal(str(item.price))

        # Tiền hàng thực tế khách trả = Tổng thanh toán - Phí ship (nếu có)
        total_items_paid = Decimal(str(order.total_amount)) - Decimal(str(order.shipping_fee or 0))
        if total_items_paid < Decimal("0.0"):
            total_items_paid = Decimal("0.0")

        # Tỷ lệ thực trả / niêm yết
        paid_ratio = min(Decimal("1.0"), total_items_paid / total_items_subtotal)

        # Đơn giá ròng mỗi đơn vị
        nominal_unit_price = Decimal(str(item.price))
        net_unit_price = (nominal_unit_price * paid_ratio).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return net_unit_price

    @classmethod
    def get_already_refunded_amount(cls, db: Session, order_id: int) -> Decimal:
        """
        Lấy tổng số tiền đã hoàn thành công hoặc đang chờ xử lý cho đơn hàng này.
        """
        active_statuses = [
            RefundStatus.SUCCEEDED.value,
            RefundStatus.APPROVED.value,
            RefundStatus.PROCESSING.value,
            RefundStatus.PENDING.value,
        ]
        sum_refunded = db.scalar(
            select(func.sum(Refund.amount)).where(
                Refund.order_id == order_id,
                Refund.status.in_(active_statuses),
            )
        )
        return Decimal(str(sum_refunded)) if sum_refunded is not None else Decimal("0.0")

    @classmethod
    def calculate_return_refund(
        cls,
        db: Session,
        order: Order,
        return_items: Sequence[ReturnItem],
        reason_code: str,
        include_shipping_fee: bool | None = None,
    ) -> dict[str, Decimal]:
        """
        Tính toán chi tiết số tiền hoàn trả cho yêu cầu đổi/trả:
        - items_refund_amount: Tiền hoàn cho danh sách sản phẩm trả lại.
        - shipping_fee_refund: Tiền hoàn phí vận chuyển (nếu đủ điều kiện hoặc được chỉ định).
        - total_refund_amount: items_refund_amount + shipping_fee_refund (giới hạn bởi trần tối đa).
        - max_possible_refund: Số tiền tối đa còn có thể hoàn cho đơn này.
        """
        items_total = Decimal("0.0")
        for ret_item in return_items:
            # Tìm OrderItem tương ứng
            order_item = next((it for it in order.items if it.id == ret_item.order_item_id), None)
            if not order_item:
                continue

            net_unit_price = cls.calculate_net_unit_price(order, order_item)
            qty = Decimal(str(ret_item.accepted_quantity or 0))
            line_refund = net_unit_price * qty
            items_total += line_refund

        # Xác định hoàn phí vận chuyển
        order_shipping_fee = Decimal(str(order.shipping_fee or 0))
        refund_shipping = Decimal("0.0")

        if include_shipping_fee is True:
            refund_shipping = order_shipping_fee
        elif include_shipping_fee is False:
            refund_shipping = Decimal("0.0")
        else:
            # Tự động thẩm định theo chính sách
            # Kiểm tra xem có phải hoàn toàn bộ sản phẩm còn lại không
            is_full_return = len(return_items) == len(order.items) and all(
                ret_item.requested_quantity >= next((it.quantity for it in order.items if it.id == ret_item.order_item_id), 0)
                for ret_item in return_items
            )
            if ReturnPolicyService.is_shipping_fee_refundable(order, reason_code, is_full_return):
                refund_shipping = order_shipping_fee

        # Đảm bảo giới hạn trần hoàn tiền
        already_refunded = cls.get_already_refunded_amount(db, order.id)
        order_total = Decimal(str(order.total_amount))
        max_possible_refund = max(Decimal("0.0"), order_total - already_refunded)

        desired_total = items_total + refund_shipping
        final_refund = min(desired_total, max_possible_refund)

        return {
            "items_refund_amount": items_total,
            "shipping_fee_refund": refund_shipping,
            "desired_refund_amount": desired_total,
            "max_possible_refund": max_possible_refund,
            "already_refunded": already_refunded,
            "final_refund_amount": final_refund,
        }

    @classmethod
    def validate_refund_amount(
        cls,
        db: Session,
        order: Order,
        proposed_amount: Decimal,
        exclude_refund_id: int | None = None,
    ) -> tuple[bool, str | None]:
        """
        Xác thực tính hợp lệ của số tiền hoàn đề xuất:
        - Phải > 0.
        - Không được vượt quá số tiền còn lại có thể hoàn của đơn hàng.
        """
        if proposed_amount <= Decimal("0.0"):
            return False, "Số tiền hoàn phải lớn hơn 0 đồng."

        active_statuses = [
            RefundStatus.SUCCEEDED.value,
            RefundStatus.APPROVED.value,
            RefundStatus.PROCESSING.value,
            RefundStatus.PENDING.value,
        ]
        query = select(func.sum(Refund.amount)).where(
            Refund.order_id == order.id,
            Refund.status.in_(active_statuses),
        )
        if exclude_refund_id:
            query = query.where(Refund.id != exclude_refund_id)

        sum_prior = db.scalar(query)
        prior_amount = Decimal(str(sum_prior)) if sum_prior is not None else Decimal("0.0")

        order_total = Decimal(str(order.total_amount))
        available_cap = max(Decimal("0.0"), order_total - prior_amount)

        if proposed_amount > available_cap:
            return (
                False,
                f"Số tiền hoàn ({int(proposed_amount):,} đ) vượt quá hạn mức tối đa còn lại của đơn hàng ({int(available_cap):,} đ). "
                f"Đơn hàng: {int(order_total):,} đ, Đã hoàn/chờ duyệt: {int(prior_amount):,} đ.",
            )

        return True, None
