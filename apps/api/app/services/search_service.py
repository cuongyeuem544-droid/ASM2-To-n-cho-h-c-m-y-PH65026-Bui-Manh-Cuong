import logging
import re
from typing import List, Optional, Tuple

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.models import CanonicalProduct, ProductIngredient
from app.models.enums import PublishStatus
from app.services.normalization import normalize_for_match, strip_accents

logger = logging.getLogger("pharmatrust.search")


def init_fts_table(db: Session) -> None:
    """Khởi tạo bảng ảo FTS5 cho tìm kiếm toàn văn thuốc nếu chưa có."""
    try:
        db.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
                product_id UNINDEXED,
                canonical_name,
                unaccent_name,
                registration_number,
                active_ingredients,
                indications,
                dosage_form,
                manufacturer,
                tokenize = 'unicode61'
            );
        """))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Không thể khởi tạo bảng ảo FTS5 (có thể SQLite không hỗ trợ module FTS5): {e}")


def index_single_product(db: Session, product: CanonicalProduct) -> None:
    """Cập nhật chỉ mục FTS5 cho một sản phẩm."""
    try:
        # Chuẩn bị dữ liệu hoạt chất
        ingredients_list = []
        if product.ingredients:
            for pi in product.ingredients:
                if pi.ingredient and pi.ingredient.normalized_name:
                    ingredients_list.append(pi.ingredient.normalized_name)
                    if pi.original_strength_text:
                        ingredients_list.append(pi.original_strength_text)
        ingredients_str = " ".join(ingredients_list)

        unaccent_name = strip_accents(product.canonical_name or "").lower()
        unaccent_indications = strip_accents(product.indications or "").lower()
        unaccent_dosage = strip_accents(product.dosage_form or "").lower()

        # Dùng savepoint (nested transaction) để nếu FTS5 lỗi thì không rollback giao dịch chính
        with db.begin_nested():
            # Xóa bản ghi cũ nếu có
            db.execute(
                text("DELETE FROM products_fts WHERE product_id = :pid"),
                {"pid": str(product.id)},
            )

            # Chèn bản ghi mới
            db.execute(
                text("""
                    INSERT INTO products_fts (
                        product_id, canonical_name, unaccent_name, registration_number,
                        active_ingredients, indications, dosage_form, manufacturer
                    ) VALUES (
                        :pid, :name, :uname, :reg, :ing, :ind, :dosage, :mfg
                    )
                """),
                {
                    "pid": str(product.id),
                    "name": product.canonical_name or "",
                    "uname": unaccent_name,
                    "reg": product.registration_number or "",
                    "ing": ingredients_str,
                    "ind": f"{product.indications or ''} {unaccent_indications}",
                    "dosage": f"{product.dosage_form or ''} {unaccent_dosage}",
                    "mfg": product.manufacturer or "",
                },
            )
    except Exception as e:
        logger.debug(f"Bỏ qua index FTS5 cho sản phẩm {product.id}: {e}")


def reindex_all_products(db: Session) -> int:
    """Lập lại toàn bộ chỉ mục tìm kiếm FTS5 cho kho thuốc."""
    init_fts_table(db)
    try:
        db.execute(text("DELETE FROM products_fts"))
        db.commit()
    except Exception:
        pass

    products = db.scalars(select(CanonicalProduct)).all()
    indexed_count = 0
    for p in products:
        index_single_product(db, p)
        indexed_count += 1

    return indexed_count


def search_product_ids_fts(
    db: Session,
    query: str,
    limit: int = 50,
    offset: int = 0,
) -> List[int]:
    """
    Tìm kiếm danh sách ID sản phẩm qua FTS5 theo thứ tự độ liên quan (BM25 ranking).
    Hỗ trợ tiếng Việt có dấu, không dấu, tìm theo hoạt chất, bệnh lý/triệu chứng.
    """
    clean_q = query.strip()[:100]
    if not clean_q or len(clean_q) < 2:
        return []

    unaccent_q = strip_accents(clean_q).lower()
    
    # Tách từ khóa và lọc ký tự an toàn (loại bỏ toàn bộ ký tự đặc biệt FTS)
    words = [re.sub(r"[^\w\d]", "", w) for w in unaccent_q.split() if len(w) > 1]
    if not words:
        words = [re.sub(r"[^\w\d]", "", w) for w in clean_q.split() if w]
    
    if not words:
        return []

    # Xây dựng câu truy vấn FTS5 an toàn:
    # Ưu tiên khớp cả cụm nguyên bản an toàn -> khớp các từ đơn lẻ với tiền tố *
    safe_phrase = re.sub(r"[^\w\d\s]", " ", unaccent_q).strip()
    prefix_terms = " ".join([f'"{w}"*' for w in words[:8]])
    if safe_phrase:
        match_query = f'"{safe_phrase}" OR ({prefix_terms})'
    else:
        match_query = prefix_terms

    try:
        sql = text("""
            SELECT product_id, bm25(products_fts, 5.0, 4.0, 4.0, 3.0, 2.0, 1.0, 1.0) AS rank
            FROM products_fts
            WHERE products_fts MATCH :mq
            ORDER BY rank ASC
            LIMIT :lim OFFSET :off
        """)
        rows = db.execute(sql, {"mq": match_query, "lim": limit, "off": offset}).fetchall()
        if rows:
            return [int(r[0]) for r in rows if r[0]]
    except Exception as e:
        logger.debug(f"FTS5 query không thành công, chuyển sang fallback ranking: {e}")

    # Fallback nếu FTS5 không có kết quả hoặc gặp lỗi cú pháp FTS
    return _fallback_weighted_search(db, clean_q, unaccent_q, limit, offset)


def _fallback_weighted_search(
    db: Session,
    query: str,
    unaccent_q: str,
    limit: int,
    offset: int,
) -> List[int]:
    """
    Tìm kiếm dự phòng dựa trên SQL LIKE kết hợp tính điểm liên quan đa trường.
    """
    pattern_orig = f"%{query}%"
    pattern_unaccent = f"%{unaccent_q}%"

    products = db.scalars(
        select(CanonicalProduct).where(
            or_(
                CanonicalProduct.canonical_name.ilike(pattern_orig),
                CanonicalProduct.registration_number.ilike(pattern_orig),
                CanonicalProduct.indications.ilike(pattern_orig),
                CanonicalProduct.description.ilike(pattern_orig),
                CanonicalProduct.manufacturer.ilike(pattern_orig),
            )
        )
    ).all()

    # Tính điểm liên quan cho từng sản phẩm
    scored_products: List[Tuple[int, int]] = []
    for p in products:
        score = 0
        name = (p.canonical_name or "").lower()
        uname = strip_accents(name)
        reg = (p.registration_number or "").lower()
        ind = strip_accents(p.indications or "").lower()
        desc = strip_accents(p.description or "").lower()

        # 1. Khớp chính xác tên thuốc
        if unaccent_q in uname:
            score += 100
            if uname.startswith(unaccent_q):
                score += 50
        # 2. Khớp số đăng ký
        if unaccent_q in reg:
            score += 80
        # 3. Khớp chỉ định / công dụng y khoa
        if unaccent_q in ind:
            score += 40
        # 4. Khớp mô tả
        if unaccent_q in desc:
            score += 20

        scored_products.append((p.id, score))

    scored_products.sort(key=lambda x: x[1], reverse=True)
    return [pid for pid, _ in scored_products[offset : offset + limit]]
