from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import logging
from typing import Any, Optional
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    BatchStatus,
    CanonicalProduct,
    FulfillmentItem,
    InventoryBatch,
    Order,
    OrderFulfillment,
    OrderItem,
    OrderItemBatchAllocation,
    PaymentTransaction,
    PriceObservation,
    ProductSku,
    Refund,
    StockMovement,
    StockReservation,
    User,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import UserRole

logger = logging.getLogger("pharmatrust.fulfillment")


def utcnow() -> datetime:
    return datetime.now(UTC)


class FulfillmentRoutingService:
    """
    Dịch vụ Điều phối Đa Kho & Thuật toán Phân bổ Lô FEFO (First-Expired First-Out).
    """

    NORTH_PROVINCES = {
        "hà nội", "ha noi", "hải phòng", "hai phong", "quảng ninh", "quang ninh",
        "bắc ninh", "bac ninh", "hải dương", "hai duong", "hưng yên", "hung yen",
        "hà nam", "ha nam", "nam định", "nam dinh", "thái bình", "thai binh",
        "ninh bình", "ninh binh", "vĩnh phúc", "vinh phuc", "phú thọ", "phu tho",
        "thái nguyên", "thai nguyen", "bắc giang", "bac giang", "lạng sơn", "lang son",
        "tuyên quang", "tuyen quang", "hà giang", "ha giang", "cao bằng", "cao bang",
        "bắc kạn", "bac kan", "lào cai", "lao cai", "yên bái", "yen bai",
        "sơn la", "son la", "hòa bình", "hoa binh", "điện biên", "dien bien", "lai châu", "lai chau",
    }

    @classmethod
    def get_preferred_warehouse_order(
        cls,
        db: Session,
        shipping_city: Optional[str],
        shipping_address: Optional[str],
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        province_code: Optional[str] = None,
        district_code: Optional[str] = None,
    ) -> list[Warehouse]:
        """
        Xác định thứ tự ưu tiên kho dựa trên khoảng cách địa lý đến khách hàng:
        1. Luôn chỉ chọn từ danh sách các kho ĐÃ TẠO và đang hoạt động (Warehouse.is_active == True).
        2. Nếu một khu vực/tỉnh thành gần kho chưa được tạo, tự động điều phối về kho ĐÃ TẠO gần nhất.
        3. Tuyệt đối không bao giờ chuyển đơn về kho chưa được tạo.
        """
        all_warehouses = db.scalars(
            select(Warehouse).where(Warehouse.is_active == True).order_by(Warehouse.id.asc())
        ).all()
        if not all_warehouses:
            raise HTTPException(status_code=500, detail="Hệ thống chưa thiết lập kho hàng nào đang hoạt động.")

        from app.services.geo_service import GeoService, calculate_haversine_distance

        # Xác định tọa độ khách hàng (từ GPS, hoặc mã tỉnh/huyện, hoặc nhận diện từ địa chỉ giao hàng)
        combined_addr = f"{shipping_city or ''} {shipping_address or ''}".strip()
        cust_lat, cust_lng, _ = GeoService.resolve_customer_coordinates(
            lat=lat,
            lng=lng,
            province_code=province_code,
            district_code=district_code,
            address_text=combined_addr,
        )

        def get_distance_to_wh(w: Warehouse) -> float:
            if w.lat is not None and w.lng is not None:
                w_lat, w_lng = float(w.lat), float(w.lng)
            else:
                w_addr = f"{w.province or ''} {w.district or ''} {w.address or ''} {w.name or ''}"
                w_lat, w_lng, _ = GeoService.resolve_customer_coordinates(
                    address_text=w_addr
                )
            return calculate_haversine_distance(cust_lat, cust_lng, w_lat, w_lng)

        return sorted(all_warehouses, key=get_distance_to_wh)

    @classmethod
    def get_or_create_default_sku(cls, db: Session, product_id: int) -> ProductSku:
        """
        Lấy SKU mặc định của sản phẩm hoặc tạo mới nếu chưa có.
        """
        sku = db.scalar(
            select(ProductSku).where(
                ProductSku.canonical_product_id == product_id,
                ProductSku.is_default == True,
            )
        )
        if not sku:
            sku = db.scalar(select(ProductSku).where(ProductSku.canonical_product_id == product_id))

        if not sku:
            prod = db.get(CanonicalProduct, product_id)
            price_row = db.query(PriceObservation.observed_price).filter(PriceObservation.product_id == product_id).first()
            base_p = Decimal(str(price_row[0])) if (price_row and price_row[0]) else Decimal("0.0")

            clean_code = str(prod.registration_number).strip().replace(" ", "-") if (prod and prod.registration_number) else f"{product_id:04d}"
            sku = ProductSku(
                canonical_product_id=product_id,
                sku_code=f"SKU-{clean_code}-BOX",
                barcode=None,  # Không tự sinh barcode giả 893... khi không có dữ liệu đối chiếu
                uom=(prod.dosage_form if prod else None) or "Hộp",
                conversion_rate=1,
                base_price=base_p,
                is_default=True,
                is_active=True,
            )
            db.add(sku)
            db.flush()

        return sku

    @classmethod
    def route_and_allocate_order(
        cls,
        db: Session,
        order: Order,
        items: list[OrderItem],
        shipping_city: Optional[str],
        shipping_address: Optional[str],
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        province_code: Optional[str] = None,
        district_code: Optional[str] = None,
    ) -> list[OrderFulfillment]:
        """
        Thực hiện định tuyến kho thông minh & phân bổ lô FEFO cho đơn hàng:
        - Kịch bản 1: Có 1 kho duy nhất đủ 100% hàng -> 1 kiện duy nhất từ kho đó.
        - Kịch bản 2: Không kho nào đơn lẻ đủ hàng -> Tách đơn (Split Order) giữa các kho.
        - Kịch bản 3: Toàn hệ thống không đủ hàng -> Trả về lỗi 400 kèm số lượng thiếu chi tiết.
        """
        ordered_warehouses = cls.get_preferred_warehouse_order(
            db=db,
            shipping_city=shipping_city,
            shipping_address=shipping_address,
            lat=lat if lat is not None else order.lat,
            lng=lng if lng is not None else order.lng,
            province_code=province_code if province_code is not None else getattr(order, "province_code", None),
            district_code=district_code if district_code is not None else getattr(order, "district_code", None),
        )
        today = date.today()
        # Quyết định Q7: Ngưỡng hạn sử dụng tối thiểu 180 ngày (6 tháng) cho đơn giao khách
        fefo_cutoff_date = today + timedelta(days=180)

        # 1. Map mỗi order item sang SKU chính xác (hỗ trợ multi-SKU người dùng chọn)
        item_sku_map: dict[int, ProductSku] = {}
        for it in items:
            sku_obj: Optional[ProductSku] = None
            if it.product_sku:
                raw_sku_code = it.product_sku.split(" ")[0].strip()
                if raw_sku_code.startswith("SKU-"):
                    sku_obj = db.scalar(select(ProductSku).where(ProductSku.sku_code == raw_sku_code))
                if not sku_obj and it.product_sku.startswith("SKU-"):
                    sku_obj = db.scalar(select(ProductSku).where(ProductSku.sku_code == it.product_sku.strip()))
            if not sku_obj and it.product_id:
                sku_obj = cls.get_or_create_default_sku(db, it.product_id)
            if not sku_obj:
                raise HTTPException(status_code=400, detail=f"Không tìm thấy quy cách đóng gói (SKU) hợp lệ cho '{it.product_name}'.")
            item_sku_map[it.id] = sku_obj

        # 2. Kiểm tra tồn khả dụng của từng sản phẩm tại từng kho (chỉ xét lô ACTIVE và còn hạn >= 180 ngày)
        # warehouse_id -> sku_id -> available_qty
        wh_sku_avail: dict[int, dict[int, int]] = {w.id: {} for w in ordered_warehouses}

        for w in ordered_warehouses:
            for it in items:
                sku = item_sku_map[it.id]
                avail = db.query(func.coalesce(func.sum(WarehouseBatchStock.quantity_available), 0)).join(
                    InventoryBatch, InventoryBatch.id == WarehouseBatchStock.batch_id
                ).filter(
                    WarehouseBatchStock.warehouse_id == w.id,
                    WarehouseBatchStock.quantity_available > 0,
                    InventoryBatch.sku_id == sku.id,
                    InventoryBatch.status == BatchStatus.ACTIVE,
                    InventoryBatch.expiry_date >= fefo_cutoff_date,
                ).scalar() or 0
                wh_sku_avail[w.id][sku.id] = int(avail)

        # 3. KỊCH BẢN 1: Kiểm tra xem có 1 kho đơn lẻ nào đáp ứng đủ 100% tất cả items không
        single_fulfill_wh: Optional[Warehouse] = None
        for w in ordered_warehouses:
            can_fulfill_all = True
            for it in items:
                sku = item_sku_map[it.id]
                if wh_sku_avail[w.id].get(sku.id, 0) < it.quantity:
                    can_fulfill_all = False
                    break
            if can_fulfill_all:
                single_fulfill_wh = w
                break

        fulfillments_to_return: list[OrderFulfillment] = []

        if single_fulfill_wh:
            # Phân bổ toàn bộ đơn hàng cho single_fulfill_wh
            logger.info(f"[ROUTING] Đơn {order.order_code}: Đáp ứng 100% tại kho {single_fulfill_wh.code}")
            order.assigned_warehouse_id = single_fulfill_wh.id
            order.assignment_method = "NEAREST_SINGLE"
            o_lat = getattr(order, "lat", None)
            o_lng = getattr(order, "lng", None)
            if o_lat is not None and o_lng is not None and single_fulfill_wh.lat is not None and single_fulfill_wh.lng is not None:
                from app.services.geo_service import calculate_haversine_distance
                order.assignment_distance_km = round(
                    calculate_haversine_distance(o_lat, o_lng, single_fulfill_wh.lat, single_fulfill_wh.lng), 2
                )

            ff = cls._create_fulfillment(
                db=db,
                order=order,
                warehouse=single_fulfill_wh,
                items=items,
                item_sku_map=item_sku_map,
                qty_breakdown={it.id: it.quantity for it in items},
                today=today,
                carrier_name="Giao Hàng Tiết Kiệm (GHTK)",
                shipping_fee=order.shipping_fee,
            )
            fulfillments_to_return.append(ff)

        else:
            # 4. KỊCH BẢN 2 hoặc 3: Kiểm tra tổng tồn toàn hệ thống
            system_shortages = []
            for it in items:
                sku = item_sku_map[it.id]
                total_system_avail = sum(wh_sku_avail[w.id].get(sku.id, 0) for w in ordered_warehouses)
                if total_system_avail < it.quantity:
                    system_shortages.append(
                        f"'{it.product_name}': yêu cầu {it.quantity}, toàn hệ thống chỉ còn khả dụng {total_system_avail}"
                    )

            if system_shortages:
                # Kịch bản 3: Không đủ hàng trong toàn hệ thống (đáp ứng điều kiện HSD >= 180 ngày)
                err_detail = "Số lượng tồn kho không đủ (đáp ứng hạn sử dụng an toàn >= 180 ngày): " + "; ".join(system_shortages)
                raise HTTPException(status_code=400, detail=err_detail)

            # Kịch bản 2: Điều phối điều chuyển gom hàng (Consolidation Transfer)
            consolidation_hub = ordered_warehouses[0]
            logger.info(f"[ROUTING] Đơn {order.order_code}: Điều chuyển gom hàng về kho đích {consolidation_hub.code}.")
            order.assigned_warehouse_id = consolidation_hub.id
            order.assignment_method = "CONSOLIDATED_TRANSFER"
            order.fulfillment_status = "WAITING_INTERNAL_TRANSFER"
            order.assigned_at = utcnow()
            o_lat = getattr(order, "lat", None)
            o_lng = getattr(order, "lng", None)
            if o_lat is not None and o_lng is not None and consolidation_hub.lat is not None and consolidation_hub.lng is not None:
                from app.services.geo_service import calculate_haversine_distance
                order.assignment_distance_km = round(
                    calculate_haversine_distance(o_lat, o_lng, consolidation_hub.lat, consolidation_hub.lng), 2
                )

            wh_item_alloc: dict[int, dict[int, int]] = {w.id: {} for w in ordered_warehouses}

            for it in items:
                sku = item_sku_map[it.id]
                remaining_needed = it.quantity

                for w in ordered_warehouses:
                    avail_here = wh_sku_avail[w.id].get(sku.id, 0)
                    if avail_here > 0 and remaining_needed > 0:
                        take = min(remaining_needed, avail_here)
                        wh_item_alloc[w.id][it.id] = take
                        remaining_needed -= take
                        wh_sku_avail[w.id][sku.id] -= take

            # Tạo lệnh chuyển kho StockTransfer từ các kho nguồn về kho đích (Consolidation Hub)
            from app.models.inventory import StockTransfer, StockTransferItem
            for w in ordered_warehouses:
                if w.id == consolidation_hub.id:
                    continue
                allocs = wh_item_alloc[w.id]
                items_to_transfer = [it for it in items if allocs.get(it.id, 0) > 0]
                if items_to_transfer:
                    transfer = StockTransfer(
                        transfer_code=f"TRF-{order.order_code}-{w.code[:6]}-{consolidation_hub.code[:6]}",
                        from_warehouse_id=w.id,
                        to_warehouse_id=consolidation_hub.id,
                        status="IN_TRANSIT",
                        note=f"Điều chuyển hàng phục vụ đơn hàng {order.order_code}",
                        shipped_at=utcnow(),
                    )
                    db.add(transfer)
                    db.flush()

            # Tạo kiện hàng fulfillment cho từng kho
            for w in ordered_warehouses:
                allocs = wh_item_alloc[w.id]
                if any(qty > 0 for qty in allocs.values()):
                    carrier = "GHTK Fast" if "HCM" in w.code else "ViettelPost Express"
                    ff = cls._create_fulfillment(
                        db=db,
                        order=order,
                        warehouse=w,
                        items=items,
                        item_sku_map=item_sku_map,
                        qty_breakdown=allocs,
                        today=today,
                        carrier_name=carrier,
                        shipping_fee=Decimal("0.0"),
                    )
                    fulfillments_to_return.append(ff)

        warehouses_to_notify = set()
        if order.assigned_warehouse_id:
            warehouses_to_notify.add(order.assigned_warehouse_id)
        for ff in fulfillments_to_return:
            if ff.warehouse_id:
                warehouses_to_notify.add(ff.warehouse_id)

        for wid in warehouses_to_notify:
            try:
                from app.services.warehouse_notification_service import WarehouseNotificationService
                WarehouseNotificationService.notify_order_new(db, order, wid)
            except Exception as e:
                logger.warning(f"Failed to create ORDER_NEW notification for warehouse {wid}: {e}")

        db.flush()
        return fulfillments_to_return

    @classmethod
    def _create_fulfillment(
        cls,
        db: Session,
        order: Order,
        warehouse: Warehouse,
        items: list[OrderItem],
        item_sku_map: dict[int, ProductSku],
        qty_breakdown: dict[int, int],
        today: date,
        carrier_name: str,
        shipping_fee: Decimal,
    ) -> OrderFulfillment:
        """
        Tạo OrderFulfillment và phân bổ các lô thuốc theo nguyên tắc FEFO.
        """
        ff_code = f"FF-{order.order_code}-{warehouse.code}"
        fulfillment = OrderFulfillment(
            fulfillment_code=ff_code,
            order_id=order.id,
            warehouse_id=warehouse.id,
            status="PENDING",
            carrier_name=carrier_name,
            tracking_code=f"TRK{warehouse.id}{order.id}{int(datetime.now().timestamp()) % 10000}",
            shipping_fee=shipping_fee,
        )
        db.add(fulfillment)
        db.flush()

        for it in items:
            allocated_qty_for_this_wh = qty_breakdown.get(it.id, 0)
            if allocated_qty_for_this_wh <= 0:
                continue

            ff_item = FulfillmentItem(
                fulfillment_id=fulfillment.id,
                order_item_id=it.id,
                quantity=allocated_qty_for_this_wh,
            )
            db.add(ff_item)
            db.flush()

            # Phân bổ lô FEFO cho dòng sản phẩm này tại kho này
            sku = item_sku_map[it.id]
            cls._allocate_fefo_batches(
                db=db,
                order=order,
                fulfillment=fulfillment,
                fulfillment_item=ff_item,
                order_item=it,
                sku=sku,
                warehouse=warehouse,
                required_qty=allocated_qty_for_this_wh,
                today=today,
            )

        return fulfillment

    @classmethod
    def _allocate_fefo_batches(
        cls,
        db: Session,
        order: Order,
        fulfillment: OrderFulfillment,
        fulfillment_item: FulfillmentItem,
        order_item: OrderItem,
        sku: ProductSku,
        warehouse: Warehouse,
        required_qty: int,
        today: date,
    ):
        """
        Thuật toán phân bổ lô FEFO:
        Lấy các lô còn hạn dùng, ACTIVE, sắp xếp tăng dần theo expiry_date ASC (hạn gần nhất xuất trước).
        Khấu trừ available, tăng reserved, tạo StockReservation và OrderItemBatchAllocation.
        """
        fefo_cutoff_date = today + timedelta(days=180)
        batch_stocks = (
            db.query(WarehouseBatchStock, InventoryBatch)
            .join(InventoryBatch, InventoryBatch.id == WarehouseBatchStock.batch_id)
            .filter(
                WarehouseBatchStock.warehouse_id == warehouse.id,
                InventoryBatch.sku_id == sku.id,
                InventoryBatch.status == BatchStatus.ACTIVE,
                InventoryBatch.expiry_date >= fefo_cutoff_date,
                WarehouseBatchStock.quantity_available > 0,
            )
            .order_by(InventoryBatch.expiry_date.asc(), InventoryBatch.id.asc())
            .all()
        )

        remaining = required_qty
        for stock_row, batch in batch_stocks:
            if remaining <= 0:
                break

            take = min(remaining, stock_row.quantity_available)
            stock_row.quantity_available -= take
            stock_row.quantity_reserved += take

            # Tạo bản ghi phân bổ lô
            db.add(
                OrderItemBatchAllocation(
                    fulfillment_item_id=fulfillment_item.id,
                    order_item_id=order_item.id,
                    batch_id=batch.id,
                    warehouse_id=warehouse.id,
                    allocated_quantity=take,
                )
            )

            # Tạo bản ghi giữ chỗ (Reservation)
            db.add(
                StockReservation(
                    order_id=order.id,
                    batch_id=batch.id,
                    warehouse_id=warehouse.id,
                    quantity=take,
                    status="RESERVED",
                    expires_at=datetime.now(UTC) + timedelta(hours=24),
                )
            )

            remaining -= take
            logger.info(
                f"[FEFO] Đơn {order.order_code}: Cấp {take} {sku.uom} từ lô {batch.batch_number} "
                f"(HSD: {batch.expiry_date}) tại kho {warehouse.code}"
            )

        if remaining > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Không đủ tồn kho hợp lệ theo FEFO tại {warehouse.name} cho sản phẩm '{order_item.product_name}'. Thiếu {remaining} đơn vị.",
            )

    @classmethod
    def transition_fulfillment_status(
        cls,
        db: Session,
        fulfillment_id: int,
        new_status: str,
        user_id: Optional[int] = None,
    ) -> OrderFulfillment:
        """
        Chuyển trạng thái kiện hàng (PICKED -> PACKED -> SHIPPED -> DELIVERED).
        Đặc biệt khi chuyển sang SHIPPED:
        - Giảm quantity_on_hand và quantity_reserved tại kho.
        - Hoàn thành StockReservation -> FULFILLED.
        - Sinh bản ghi Thẻ kho (StockMovement - DISPATCH).
        - Đồng bộ trạng thái đơn hàng cha (Order).
        """
        ff = db.scalar(
            select(OrderFulfillment)
            .options(
                selectinload(OrderFulfillment.warehouse),
                selectinload(OrderFulfillment.items).selectinload(FulfillmentItem.order_item),
            )
            .where(OrderFulfillment.id == fulfillment_id)
        )
        if not ff:
            raise HTTPException(status_code=404, detail="Không tìm thấy kiện hàng")

        # Kiểm tra quyền sở hữu kho nếu user_id được cung cấp (chống can thiệp chéo kho)
        if user_id:
            user = db.get(User, user_id)
            if user and user.role != UserRole.ADMIN and user.warehouse_id != ff.warehouse_id:
                raise HTTPException(
                    status_code=403,
                    detail=f"Kiện hàng {ff.fulfillment_code} thuộc kho #{ff.warehouse_id}. Bạn không có quyền thao tác trên kho này.",
                )

        old_status = ff.status

        # Chuẩn hóa tên trạng thái (hỗ trợ PICKING và PICKED tương đương)
        target_status = new_status.upper()
        if target_status == "PICKING":
            target_status = "PICKED"

        curr_status = old_status.upper()
        if curr_status in ["PENDING", "ALLOCATED", "WAITING_INTERNAL_TRANSFER", "CONSOLIDATED"]:
            curr_status = "PENDING"
        elif curr_status == "PICKING":
            curr_status = "PICKED"

        # Nếu đã ở trạng thái mục tiêu (gọi lặp lại / idempotent), trả về ngay mà không làm gì
        if target_status == curr_status:
            return ff

        # State machine nghiêm ngặt, bắt buộc tuần tự:
        # PENDING -> PICKED -> PACKED -> SHIPPED -> DELIVERED
        # CANCELLED chỉ cho phép từ các trạng thái chưa kết thúc
        strict_transitions: dict[str, set[str]] = {
            "PENDING": {"PICKED", "CANCELLED"},
            "PICKED": {"PACKED", "CANCELLED"},
            "PACKED": {"SHIPPED", "CANCELLED"},
            "SHIPPED": {"DELIVERED", "CANCELLED"},
            "DELIVERED": set(),
            "CANCELLED": set(),
        }

        allowed = strict_transitions.get(curr_status)
        if allowed is None or target_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Không thể chuyển trạng thái kiện hàng từ '{old_status}' sang '{new_status}'. Quy trình bắt buộc tuần tự: Lấy hàng (PICKED) -> Đóng gói (PACKED) -> Xuất kho (SHIPPED) -> Giao hàng (DELIVERED).",
            )

        now = utcnow()

        # QUAN TRỌNG: Không gán ff.status = target_status trước khi kiểm định thành công
        if target_status == "SHIPPED":
            # 1. Tiền kiểm định kiện hàng phải có sản phẩm
            if not ff.items:
                raise HTTPException(
                    status_code=400,
                    detail=f"Kiện hàng {ff.fulfillment_code} không có bất kỳ sản phẩm nào để xuất kho.",
                )

            # 2. Tiền kiểm định 100% FulfillmentItem phải có phân bổ lô hợp lệ và đúng số lượng
            all_allocations: list[OrderItemBatchAllocation] = []
            for item in ff.items:
                item_allocs = db.scalars(
                    select(OrderItemBatchAllocation).where(
                        OrderItemBatchAllocation.fulfillment_item_id == item.id,
                        OrderItemBatchAllocation.warehouse_id == ff.warehouse_id,
                    )
                ).all()

                if not item_allocs and item.order_item_id:
                    item_allocs = db.scalars(
                        select(OrderItemBatchAllocation).where(
                            OrderItemBatchAllocation.order_item_id == item.order_item_id,
                            OrderItemBatchAllocation.warehouse_id == ff.warehouse_id,
                        )
                    ).all()

                total_allocated = sum(a.allocated_quantity for a in item_allocs) if item_allocs else 0
                if not item_allocs or total_allocated != item.quantity:
                    prod_name = item.order_item.product_name if item.order_item else f"ID {item.id}"
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Sản phẩm '{prod_name}' trong kiện hàng {ff.fulfillment_code} "
                            f"chưa được phân bổ đủ lô xuất kho (yêu cầu {item.quantity}, phân bổ {total_allocated}). "
                            "Không thể thực hiện xuất kho."
                        ),
                    )

                for alloc in item_allocs:
                    if alloc.warehouse_id != ff.warehouse_id:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Lô xuất #{alloc.batch_id} thuộc kho #{alloc.warehouse_id}, không khớp với kho xuất của kiện hàng #{ff.warehouse_id}.",
                        )

                all_allocations.extend(item_allocs)

            # Khử trùng lặp allocations nếu có
            unique_allocs = list({a.id: a for a in all_allocations}.values())

            # 3. Tiền kiểm định theo từng lô (Batch): tồn tại, đúng kho, đủ on_hand, đủ reserved, và có StockReservation hợp lệ
            batch_demand: dict[int, int] = {}
            for alloc in unique_allocs:
                batch_demand[alloc.batch_id] = batch_demand.get(alloc.batch_id, 0) + alloc.allocated_quantity

            batch_plans = []
            for batch_id, req_qty in batch_demand.items():
                batch = db.scalar(select(InventoryBatch).where(InventoryBatch.id == batch_id))
                if not batch:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Lô xuất #{batch_id} không tồn tại trong hệ thống.",
                    )

                stock = db.scalar(
                    select(WarehouseBatchStock).where(
                        WarehouseBatchStock.warehouse_id == ff.warehouse_id,
                        WarehouseBatchStock.batch_id == batch_id,
                    )
                )
                if not stock:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Không tìm thấy dữ liệu tồn kho cho lô #{batch_id} tại kho #{ff.warehouse_id}.",
                    )

                if stock.quantity_on_hand < req_qty:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Tồn kho thực tế của lô #{batch_id} ({stock.quantity_on_hand}) không đủ để xuất ({req_qty}).",
                    )

                if stock.quantity_reserved < req_qty:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Số lượng tồn kho giữ chỗ của lô #{batch_id} ({stock.quantity_reserved}) không đủ ({req_qty}) để xuất kho.",
                    )

                reservations = db.scalars(
                    select(StockReservation).where(
                        StockReservation.order_id == ff.order_id,
                        StockReservation.batch_id == batch_id,
                        StockReservation.warehouse_id == ff.warehouse_id,
                        StockReservation.status == "RESERVED",
                    )
                ).all()

                total_res_qty = sum(r.quantity for r in reservations)
                if total_res_qty < req_qty:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Không tìm thấy đủ phiếu giữ chỗ tồn kho hợp lệ (RESERVED) cho lô #{batch_id} thuộc đơn hàng #{ff.order_id} (yêu cầu {req_qty}, có {total_res_qty}).",
                    )

                batch_plans.append({
                    "batch_id": batch_id,
                    "batch": batch,
                    "stock": stock,
                    "req_qty": req_qty,
                    "reservations": reservations,
                })

            # 4. Khi 100% tiền kiểm định đạt yêu cầu: Thực thi nguyên tử trong transaction
            ff.status = "SHIPPED"
            ff.shipped_at = now

            for plan in batch_plans:
                stock = plan["stock"]
                req_qty = plan["req_qty"]
                reservations = plan["reservations"]
                b_id = plan["batch_id"]

                stock.quantity_reserved -= req_qty
                stock.quantity_on_hand -= req_qty

                # Cập nhật StockReservation -> FULFILLED
                rem_to_fulfill = req_qty
                for r in reservations:
                    if rem_to_fulfill <= 0:
                        break
                    if r.quantity <= rem_to_fulfill:
                        r.status = "FULFILLED"
                        rem_to_fulfill -= r.quantity
                    else:
                        r.quantity -= rem_to_fulfill
                        db.add(
                            StockReservation(
                                order_id=r.order_id,
                                batch_id=r.batch_id,
                                warehouse_id=r.warehouse_id,
                                quantity=rem_to_fulfill,
                                status="FULFILLED",
                                expires_at=r.expires_at,
                            )
                        )
                        rem_to_fulfill = 0

                # Sinh duy nhất 1 bản ghi Thẻ kho (StockMovement - DISPATCH) cho mỗi lô
                db.add(
                    StockMovement(
                        movement_code=f"MOV-DISP-{ff.id}-{b_id}-{uuid.uuid4().hex[:6].upper()}",
                        movement_type="DISPATCH",
                        warehouse_id=ff.warehouse_id,
                        batch_id=b_id,
                        quantity=-req_qty,
                        balance_after=stock.quantity_on_hand,
                        reference_type="ORDER_FULFILLMENT",
                        reference_id=ff.fulfillment_code,
                        created_by=user_id,
                        note=f"Xuất kho kiện {ff.fulfillment_code} giao cho khách",
                    )
                )

        elif target_status == "PICKED":
            ff.status = "PICKED"
            if not ff.picked_at:
                ff.picked_at = now
        elif target_status == "PACKED":
            ff.status = "PACKED"
            if not ff.packed_at:
                ff.packed_at = now
        elif target_status == "DELIVERED":
            ff.status = "DELIVERED"
            if not ff.delivered_at:
                ff.delivered_at = now
        elif target_status == "CANCELLED":
            ff.status = "CANCELLED"
            # Hoàn trả lại tồn kho khả dụng nếu kiện bị hủy trước khi SHIPPED
            if old_status not in ["SHIPPED", "DELIVERED"]:
                allocations = db.scalars(
                    select(OrderItemBatchAllocation).where(
                        OrderItemBatchAllocation.fulfillment_item_id.in_([it.id for it in ff.items])
                    )
                ).all()
                for alloc in allocations:
                    stock = db.scalar(
                        select(WarehouseBatchStock).where(
                            WarehouseBatchStock.warehouse_id == alloc.warehouse_id,
                            WarehouseBatchStock.batch_id == alloc.batch_id,
                        )
                    )
                    if stock:
                        stock.quantity_reserved = max(0, stock.quantity_reserved - alloc.allocated_quantity)
                        stock.quantity_available += alloc.allocated_quantity

                    res = db.scalar(
                        select(StockReservation).where(
                            StockReservation.order_id == ff.order_id,
                            StockReservation.batch_id == alloc.batch_id,
                            StockReservation.warehouse_id == alloc.warehouse_id,
                            StockReservation.status == "RESERVED",
                        )
                    )
                    if res:
                        res.status = "RELEASED"

        # Đồng bộ trạng thái đơn hàng cha (Order)
        order = db.get(Order, ff.order_id)
        if order:
            all_ffs = db.scalars(select(OrderFulfillment).where(OrderFulfillment.order_id == order.id)).all()
            all_statuses = [f.status for f in all_ffs]

            if all(s == "DELIVERED" for s in all_statuses):
                order.order_status = "COMPLETED"
                order.fulfillment_status = "DELIVERED"
            elif any(s in ["SHIPPED", "DELIVERED"] for s in all_statuses):
                order.order_status = "SHIPPING"
                order.fulfillment_status = "SHIPPED"
            elif any(s in ["PICKED", "PACKED"] for s in all_statuses):
                order.order_status = "PROCESSING"
                order.fulfillment_status = "PACKED" if any(s == "PACKED" for s in all_statuses) else "PICKING"
            elif all(s == "CANCELLED" for s in all_statuses):
                order.order_status = "CANCELLED"
                order.fulfillment_status = "CANCELLED"

        db.commit()
        return ff

    @classmethod
    def release_order_reservations(
        cls,
        db: Session,
        order_id: int,
        reason: str = "ORDER_CANCELLED",
    ) -> int:
        """
        Giải phóng toàn bộ tồn kho thuốc đã giữ chỗ (StockReservation) của đơn hàng,
        hoàn trả lại quantity_available cho kho và hủy các kiện hàng PENDING.
        """
        reservations = db.scalars(
            select(StockReservation).where(
                StockReservation.order_id == order_id,
                StockReservation.status == "RESERVED",
            )
        ).all()

        released_count = 0
        for res in reservations:
            stock = db.scalar(
                select(WarehouseBatchStock).where(
                    WarehouseBatchStock.warehouse_id == res.warehouse_id,
                    WarehouseBatchStock.batch_id == res.batch_id,
                )
            )
            if stock:
                stock.quantity_reserved = max(0, stock.quantity_reserved - res.quantity)
                stock.quantity_available += res.quantity
            res.status = "RELEASED"
            released_count += res.quantity

        # Hủy các kiện hàng liên quan
        ffs = db.scalars(
            select(OrderFulfillment).where(
                OrderFulfillment.order_id == order_id,
                OrderFulfillment.status.in_(["PENDING", "PICKED", "PACKED"]),
            )
        ).all()
        for f in ffs:
            f.status = "CANCELLED"

        order = db.get(Order, order_id)
        if order and order.order_status not in ["COMPLETED", "SHIPPING"]:
            order.order_status = "CANCELLED"
            order.fulfillment_status = "CANCELLED"

        # Gửi thông báo hủy đơn đến kho được phân công và các kho liên quan
        warehouse_ids_to_notify = set()
        if order and order.assigned_warehouse_id:
            warehouse_ids_to_notify.add(order.assigned_warehouse_id)
        for f in ffs:
            if f.warehouse_id:
                warehouse_ids_to_notify.add(f.warehouse_id)
        for res in reservations:
            if res.warehouse_id:
                warehouse_ids_to_notify.add(res.warehouse_id)

        if order and warehouse_ids_to_notify:
            try:
                from app.services.warehouse_notification_service import WarehouseNotificationService
                for wh_id in warehouse_ids_to_notify:
                    WarehouseNotificationService.notify_order_cancelled(
                        db=db,
                        order=order,
                        warehouse_id=wh_id,
                        reason=reason,
                    )
            except Exception as e:
                logger.warning(f"Could not dispatch cancel notification to warehouses {warehouse_ids_to_notify}: {e}")

        db.commit()
        logger.info(f"[INVENTORY RESERVATION] Đã giải phóng {released_count} đơn vị thuốc cho đơn #{order_id} (Lý do: {reason})")
        return released_count

    @classmethod
    def expire_stale_reservations(
        cls,
        db: Session,
        max_age_minutes: int = 30,
    ) -> list[str]:
        """
        Quét và tự động giải phóng tồn kho cho các đơn hàng trực tuyến (MoMo / VietQR)
        đã quá hạn thời gian thanh toán mà chưa nhận được tiền.
        """
        threshold = datetime.now(UTC) - timedelta(minutes=max_age_minutes)
        stale_orders = db.scalars(
            select(Order).where(
                Order.payment_status == "PENDING",
                Order.order_status == "PENDING",
                Order.payment_method.in_(["MOMO", "BANK_TRANSFER", "VIETQR"]),
                Order.created_at <= threshold,
            )
        ).all()

        cancelled_order_codes = []
        for o in stale_orders:
            cls.release_order_reservations(db, o.id, reason="PAYMENT_EXPIRED")
            o.payment_status = "EXPIRED"
            cancelled_order_codes.append(o.order_code)

        db.commit()
        return cancelled_order_codes

    @classmethod
    def cancel_transfer_and_refund_order(
        cls,
        db: Session,
        transfer_id: int,
        reason: str,
        user_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Quyết định Q6: Tự động hủy đơn hàng và hoàn tiền 100% nếu điều chuyển kho nội bộ thất bại.
        - Hủy StockTransfer -> CANCELLED
        - Hủy Order -> CANCELLED & Order.fulfillment_status = CANCELLED
        - Giải phóng StockReservation của Order
        - Sinh RefundRecord hoàn tiền 100% số tiền đơn hàng
        - Sinh PaymentTransaction(REFUNDED)
        - Lưu Audit log và cảnh báo hệ thống
        """
        from app.models import Refund
        from app.models.inventory import StockTransfer

        transfer = db.get(StockTransfer, transfer_id)
        if not transfer:
            raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu điều chuyển kho")

        transfer.status = "CANCELLED"
        transfer.note = (transfer.note or "") + f" | HỦY ĐIỀU CHUYỂN: {reason}"
        now = utcnow()

        order = db.get(Order, transfer.order_id) if transfer.order_id else None
        refund_created = None

        if order:
            order.order_status = "CANCELLED"
            order.fulfillment_status = "CANCELLED"

            # Giải phóng tất cả tồn kho đã giữ chỗ cho đơn này
            reservations = db.scalars(
                select(StockReservation).where(
                    StockReservation.order_id == order.id,
                    StockReservation.status == "RESERVED",
                )
            ).all()
            for res in reservations:
                res.status = "RELEASED"
                stock = db.scalar(
                    select(WarehouseBatchStock).where(
                        WarehouseBatchStock.warehouse_id == res.warehouse_id,
                        WarehouseBatchStock.batch_id == res.batch_id,
                    )
                )
                if stock:
                    stock.quantity_reserved = max(0, stock.quantity_reserved - res.quantity)
                    stock.quantity_available += res.quantity

            # Hoàn tiền 100% nếu khách đã thanh toán hoặc đã tạo giao dịch
            refund_amount = order.total_amount
            refund_code = f"REF-AUTO-{order.order_code}-{int(now.timestamp()) % 100000}"
            refund_record = Refund(
                refund_code=refund_code,
                order_id=order.id,
                amount=refund_amount,
                currency="VND",
                refund_method=order.payment_method or "VIETQR",
                status="SUCCEEDED",
                reason=f"Tự động hoàn tiền 100% do điều chuyển kho nội bộ thất bại: {reason}",
                notes=f"Đơn hàng {order.order_code} hủy tự động do sự cố vận chuyển từ kho {transfer.from_warehouse_id} tới {transfer.to_warehouse_id}.",
                requested_at=now,
                succeeded_at=now,
            )
            db.add(refund_record)
            order.payment_status = "REFUNDED"

            # Thêm PaymentTransaction hoàn tiền
            refund_tx = PaymentTransaction(
                order_id=order.id,
                transaction_code=f"TXN-REF-{order.order_code}-{int(now.timestamp()) % 100000}",
                provider=order.payment_method or "VIETQR",
                amount=refund_amount,
                currency="VND",
                status="REFUNDED",
            )
            db.add(refund_tx)
            refund_created = refund_code

            logger.info(
                f"[TRANSFER_FAILED_REFUND] Đơn {order.order_code}: Tự động hoàn tiền 100% {refund_amount}đ. Lý do: {reason}"
            )

        db.commit()
        return {
            "success": True,
            "message": "Đã hủy điều chuyển và tự động hủy đơn hàng, hoàn tiền 100% cho khách hàng.",
            "transfer_id": transfer_id,
            "order_code": order.order_code if order else None,
            "refund_code": refund_created,
            "refund_amount": float(order.total_amount) if order else 0,
        }

    @classmethod
    def receive_transfer_and_consolidate(
        cls,
        db: Session,
        transfer_id: int,
        user_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Nhận hàng điều chuyển tại kho đích.
        Cập nhật chuyển kho hoàn tất -> Chuyển trạng thái đơn hàng sang CONSOLIDATED.
        """
        from app.models.inventory import StockTransfer

        transfer = db.get(StockTransfer, transfer_id)
        if not transfer:
            raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu điều chuyển kho")

        transfer.status = "COMPLETED"
        transfer.received_at = utcnow()

        # Cập nhật số lượng received_quantity trên các item
        for it in transfer.items:
            it.received_quantity = it.quantity

        order = db.get(Order, transfer.order_id) if transfer.order_id else None
        if order:
            pending_transfers = db.scalars(
                select(StockTransfer).where(
                    StockTransfer.order_id == order.id,
                    StockTransfer.status.in_(["DRAFT", "IN_TRANSIT"]),
                    StockTransfer.id != transfer.id,
                )
            ).all()

            if not pending_transfers:
                order.fulfillment_status = "CONSOLIDATED"
                logger.info(f"[CONSOLIDATED] Đơn {order.order_code}: Hàng đã gom đủ tại kho {order.assigned_warehouse_id}. Sẵn sàng đóng gói!")

        db.commit()
        return {
            "success": True,
            "message": "Đã tiếp nhận hàng điều chuyển thành công",
            "transfer_id": transfer_id,
            "order_fulfillment_status": order.fulfillment_status if order else None,
        }

    @classmethod
    def reroute_unfulfilled_orders_on_new_warehouse(
        cls,
        db: Session,
        new_warehouse: Warehouse,
    ) -> list[dict[str, Any]]:
        """
        Khi Admin tạo một kho mới hoặc kích hoạt lại một kho:
        Quét tất cả các đơn hàng chưa đóng gói / chưa giao (PENDING, CONFIRMED, PROCESSING).
        Không điều phối lại các đơn đã đóng gói (PACKED), đang giao (SHIPPED), đã giao (DELIVERED) hoặc đã hủy (CANCELLED).
        Nếu kho mới gần khách hơn kho hiện tại:
        - Chuyển assigned_warehouse_id = new_warehouse.id
        - Cập nhật assignment_distance_km, assignment_method = 'AUTO_REROUTED_NEW_WAREHOUSE', assigned_at = utcnow()
        - Cập nhật OrderFulfillment chưa xuất kho sang kho mới
        - Gửi thông báo kho mới nhận đơn (ORDER_NEW)
        """
        if not new_warehouse.is_active:
            return []
        if new_warehouse.lat is None or new_warehouse.lng is None:
            return []

        from app.services.geo_service import GeoService, calculate_haversine_distance

        candidate_orders = db.scalars(
            select(Order).where(
                Order.order_status.in_(["PENDING", "CONFIRMED", "PROCESSING"]),
                ~Order.fulfillment_status.in_(["PACKED", "SHIPPED", "DELIVERED", "CANCELLED"]),
            )
        ).all()

        rerouted = []
        new_lat, new_lng = float(new_warehouse.lat), float(new_warehouse.lng)

        for order in candidate_orders:
            combined_addr = f"{order.shipping_city or ''} {order.shipping_address or ''}".strip()
            cust_lat, cust_lng, _ = GeoService.resolve_customer_coordinates(
                lat=order.lat,
                lng=order.lng,
                province_code=order.province_code,
                district_code=order.district_code,
                address_text=combined_addr,
            )

            dist_to_new = calculate_haversine_distance(cust_lat, cust_lng, new_lat, new_lng)

            curr_dist = order.assignment_distance_km
            if curr_dist is None and order.assigned_warehouse_id:
                curr_wh = db.get(Warehouse, order.assigned_warehouse_id)
                if curr_wh and curr_wh.lat is not None and curr_wh.lng is not None:
                    curr_dist = calculate_haversine_distance(cust_lat, cust_lng, float(curr_wh.lat), float(curr_wh.lng))
                else:
                    curr_dist = 999999.0
            elif curr_dist is None:
                curr_dist = 999999.0

            if dist_to_new < curr_dist and order.assigned_warehouse_id != new_warehouse.id:
                old_wh_id = order.assigned_warehouse_id
                order.assigned_warehouse_id = new_warehouse.id
                order.assignment_distance_km = dist_to_new
                order.assignment_method = "AUTO_REROUTED_NEW_WAREHOUSE"
                order.assigned_at = utcnow()

                # Cập nhật order_fulfillments nếu có và chưa xuất kho
                order_ffs = db.scalars(
                    select(OrderFulfillment).where(OrderFulfillment.order_id == order.id)
                ).all()
                for ff in order_ffs:
                    if ff.status in ["PENDING", "ALLOCATED"]:
                        ff.warehouse_id = new_warehouse.id
                        ff.fulfillment_code = f"FF-{order.order_code}-{new_warehouse.code}"

                try:
                    from app.services.warehouse_notification_service import WarehouseNotificationService
                    WarehouseNotificationService.notify_order_new(db, order, new_warehouse.id)
                except Exception as e:
                    logger.warning(f"Lỗi tạo thông báo khi điều phối lại sang kho mới {order.order_code}: {e}")

                rerouted.append({
                    "order_id": order.id,
                    "order_code": order.order_code,
                    "old_warehouse_id": old_wh_id,
                    "new_warehouse_id": new_warehouse.id,
                    "new_warehouse_code": new_warehouse.code,
                    "distance_km": dist_to_new,
                })

        if rerouted:
            db.flush()
            logger.info(f"Đã điều phối lại {len(rerouted)} đơn hàng sang kho mới {new_warehouse.code}")

        return rerouted
