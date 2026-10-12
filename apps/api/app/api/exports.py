import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import CanonicalProduct, User
from app.models.enums import UserRole


router = APIRouter(prefix="/exports", tags=["Xuất dữ liệu"])


def _rows(db: Session, include_demo: bool) -> list[dict]:
    from app.models import ProductIngredient

    query = select(CanonicalProduct).options(
        selectinload(CanonicalProduct.source_fields),
        selectinload(CanonicalProduct.ingredients).selectinload(ProductIngredient.ingredient),
    ).order_by(CanonicalProduct.canonical_name)
    if not include_demo:
        query = query.where(CanonicalProduct.is_demo.is_(False))
    products = db.scalars(query).all()
    return [
        {
            "id": product.id,
            "canonical_name": product.canonical_name,
            "registration_number": product.registration_number,
            "ingredients": ", ".join(
                f"{item.ingredient.normalized_name} {item.strength_value or ''}{item.strength_unit or ''}".strip()
                for item in product.ingredients if item.ingredient
            ),
            "manufacturer": product.manufacturer,
            "manufacturing_country": product.manufacturing_country,
            "dosage_form": product.dosage_form,
            "route": product.route,
            "package_description": product.package_description,
            "image_url": product.image_url,
            "indications": product.indications,
            "usage_instructions": product.usage_instructions,
            "contraindications": product.contraindications,
            "side_effects": product.side_effects,
            "storage_conditions": product.storage_conditions,
            "description": product.description,
            "rx_otc_status": product.rx_otc_status.value,
            "regulatory_status": product.regulatory_status.value,
            "overall_score": product.overall_score,
            "confidence_label": product.confidence_label.value,
            "publish_status": product.publish_status.value,
            "registration_valid_to": product.registration_valid_to.isoformat() if product.registration_valid_to else None,
            "is_demo": product.is_demo,
            "updated_at": product.updated_at.isoformat(),
            "source_evidence": json.dumps(
                [{"source_id": item.source_id, "field": item.field_name, "observed_at": item.observed_at.isoformat()} for item in product.source_fields],
                ensure_ascii=False,
            ),
        }
        for product in products
    ]


@router.get("/products")
def export_products(
    format: str = Query("csv", pattern="^(csv|xlsx|json)$"),
    include_demo: bool = True,
    _: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    rows = _rows(db, include_demo)
    if not rows:
        raise HTTPException(status_code=404, detail="Không có dữ liệu để xuất")
    if format == "json":
        content = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
        media_type = "application/json"
    elif format == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Products"
        sheet.append(list(rows[0].keys()))
        for row in rows:
            sheet.append(list(row.values()))
        stream = io.BytesIO()
        workbook.save(stream)
        content = stream.getvalue()
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        content = ("\ufeff" + stream.getvalue()).encode("utf-8")
        media_type = "text/csv"
    headers = {"Content-Disposition": f'attachment; filename="pharmatrust-products.{format}"'}
    return StreamingResponse(io.BytesIO(content), media_type=media_type, headers=headers)

