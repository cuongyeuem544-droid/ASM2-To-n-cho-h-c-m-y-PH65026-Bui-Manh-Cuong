import logging
import re
from typing import List, Optional, Tuple

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.models import CanonicalProduct, Ingredient, ProductIngredient
from app.models.enums import PublishStatus
from app.services.normalization import normalize_for_match, strip_accents

logger = logging.getLogger("pharmatrust.search")

# Từ điển đồng nghĩa dược phẩm chuẩn hóa (Active ingredients <-> Common brand names)
# TUYỆT ĐỐI KHÔNG SUY DIỄN BỆNH LÝ NGUY HIỂM SANG THUỐC KÊ ĐƠN (Rx)
CURATED_PHARMACY_SYNONYMS: dict[str, list[str]] = {
    "paracetamol": ["hapacol", "efferalgan", "panadol", "acetaminophen"],
    "acetaminophen": ["paracetamol", "hapacol", "efferalgan", "panadol"],
    "hapacol": ["paracetamol"],
    "efferalgan": ["paracetamol"],
    "panadol": ["paracetamol"],
    "ibuprofen": ["gofen", "advil"],
    "cetirizine": ["zyrtec"],
    "loratadine": ["clarityne", "loratadin"],
    "fexofenadine": ["telfast"],
    "telfast": ["fexofenadine"],
    "diosmectite": ["smecta"],
    "smecta": ["diosmectite"],
    "berberin": ["berberine"],
    "berberine": ["berberin"],
    "prospan": ["cao la thuong xuan", "siro ho"],
    "gaviscon": ["antacid", "da day"],
    "vitamin c": ["acid ascorbic", "ceelin"],
    "oresol": ["o resol", "hydrite", "bu nuoc"],
}

# Từ điển sửa lỗi chính tả thường gặp khi tìm kiếm thuốc tại Việt Nam
COMMON_MISSPELLINGS: dict[str, str] = {
    "paracetamon": "paracetamol",
    "paracetamoll": "paracetamol",
    "parasitamol": "paracetamol",
    "paracelamol": "paracetamol",
    "panadoll": "panadol",
    "panadon": "panadol",
    "efferalgane": "efferalgan",
    "eferalgan": "efferalgan",
    "efferalgang": "efferalgan",
    "hapacool": "hapacol",
    "berberine": "berberin",
    "beberin": "berberin",
    "smacta": "smecta",
    "smeta": "smecta",
    "prospam": "prospan",
    "prospant": "prospan",
    "gavisconne": "gaviscon",
    "loratadin": "loratadine",
    "cetirizin": "cetirizine",
    "fexofenadin": "fexofenadine",
    "vitaminc": "vitamin c",
    "omega3": "omega 3",
}


def _is_sqlite(db: Session) -> bool:
    try:
        bind = db.get_bind()
        return bind is not None and getattr(bind.dialect, "name", "") == "sqlite"
    except Exception:
        return False


def init_fts_table(db: Session) -> None:
    """Khởi tạo bảng ảo FTS5 cho tìm kiếm toàn văn thuốc nếu dùng SQLite."""
    if not _is_sqlite(db):
        return
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
    """Cập nhật chỉ mục FTS5 cho một sản phẩm (chỉ trên SQLite)."""
    if not _is_sqlite(db):
        return
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
    """Lập lại toàn bộ chỉ mục tìm kiếm FTS5 cho kho thuốc (chỉ trên SQLite)."""
    if not _is_sqlite(db):
        return 0
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
    Tìm kiếm danh sách ID sản phẩm theo thứ tự độ liên quan.
    Hỗ trợ tiếng Việt có dấu, không dấu, tìm theo tên thương mại, hoạt chất, số ĐK, NSX.
    Tự động áp dụng từ điển đồng nghĩa & sửa lỗi chính tả thường gặp.
    Tương thích cả SQLite FTS5 lẫn Neon PostgreSQL.
    """
    clean_q = query.strip()[:100]
    if not clean_q or len(clean_q) < 2:
        return []

    # Sửa lỗi chính tả thường gặp
    lower_q = clean_q.lower()
    corrected_q = COMMON_MISSPELLINGS.get(lower_q, lower_q)
    unaccent_q = strip_accents(corrected_q).lower()

    # Mở rộng từ đồng nghĩa dược khoa hợp lệ
    synonyms = CURATED_PHARMACY_SYNONYMS.get(unaccent_q, [])

    if _is_sqlite(db):
        words = [re.sub(r"[^\w\d]", "", w) for w in unaccent_q.split() if len(w) > 1]
        if not words:
            words = [re.sub(r"[^\w\d]", "", w) for w in clean_q.split() if w]

        if words:
            safe_phrase = re.sub(r"[^\w\d\s]", " ", unaccent_q).strip()
            prefix_terms = " ".join([f'"{w}"*' for w in words[:8]])
            if safe_phrase:
                match_query = f'"{safe_phrase}" OR ({prefix_terms})'
            else:
                match_query = prefix_terms

            try:
                with db.begin_nested():
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

    # Fallback chuẩn hóa an toàn trên PostgreSQL (Neon) và SQLite với từ đồng nghĩa & đa trường
    return _fallback_weighted_search(db, corrected_q, unaccent_q, synonyms=synonyms, limit=limit, offset=offset)


def _fallback_weighted_search(
    db: Session,
    query: str,
    unaccent_q: str,
    synonyms: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> List[int]:
    """
    Tìm kiếm dự phòng dựa trên SQL LIKE kết hợp tính điểm liên quan đa trường.
    Bao gồm tên thuốc, hoạt chất (ProductIngredient), số đăng ký, chỉ định, nhà sản xuất.
    """
    if synonyms is None:
        synonyms = []

    pattern_orig = f"%{query}%"
    pattern_unaccent = f"%{unaccent_q}%"

    search_conditions = [
        CanonicalProduct.canonical_name.ilike(pattern_orig),
        CanonicalProduct.canonical_name.ilike(pattern_unaccent),
        CanonicalProduct.registration_number.ilike(pattern_orig),
        CanonicalProduct.indications.ilike(pattern_orig),
        CanonicalProduct.indications.ilike(pattern_unaccent),
        CanonicalProduct.description.ilike(pattern_orig),
        CanonicalProduct.manufacturer.ilike(pattern_orig),
        Ingredient.normalized_name.ilike(pattern_orig),
        Ingredient.normalized_name.ilike(pattern_unaccent),
    ]

    for syn in synonyms[:4]:
        search_conditions.append(CanonicalProduct.canonical_name.ilike(f"%{syn}%"))
        search_conditions.append(Ingredient.normalized_name.ilike(f"%{syn}%"))

    products_query = (
        select(CanonicalProduct)
        .options(
            selectinload(CanonicalProduct.ingredients).selectinload(ProductIngredient.ingredient)
        )
        .join(ProductIngredient, ProductIngredient.product_id == CanonicalProduct.id, isouter=True)
        .join(Ingredient, Ingredient.id == ProductIngredient.ingredient_id, isouter=True)
        .where(
            CanonicalProduct.publish_status == PublishStatus.PUBLISHED,
            or_(*search_conditions),
        )
        .distinct()
    )

    products = db.scalars(products_query).all()

    # Tính điểm liên quan cho từng sản phẩm
    scored_products: List[Tuple[int, int]] = []
    query_tokens = [w for w in unaccent_q.split() if len(w) > 1]

    for p in products:
        score = 0
        name = (p.canonical_name or "").lower()
        uname = strip_accents(name)
        reg = (p.registration_number or "").lower()
        ind = strip_accents(p.indications or "").lower()
        desc = strip_accents(p.description or "").lower()
        mfg = strip_accents(p.manufacturer or "").lower()

        # 1. Khớp chính xác tên thuốc
        if unaccent_q == uname:
            score += 200
        elif uname.startswith(unaccent_q):
            score += 150
        elif unaccent_q in uname:
            score += 100

        # Khớp từng từ đơn lẻ trong tên thuốc
        for token in query_tokens:
            if token in uname:
                score += 30

        # 2. Khớp số đăng ký
        if unaccent_q in reg:
            score += 120

        # 3. Khớp hoạt chất (Active Ingredients)
        if p.ingredients:
            for pi in p.ingredients:
                if pi.ingredient and pi.ingredient.normalized_name:
                    ing_name = strip_accents(pi.ingredient.normalized_name.lower())
                    if unaccent_q in ing_name:
                        score += 110
                    for token in query_tokens:
                        if token in ing_name:
                            score += 25
                    if pi.original_strength_text and any(tok in pi.original_strength_text.lower() for tok in query_tokens):
                        score += 40

        # 4. Khớp từ đồng nghĩa
        for syn in synonyms:
            if syn in uname:
                score += 70

        # 5. Khớp nhà sản xuất
        if unaccent_q in mfg:
            score += 50

        # 6. Khớp chỉ định / công dụng y khoa
        if unaccent_q in ind:
            score += 40

        # 7. Khớp mô tả
        if unaccent_q in desc:
            score += 20

        scored_products.append((p.id, score))

    scored_products.sort(key=lambda x: x[1], reverse=True)
    return [pid for pid, _ in scored_products[offset : offset + limit]]
