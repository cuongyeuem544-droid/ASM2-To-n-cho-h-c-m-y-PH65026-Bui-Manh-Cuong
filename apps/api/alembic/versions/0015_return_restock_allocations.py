"""Migration: Return Restock Allocations with Multi-Batch Idempotency and Historical Backfill.

Revision ID: 0015_return_restock_allocations
Revises: 0014_live_chat_attachments
"""
import re
from alembic import op
import sqlalchemy as sa

revision = "0015_return_restock_allocations"
down_revision = "0014_live_chat_attachments"
branch_labels = None
depends_on = None


def _get_existing_tables(conn) -> set[str]:
    inspector = sa.inspect(conn)
    return set(inspector.get_table_names())


def upgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)

    if "return_restock_allocations" not in tables:
        op.create_table(
            "return_restock_allocations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("canonical_return_code", sa.String(50), nullable=False, index=True),
            sa.Column("source_type", sa.String(50), nullable=False),
            sa.Column("source_code", sa.String(50), nullable=False, index=True),
            sa.Column("order_item_id", sa.Integer(), sa.ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("batch_id", sa.Integer(), sa.ForeignKey("inventory_batches.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("stock_movement_id", sa.Integer(), sa.ForeignKey("stock_movements.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.UniqueConstraint("canonical_return_code", "order_item_id", "batch_id", name="uq_restock_canonical_item_batch"),
        )

    # Backfill ReturnRestockAllocation từ StockMovement lịch sử khi có thể xác định chắc chắn 100%
    # Dữ liệu lịch sử không xác định được order_item/batch phải fail-closed và đưa ra danh sách cần đối soát.
    movements = conn.execute(
        sa.text(
            "SELECT id, movement_code, warehouse_id, batch_id, quantity, reference_type, reference_id, note, created_at "
            "FROM stock_movements WHERE movement_type = 'RETURN_RESTOCK'"
        )
    ).fetchall()

    if not movements:
        return

    existing_alloc_mv_ids = {
        row[0]
        for row in conn.execute(
            sa.text("SELECT stock_movement_id FROM return_restock_allocations WHERE stock_movement_id IS NOT NULL")
        ).fetchall()
    }

    unresolvable: list[dict] = []
    to_insert: list[dict] = []

    for mv in movements:
        mv_id, mv_code, wh_id, batch_id, qty, ref_type, ref_id, note, created_at = mv
        if mv_id in existing_alloc_mv_ids:
            continue

        ref_code = (ref_id or "").strip()
        note_str = note or ""
        resolved_order_item_id = None

        # 1. Trích xuất từ note nếu có pattern rõ ràng
        m_order_item = re.search(r"\[order_item_id:(\d+)\]", note_str) or re.search(r"order_item\s*#(\d+)", note_str)
        if m_order_item:
            resolved_order_item_id = int(m_order_item.group(1))

        # 2. Nếu chưa có trong note, tra cứu qua chứng từ hoàn (ReturnRequest hoặc WarehouseReturnCase)
        if not resolved_order_item_id and ref_code:
            # Tra cứu qua WarehouseReturnCase
            case_row = conn.execute(
                sa.text("SELECT id, return_request_id FROM warehouse_return_cases WHERE case_code = :code"),
                {"code": ref_code},
            ).fetchone()

            if case_row:
                case_id = case_row[0]
                # Lấy các return_items thuộc case này có batch_id khớp trong OrderItemBatchAllocation
                candidates = conn.execute(
                    sa.text(
                        "SELECT DISTINCT ri.order_item_id "
                        "FROM return_items ri "
                        "JOIN order_item_batch_allocations a ON a.order_item_id = ri.order_item_id "
                        "WHERE ri.warehouse_return_case_id = :case_id AND a.batch_id = :batch_id"
                    ),
                    {"case_id": case_id, "batch_id": batch_id},
                ).fetchall()

                if len(candidates) == 1:
                    resolved_order_item_id = candidates[0][0]
                elif len(candidates) == 0:
                    # Thử mở rộng sang return_request của case
                    ret_req_id = case_row[1]
                    if ret_req_id:
                        req_candidates = conn.execute(
                            sa.text(
                                "SELECT DISTINCT ri.order_item_id "
                                "FROM return_items ri "
                                "JOIN order_item_batch_allocations a ON a.order_item_id = ri.order_item_id "
                                "WHERE ri.return_request_id = :req_id AND a.batch_id = :batch_id"
                            ),
                            {"req_id": ret_req_id, "batch_id": batch_id},
                        ).fetchall()
                        if len(req_candidates) == 1:
                            resolved_order_item_id = req_candidates[0][0]
            else:
                # Tra cứu qua ReturnRequest trực tiếp
                req_row = conn.execute(
                    sa.text("SELECT id FROM return_requests WHERE return_code = :code"),
                    {"code": ref_code},
                ).fetchone()
                if req_row:
                    req_id = req_row[0]
                    req_candidates = conn.execute(
                        sa.text(
                            "SELECT DISTINCT ri.order_item_id "
                            "FROM return_items ri "
                            "JOIN order_item_batch_allocations a ON a.order_item_id = ri.order_item_id "
                            "WHERE ri.return_request_id = :req_id AND a.batch_id = :batch_id"
                        ),
                        {"req_id": req_id, "batch_id": batch_id},
                    ).fetchall()
                    if len(req_candidates) == 1:
                        resolved_order_item_id = req_candidates[0][0]

        # 3. Kiểm tra tính toàn vẹn: nếu không thể xác định batch_id hoặc order_item_id -> Fail Closed
        if not resolved_order_item_id or not batch_id or not ref_code:
            unresolvable.append({
                "movement_id": mv_id,
                "movement_code": mv_code,
                "reference_id": ref_id,
                "batch_id": batch_id,
                "note": note,
            })
            continue

        canonical_code = ref_code
        src_type = ref_type or ("WAREHOUSE_RETURN_CASE" if ref_code.startswith("WRC-") else "RETURN_REQUEST")

        to_insert.append({
            "canonical_return_code": canonical_code,
            "source_type": src_type,
            "source_code": ref_code,
            "order_item_id": resolved_order_item_id,
            "batch_id": batch_id,
            "warehouse_id": wh_id,
            "quantity": qty,
            "stock_movement_id": mv_id,
            "created_at": created_at,
        })

    if unresolvable:
        raise RuntimeError(
            f"Migration 0015 fail-closed: Phát hiện {len(unresolvable)} bản ghi StockMovement RETURN_RESTOCK lịch sử "
            f"không thể xác định chính xác order_item_id hoặc batch_id với độ tin cậy 100%. "
            f"Bắt buộc đối soát dữ liệu: {unresolvable}"
        )

    for item in to_insert:
        # Kiểm tra trùng constraint trước khi chèn
        existing = conn.execute(
            sa.text(
                "SELECT id FROM return_restock_allocations "
                "WHERE canonical_return_code = :code AND order_item_id = :oid AND batch_id = :bid"
            ),
            {"code": item["canonical_return_code"], "oid": item["order_item_id"], "bid": item["batch_id"]},
        ).fetchone()
        if not existing:
            conn.execute(
                sa.text(
                    "INSERT INTO return_restock_allocations "
                    "(canonical_return_code, source_type, source_code, order_item_id, batch_id, warehouse_id, quantity, stock_movement_id, created_at) "
                    "VALUES (:canonical_return_code, :source_type, :source_code, :order_item_id, :batch_id, :warehouse_id, :quantity, :stock_movement_id, :created_at)"
                ),
                item,
            )


def downgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)
    if "return_restock_allocations" in tables:
        op.drop_table("return_restock_allocations")
