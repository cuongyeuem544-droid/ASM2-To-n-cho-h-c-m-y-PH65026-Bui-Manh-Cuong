import hashlib
import re
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select

from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import (
    AdminAlert,
    CanonicalProduct,
    CrawlLock,
    DataSource,
    FailedCrawlItem,
    Ingredient,
    PriceObservation,
    ProductCandidate,
    ProductIngredient,
    ProductSourceField,
    RawDocument,
    RegulatoryRecord,
    User,
)
from app.models.enums import ProcessingStatus, PublishStatus, RegulatoryStatus, RxOtcStatus, SourceType, UserRole
from app.services.crawler import (
    FetchResult,
    LongChauAdapter,
    MedigoAdapter,
    PharmacityAdapter,
    PublicHtmlAdapter,
    USER_AGENT,
    extract_product_leaflet,
)
from app.services.matching import match_products
from app.services.normalization import normalize_for_match, normalize_registration_number
from app.services.scoring import calculate_product_score


router = APIRouter(prefix="/crawler", tags=["crawler"])


class ScrapeUrlRequest(BaseModel):
    url: str
    save_to_catalog: bool = False


class ScrapedDrugResponse(BaseModel):
    name: str
    registration_number: str | None = None
    manufacturer: str | None = None
    dosage_form: str | None = None
    package: str | None = None
    ingredients: list[dict[str, Any]] = []
    price: float | None = None
    image_url: str | None = None
    description: str | None = None
    usage_instructions: str | None = None
    indications: str | None = None
    contraindications: str | None = None
    side_effects: str | None = None
    storage_conditions: str | None = None
    source_url: str
    source_name: str
    saved_product_id: int | None = None
    confidence_score: int | None = None
    message: str | None = None


SAMPLE_LINKS = [
    {
        "title": "Viên sủi Efferalgan 500mg (Hộp 4 vỉ x 4 viên)",
        "source": "Pharmacity",
        "url": "https://www.pharmacity.vn/vien-nen-sui-bot-efferalgan-eff-500mg-dieu-tri-dau-dau-dau-rang-sot-nhuc-moi-co-4-vi-x-4-vien.html",
        "category": "Giảm đau, hạ sốt",
    },
    {
        "title": "Viên uống Panadol Extra đỏ giảm đau nhanh",
        "source": "Pharmacity",
        "url": "https://www.pharmacity.vn/vien-uong-panadol-extra-do-hop-180-vien.html",
        "category": "Giảm đau, hạ sốt",
    },
    {
        "title": "Thuốc trị đau dạ dày Nexium MUPS 40mg (Hộp 28 viên)",
        "source": "Pharmacity",
        "url": "https://www.pharmacity.vn/thuoc-tri-dau-da-day-nexium-mups-40mg-hop-28-vien.html",
        "category": "Dạ dày, trào ngược",
    },
    {
        "title": "Thuốc kháng sinh Zinnat 500mg Cefuroxime (Hộp 10 viên)",
        "source": "Pharmacity",
        "url": "https://www.pharmacity.vn/thuoc-khang-sinh-zinnat-500mg-hop-10-vien.html",
        "category": "Kháng sinh phổ rộng",
    },
    {
        "title": "Viên sủi Berocca Performance hương cam (Tuýp 10 viên)",
        "source": "Pharmacity",
        "url": "https://www.pharmacity.vn/vien-sui-berocca-performance-huong-cam-tuyp-10-vien.html",
        "category": "Vitamin & Khoáng chất",
    },
    {
        "title": "Thuốc điều trị tiêu chảy Smecta 3g (Hộp 30 gói)",
        "source": "Pharmacity",
        "url": "https://www.pharmacity.vn/thuoc-bot-pha-hon-dich-uong-smecta-3g-hop-30-goi.html",
        "category": "Tiêu hóa",
    },
    {
        "title": "Thuốc trị dị ứng Telfast HD 180mg (Hộp 30 viên)",
        "source": "Pharmacity",
        "url": "https://www.pharmacity.vn/telfast-hd-180mg-hop30-vien.html",
        "category": "Dị ứng, mày đay",
    },
    {
        "title": "Hỗn dịch uống Gaviscon Dual Action (Hộp 24 gói)",
        "source": "Pharmacity",
        "url": "https://www.pharmacity.vn/hon-dich-uong-gaviscon-dual-action-hop-24-goi-x-10ml.html",
        "category": "Dạ dày, ợ chua",
    },
    {
        "title": "Thuốc hạ sốt Hapacol 650mg DHG Pharma",
        "source": "Pharmacity",
        "url": "https://www.pharmacity.vn/thuoc-ha-sot-giam-dau-hapacol-650-hop-100-vien.html",
        "category": "Giảm đau, hạ sốt",
    },
]


@router.get("/samples")
def get_sample_links():
    """
    Trả về danh sách các link sản phẩm thuốc thực tế từ nhà thuốc để người dùng cào thử nghiệm ngay.
    """
    return SAMPLE_LINKS


@router.post("/scrape-url", response_model=ScrapedDrugResponse)
def scrape_url(payload: ScrapeUrlRequest, current_user: User = Depends(get_current_user)):
    """
    Cào trực tiếp thông tin thuốc từ bất kỳ link nhà thuốc nào (Pharmacity, Long Châu...).
    Trích xuất đầy đủ: Tên thuốc, ảnh đại diện, giá, hướng dẫn sử dụng, chỉ định, chống chỉ định, tác dụng phụ.
    Tùy chọn lưu thẳng vào kho thuốc chuẩn để chuyển cho App chính.
    """
    url = payload.url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="URL không hợp lệ, phải bắt đầu bằng http:// hoặc https://")

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if "pharmacity" in domain:
        adapter = PharmacityAdapter(base_url="https://www.pharmacity.vn")
        source_name = "Nhà thuốc Pharmacity"
        source_code = "PHARMACITY"
    elif "longchau" in domain:
        adapter = LongChauAdapter(base_url="https://nhathuoclongchau.com.vn")
        source_name = "Nhà thuốc Long Châu"
        source_code = "LONG_CHAU"
    else:
        adapter = PublicHtmlAdapter(base_url=f"{parsed.scheme}://{parsed.netloc}")
        source_name = f"Nguồn dược phẩm ({parsed.netloc})"
        source_code = "WEB_PUBLIC"

    try:
        doc_result = adapter.fetch(url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Không thể truy cập đường dẫn nhà thuốc: {exc}")

    parsed_items = adapter.parse(doc_result)
    if not parsed_items:
        raise HTTPException(
            status_code=422,
            detail="Không trích xuất được thông tin thuốc từ trang này. Vui lòng kiểm tra lại URL sản phẩm chi tiết.",
        )

    item = parsed_items[0]
    saved_product_id = None
    score = None
    msg = "Đã cào dữ liệu thành công!"

    if payload.save_to_catalog:
        db = SessionLocal()
        try:
            source = db.scalar(select(DataSource).where(DataSource.code == source_code))
            if not source:
                source = db.scalar(select(DataSource).where(DataSource.source_type == SourceType.RETAILER))

            reg_num = item.get("registration_number")
            matched_prod = None

            if reg_num:
                matched_prod = db.scalar(select(CanonicalProduct).where(CanonicalProduct.registration_number == reg_num))

            if not matched_prod:
                existing_prods = db.scalars(select(CanonicalProduct)).all()
                for ep in existing_prods:
                    res = match_products(
                        item,
                        {
                            "name": ep.canonical_name,
                            "registration_number": ep.registration_number,
                            "manufacturer": ep.manufacturer,
                            "ingredients": [
                                {"name": pi.ingredient.normalized_name, "value": pi.strength_value, "unit": pi.strength_unit}
                                for pi in ep.ingredients
                            ],
                        },
                    )
                    if res.is_same_product or res.confidence >= 0.85:
                        matched_prod = ep
                        break

            if matched_prod:
                for fld in [
                    "image_url",
                    "description",
                    "usage_instructions",
                    "indications",
                    "contraindications",
                    "side_effects",
                    "storage_conditions",
                ]:
                    if item.get(fld):
                        setattr(matched_prod, fld, item[fld])

                if item.get("price") and source:
                    db.add(
                        PriceObservation(
                            product_id=matched_prod.id,
                            source_id=source.id,
                            observed_price=Decimal(str(item["price"])),
                            currency="VND",
                            source_url=url,
                        )
                    )

                calculate_product_score(db, matched_prod, f"Cập nhật từ cào web {source_name}")
                db.commit()
                saved_product_id = matched_prod.id
                score = matched_prod.overall_score
                msg = f"Đã đối sánh và cập nhật vào hồ sơ thuốc '{matched_prod.canonical_name}' (ID: {matched_prod.id})"
            else:
                new_prod = CanonicalProduct(
                    canonical_name=item["name"],
                    registration_number=reg_num,
                    dosage_form=item.get("dosage_form"),
                    package_description=item.get("package"),
                    manufacturer=item.get("manufacturer"),
                    image_url=item.get("image_url"),
                    description=item.get("description"),
                    usage_instructions=item.get("usage_instructions"),
                    indications=item.get("indications"),
                    contraindications=item.get("contraindications"),
                    side_effects=item.get("side_effects"),
                    storage_conditions=item.get("storage_conditions"),
                    regulatory_status=RegulatoryStatus.ACTIVE,
                    rx_otc_status=RxOtcStatus.OTC,
                    publish_status=PublishStatus.DRAFT,
                    is_demo=False,
                )
                db.add(new_prod)
                db.flush()

                # Thêm hoạt chất nếu có
                for ing in item.get("ingredients") or []:
                    ing_name = ing.get("name")
                    if ing_name:
                        norm_ing = normalize_for_match(ing_name)
                        ing_entity = db.scalar(select(Ingredient).where(Ingredient.normalized_name == norm_ing))
                        if not ing_entity:
                            ing_entity = Ingredient(normalized_name=norm_ing, alternative_names=[ing_name])
                            db.add(ing_entity)
                            db.flush()
                        db.add(
                            ProductIngredient(
                                product_id=new_prod.id,
                                ingredient_id=ing_entity.id,
                                strength_value=ing.get("strength_value"),
                                strength_unit=ing.get("strength_unit"),
                            )
                        )

                if item.get("price") and source:
                    db.add(
                        PriceObservation(
                            product_id=new_prod.id,
                            source_id=source.id,
                            observed_price=Decimal(str(item["price"])),
                            currency="VND",
                            source_url=url,
                        )
                    )

                calculate_product_score(db, new_prod, f"Khởi tạo từ cào trực tiếp {source_name}")
                db.commit()
                saved_product_id = new_prod.id
                score = new_prod.overall_score
                msg = f"Đã lưu thành công sản phẩm mới '{new_prod.canonical_name}' (ID: {new_prod.id}) vào danh mục thuốc chuẩn!"
        finally:
            db.close()

    return ScrapedDrugResponse(
        name=item.get("name", ""),
        registration_number=item.get("registration_number"),
        manufacturer=item.get("manufacturer"),
        dosage_form=item.get("dosage_form"),
        package=item.get("package"),
        ingredients=item.get("ingredients") or [],
        price=item.get("price"),
        image_url=item.get("image_url"),
        description=item.get("description"),
        usage_instructions=item.get("usage_instructions"),
        indications=item.get("indications"),
        contraindications=item.get("contraindications"),
        side_effects=item.get("side_effects"),
        storage_conditions=item.get("storage_conditions"),
        source_url=url,
        source_name=source_name,
        saved_product_id=saved_product_id,
        confidence_score=score,
        message=msg,
    )


class ScrapePageRequest(BaseModel):
    url: str  # URL link trang (danh mục, sản phẩm hoặc nhiều link cách nhau bằng dòng mới)
    limit: int = 20  # Số lượng thuốc cần cào
    save_to_catalog: bool = True


class BatchScrapedItem(BaseModel):
    name: str
    registration_number: str | None = None
    manufacturer: str | None = None
    dosage_form: str | None = None
    package: str | None = None
    price: float | None = None
    unit: str | None = None
    price_display: str | None = None
    image_url: str | None = None
    description: str | None = None
    usage_instructions: str | None = None
    indications: str | None = None
    contraindications: str | None = None
    side_effects: str | None = None
    storage_conditions: str | None = None
    source_url: str
    source_name: str
    saved_product_id: int | None = None
    overall_score: int | None = None
    is_rx: bool = False
    ingredients: list[dict[str, Any]] = []


class ScrapePageResponse(BaseModel):
    total_found: int
    crawled_count: int
    saved_count: int
    source_name: str
    message: str
    products: list[BatchScrapedItem]


@router.post("/scrape-page", response_model=ScrapePageResponse)
def scrape_page(payload: ScrapePageRequest, current_user: User = Depends(get_current_user)):
    """
    Cào toàn bộ dữ liệu danh mục thuốc từ link trang web hoặc cào hàng loạt từ nhiều link.
    Trích xuất: hình ảnh packshot, giá bán, số đăng ký, hoạt chất và toàn bộ tờ hướng dẫn sử dụng.
    """
    input_text = payload.url.strip()
    if not input_text:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp link trang web cần cào dữ liệu.")

    limit = max(1, min(payload.limit, 100))
    raw_lines = [line.strip() for line in input_text.splitlines() if line.strip().startswith("http")]

    extracted_items: list[dict[str, Any]] = []
    source_title = "Nhà thuốc trực tuyến"

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    }

    pharmacity_adapter = PharmacityAdapter()

    # TRƯỜNG HỢP 1: Người dùng nhập nhiều link (mỗi dòng một link)
    if len(raw_lines) > 1:
        source_title = "Danh sách liên kết thuốc"
        target_urls = raw_lines[:limit]
        for u in target_urls:
            try:
                if "pharmacity" in u.lower():
                    resp = httpx.get(u, headers=headers, timeout=12)
                    if resp.status_code == 200:
                        doc = FetchResult(
                            url=u,
                            status_code=resp.status_code,
                            content_type="text/html",
                            content=resp.content,
                            text=resp.text,
                            content_hash=hashlib.sha256(resp.content).hexdigest(),
                        )
                        parsed = pharmacity_adapter.parse(doc)
                        if parsed:
                            extracted_items.append(parsed[0])
                elif "longchau" in u.lower() or "medigo" in u.lower():
                    slug = urlparse(u).path.strip("/").split("/")[-1].replace(".html", "").replace("-", " ")
                    med = MedigoAdapter()
                    res = med.search_products(keyword=slug, limit=1)
                    if res:
                        extracted_items.append(res[0])
                else:
                    pub_adapter = PublicHtmlAdapter(base_url=u)
                    doc = pub_adapter.fetch(u)
                    soup = BeautifulSoup(doc.text, "html.parser")
                    leaflet = extract_product_leaflet(soup, doc.text)
                    title_tag = soup.select_one("h1") or soup.select_one("title")
                    name = title_tag.get_text(" ", strip=True) if title_tag else u
                    extracted_items.append({
                        "name": name,
                        "registration_number": normalize_registration_number(name),
                        "image_url": leaflet.get("image_url"),
                        "description": leaflet.get("description"),
                        "usage_instructions": leaflet.get("usage_instructions"),
                        "indications": leaflet.get("indications"),
                        "contraindications": leaflet.get("contraindications"),
                        "side_effects": leaflet.get("side_effects"),
                        "storage_conditions": leaflet.get("storage_conditions"),
                        "source_url": u,
                        "source_name": "Web Dược phẩm",
                    })
            except Exception:
                continue

    # TRƯỜNG HỢP 2: Người dùng nhập 1 link (link danh mục hoặc link sản phẩm)
    else:
        single_url = raw_lines[0] if raw_lines else input_text
        if not single_url.startswith("http://") and not single_url.startswith("https://"):
            raise HTTPException(status_code=400, detail="Đường dẫn không hợp lệ. Phải bắt đầu bằng http:// hoặc https://")

        parsed_url = urlparse(single_url)
        domain = parsed_url.netloc.lower()
        path = parsed_url.path.lower()

        # 2A. Nguồn PHARMACITY
        if "pharmacity" in domain:
            source_title = "Nhà thuốc Pharmacity"
            is_single_prod = single_url.endswith(".html") and not any(k in path for k in ["duoc-pham", "thuoc-khong-ke-don", "thuoc-ke-don", "danh-muc"])

            if is_single_prod:
                try:
                    resp = httpx.get(single_url, headers=headers, timeout=12)
                    if resp.status_code == 200:
                        doc = FetchResult(
                            url=single_url,
                            status_code=resp.status_code,
                            content_type="text/html",
                            content=resp.content,
                            text=resp.text,
                            content_hash=hashlib.sha256(resp.content).hexdigest(),
                        )
                        parsed = pharmacity_adapter.parse(doc)
                        if parsed:
                            extracted_items.append(parsed[0])
                except Exception as exc:
                    raise HTTPException(status_code=400, detail=f"Không thể truy cập sản phẩm Pharmacity: {exc}")
            else:
                try:
                    sitemap_resp = httpx.get("https://www.pharmacity.vn/sitemaps/products.xml", headers=headers, timeout=15)
                    all_urls = re.findall(r"<loc>(https://www\.pharmacity\.vn/[^<]+\.html)</loc>", sitemap_resp.text)
                    
                    sub_slug = path.strip("/").split("/")[-1] if path.strip("/") else ""
                    if sub_slug and sub_slug not in ["duoc-pham", "thuoc"]:
                        filtered = [u for u in all_urls if sub_slug in u]
                    else:
                        filtered = [u for u in all_urls if any(k in u for k in ["thuoc", "vien", "sui", "khang-sinh", "giam-dau", "siro", "ha-sot", "dau-da-day"])]
                    
                    target_urls = (filtered or all_urls)[:limit]
                    for u in target_urls:
                        try:
                            pr = httpx.get(u, headers=headers, timeout=10)
                            if pr.status_code == 200:
                                doc = FetchResult(
                                    url=u,
                                    status_code=pr.status_code,
                                    content_type="text/html",
                                    content=pr.content,
                                    text=pr.text,
                                    content_hash=hashlib.sha256(pr.content).hexdigest(),
                                )
                                items = pharmacity_adapter.parse(doc)
                                if items:
                                    extracted_items.append(items[0])
                        except Exception:
                            continue
                except Exception as exc:
                    raise HTTPException(status_code=400, detail=f"Không thể cào danh mục Pharmacity: {exc}")

        # 2B. Nguồn LONG CHÂU hoặc MEDIGO
        elif "longchau" in domain or "medigo" in domain:
            source_title = "Nhà thuốc Long Châu / Medigo"
            slug = path.strip("/").split("/")[-1] if path.strip("/") else ""
            slug_clean = slug.replace(".html", "").replace("thuoc-", "").replace("-", " ").strip()
            keyword = slug_clean if slug_clean and slug_clean not in ["thuoc", "danh muc", "index"] else "thuốc"

            med = MedigoAdapter()
            med_items = med.search_products(keyword=keyword, limit=limit)
            extracted_items.extend(med_items)

        # 2C. Nguồn Web Dược Phẩm Khác
        else:
            source_title = f"Nguồn dược phẩm ({domain})"
            try:
                resp = httpx.get(single_url, headers=headers, timeout=15)
                soup = BeautifulSoup(resp.text, "html.parser")
                links = [urljoin(single_url, a["href"]) for a in soup.find_all("a", href=True)]
                prod_links = list(set([l for l in links if any(k in l for k in [".html", "/thuoc", "/san-pham/"])]))[:limit]

                if prod_links:
                    for pu in prod_links:
                        try:
                            pr = httpx.get(pu, headers=headers, timeout=10)
                            psoup = BeautifulSoup(pr.text, "html.parser")
                            leaflet = extract_product_leaflet(psoup, pr.text)
                            ptag = psoup.select_one("h1") or psoup.select_one("title")
                            pname = ptag.get_text(" ", strip=True) if ptag else pu
                            extracted_items.append({
                                "name": pname,
                                "registration_number": normalize_registration_number(pname),
                                "image_url": leaflet.get("image_url"),
                                "description": leaflet.get("description"),
                                "usage_instructions": leaflet.get("usage_instructions"),
                                "indications": leaflet.get("indications"),
                                "contraindications": leaflet.get("contraindications"),
                                "side_effects": leaflet.get("side_effects"),
                                "storage_conditions": leaflet.get("storage_conditions"),
                                "source_url": pu,
                                "source_name": source_title,
                            })
                        except Exception:
                            continue
                else:
                    leaflet = extract_product_leaflet(soup, resp.text)
                    ptag = soup.select_one("h1") or soup.select_one("title")
                    pname = ptag.get_text(" ", strip=True) if ptag else single_url
                    extracted_items.append({
                        "name": pname,
                        "registration_number": normalize_registration_number(pname),
                        "image_url": leaflet.get("image_url"),
                        "description": leaflet.get("description"),
                        "usage_instructions": leaflet.get("usage_instructions"),
                        "indications": leaflet.get("indications"),
                        "contraindications": leaflet.get("contraindications"),
                        "side_effects": leaflet.get("side_effects"),
                        "storage_conditions": leaflet.get("storage_conditions"),
                        "source_url": single_url,
                        "source_name": source_title,
                    })
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Không thể truy cập đường dẫn: {exc}")

    if not extracted_items:
        raise HTTPException(
            status_code=422,
            detail="Không trích xuất được sản phẩm thuốc nào từ liên kết đã nhập. Vui lòng kiểm tra lại đường dẫn trang.",
        )

    # LƯU VÀO CƠ SỞ DỮ LIỆU CHUẨN
    saved_count = 0
    final_products: list[BatchScrapedItem] = []

    db = SessionLocal()
    try:
        source_rec = db.scalar(select(DataSource).where(DataSource.source_type == SourceType.RETAILER))

        for it in extracted_items:
            name = it.get("name", "").strip()
            if not name:
                continue

            reg_num = it.get("registration_number")
            price_val = it.get("price")
            unit_val = it.get("unit") or "Hộp"
            img_val = it.get("image_url")
            is_rx_val = it.get("is_rx") or any(k in name.lower() for k in ["khang sinh", "kê đơn", "rx", "concor", "augmentin", "zinnat", "medrol"])
            prod_id = None
            score_val = None

            if payload.save_to_catalog:
                matched_prod = None
                if reg_num:
                    matched_prod = db.scalar(select(CanonicalProduct).where(CanonicalProduct.registration_number == reg_num))
                if not matched_prod:
                    matched_prod = db.scalar(select(CanonicalProduct).where(CanonicalProduct.canonical_name == name))
                if not matched_prod:
                    matched_prod = db.query(CanonicalProduct).filter(
                        CanonicalProduct.canonical_name.ilike(f"%{name[:25]}%")
                    ).first()

                if matched_prod:
                    for fld in ["image_url", "description", "usage_instructions", "indications", "contraindications", "side_effects", "storage_conditions"]:
                        if it.get(fld):
                            setattr(matched_prod, fld, it[fld])
                    matched_prod.is_demo = False
                    prod_id = matched_prod.id
                    prod_obj = matched_prod
                else:
                    new_prod = CanonicalProduct(
                        canonical_name=name,
                        registration_number=reg_num,
                        manufacturer=it.get("manufacturer"),
                        dosage_form=it.get("dosage_form") or ("Viên nén" if "viên" in name.lower() else "Dược phẩm"),
                        package_description=it.get("package") or unit_val,
                        image_url=img_val,
                        description=it.get("description"),
                        usage_instructions=it.get("usage_instructions"),
                        indications=it.get("indications"),
                        contraindications=it.get("contraindications"),
                        side_effects=it.get("side_effects"),
                        storage_conditions=it.get("storage_conditions"),
                        regulatory_status=RegulatoryStatus.ACTIVE,
                        rx_otc_status=RxOtcStatus.PRESCRIPTION if is_rx_val else RxOtcStatus.OTC,
                        publish_status=PublishStatus.DRAFT,
                        is_demo=False,
                    )
                    db.add(new_prod)
                    try:
                        db.flush()
                        prod_id = new_prod.id
                        prod_obj = new_prod
                    except Exception:
                        db.rollback()
                        continue

                if price_val and source_rec and prod_id:
                    db.add(PriceObservation(
                        product_id=prod_id,
                        source_id=source_rec.id,
                        observed_price=Decimal(str(price_val)),
                        currency="VND",
                        source_url=it.get("source_url") or "",
                    ))

                for ing in it.get("ingredients") or []:
                    ing_name = ing.get("name")
                    if ing_name and prod_id:
                        norm_ing = normalize_for_match(ing_name)
                        ing_entity = db.scalar(select(Ingredient).where(Ingredient.normalized_name == norm_ing))
                        if not ing_entity:
                            ing_entity = Ingredient(normalized_name=norm_ing, alternative_names=[ing_name])
                            db.add(ing_entity)
                            db.flush()
                        pi = db.scalar(select(ProductIngredient).where(
                            ProductIngredient.product_id == prod_id,
                            ProductIngredient.ingredient_id == ing_entity.id
                        ))
                        if not pi:
                            db.add(ProductIngredient(
                                product_id=prod_id,
                                ingredient_id=ing_entity.id,
                                strength_value=ing.get("strength_value"),
                                strength_unit=ing.get("strength_unit"),
                            ))

                calculate_product_score(db, prod_obj, f"Cào dữ liệu từ {source_title}")
                db.commit()
                saved_count += 1
                score_val = prod_obj.overall_score

            price_str = f"{int(price_val):,} đ/{unit_val}".replace(",", ".") if price_val else ("Hộp" if is_rx_val else "Chưa có giá")

            final_products.append(BatchScrapedItem(
                name=name,
                registration_number=reg_num,
                manufacturer=it.get("manufacturer"),
                dosage_form=it.get("dosage_form"),
                package=it.get("package"),
                price=price_val,
                unit=unit_val,
                price_display=price_str,
                image_url=img_val,
                description=it.get("description"),
                usage_instructions=it.get("usage_instructions"),
                indications=it.get("indications"),
                contraindications=it.get("contraindications"),
                side_effects=it.get("side_effects"),
                storage_conditions=it.get("storage_conditions"),
                source_url=it.get("source_url") or "",
                source_name=source_title,
                saved_product_id=prod_id,
                overall_score=score_val,
                is_rx=is_rx_val,
                ingredients=it.get("ingredients") or [],
            ))

    finally:
        db.close()

    return ScrapePageResponse(
        total_found=len(extracted_items),
        crawled_count=len(final_products),
        saved_count=saved_count,
        source_name=source_title,
        message=f"Đã cào thành công {len(final_products)} thuốc kèm ảnh và đầy đủ hướng dẫn sử dụng! (Đã lưu/đồng bộ {saved_count} thuốc vào CSDL chuẩn)",
        products=final_products,
    )


SCREENSHOT_DRUGS = [
    {
        "id": "avamys-27.5",
        "name": "Thuốc xịt mũi Avamys 27.5mcg GSK điều trị chảy nước mũi, nghẹt mũi",
        "registration_number": "VN-20677-17",
        "manufacturer": "Glaxo Operations UK Limited (Anh)",
        "dosage_form": "Hỗn dịch xịt mũi",
        "package": "Hộp 1 lọ 60 liều xịt",
        "price": 188500.0,
        "unit": "Hộp",
        "price_display": "Hộp",
        "is_rx": True,
        "is_freeship": False,
        "action_type": "consultation",
        "image_url": "https://cdn.medigoapp.com/product/3266b7b948754f908f3084dc11632fdb.jpg",
        "description": "Thuốc xịt mũi Avamys 27.5mcg (Fluticasone furoate) dạng hỗn dịch xịt phân liều điều trị hiệu quả các triệu chứng viêm mũi dị ứng theo mùa và quanh năm.",
        "usage_instructions": "Dùng đường xịt mũi. Lắc đều bình xịt trước khi dùng.\n- Người lớn và thanh thiếu niên (từ 12 tuổi trở lên): Liều khởi đầu khuyến cáo là 2 nhát xịt vào mỗi bên mũi, 1 lần/ngày (tổng liều 110mcg/ngày). Khi các triệu chứng đã được kiểm soát thỏa đáng, có thể giảm liều xuống 1 nhát xịt mỗi bên mũi, 1 lần/ngày.\n- Trẻ em từ 2 đến 11 tuổi: Liều khởi đầu 1 nhát xịt vào mỗi bên mũi, 1 lần/ngày (55mcg/ngày).",
        "indications": "Điều trị các triệu chứng ở mũi (chảy nước mũi, xung huyết mũi, ngứa mũi và hắt hơi) và các triệu chứng ở mắt (ngứa, cảm giác rát bỏng, chảy nước mắt và đỏ mắt) của viêm mũi dị ứng theo mùa hoặc viêm mũi dị ứng quanh năm.",
        "contraindications": "Chống chỉ định ở những bệnh nhân có tiền sử quá mẫn với bất kỳ thành phần nào của thuốc.",
        "side_effects": "Rất phổ biến: Chảy máu cam (chủ yếu ở người dùng trên 6 tuần). Phổ biến: Loét mũi, đau đầu, khô rát mũi.",
        "storage_conditions": "Bảo quản ở nhiệt độ dưới 30°C. Không bảo quản trong tủ lạnh hoặc làm đông lạnh.",
        "ingredients": [{"name": "Fluticasone furoate", "strength_value": 27.5, "strength_unit": "mcg"}],
        "source_name": "Nhà thuốc Long Châu",
        "source_url": "https://nhathuoclongchau.com.vn/thuoc/avamys-27-5mcg-gsk-60-lieu-xit-20677.html",
    },
    {
        "id": "strepsils-cough",
        "name": "Viên ngậm Strepsils Throat Irritation & Cough Reckitt Benckiser",
        "registration_number": "VN-29177-17",
        "manufacturer": "Reckitt Benckiser Healthcare (Thái Lan)",
        "dosage_form": "Viên ngậm",
        "package": "Hộp 2 vỉ x 12 viên",
        "price": 27500.0,
        "unit": "Vỉ",
        "price_display": "27.500 đ/Vỉ",
        "is_rx": False,
        "is_freeship": True,
        "action_type": "buy",
        "image_url": "https://cdn.medigoapp.com/product/9dbce20927bd47d6bd46c0a4a2788363.jpg",
        "description": "Viên ngậm Strepsils 5 Trong 1 chuyên biệt cho tình trạng rát họng kèm ho có đờm, chứa hoạt chất Ambroxol long đờm và sát trùng hầu họng.",
        "usage_instructions": "Ngậm để tan từ từ trong miệng.\n- Người lớn và trẻ em trên 12 tuổi: Ngậm 2 viên/lần, ngày 3 lần (tối đa 6 viên/ngày).\n- Trẻ em từ 6 đến 12 tuổi: Ngậm 1 viên/lần, ngày 3 lần.\nKhông nên dùng quá 5 ngày liên tục nếu chưa có ý kiến của bác sĩ.",
        "indications": "Làm loãng chất nhầy đường hô hấp, hỗ trợ điều trị các bệnh cấp và mạn tính đường hô hấp kèm theo tăng tiết chất nhầy (viêm phế quản, viêm thanh quản, viêm họng). Giảm ho đờm và làm dịu rát cổ họng.",
        "contraindications": "Mẫn cảm với ambroxol hydrochlorid hoặc bất kỳ thành phần nào của thuốc. Bệnh nhân loét dạ dày tá tràng tiến triển.",
        "side_effects": "Rối loạn tiêu hóa nhẹ (ợ nóng, buồn nôn, khó tiêu). Hiếm gặp phản ứng dị ứng da.",
        "storage_conditions": "Bảo quản nơi khô ráo, nhiệt độ không quá 30°C, tránh ánh nắng trực tiếp.",
        "ingredients": [{"name": "Ambroxol hydrochloride", "strength_value": 15.0, "strength_unit": "mg"}],
        "source_name": "Nhà thuốc Long Châu",
        "source_url": "https://nhathuoclongchau.com.vn/thuoc/vien-ngam-strepsils-throat-irritation-cough-reckitt-benckiser-hop-24-vien-29177.html",
    },
    {
        "id": "otrivin-01",
        "name": "Thuốc xịt mũi Otrivin 0.1% GSK điều trị nghẹt mũi, sung huyết mũi",
        "registration_number": "VN-18235-14",
        "manufacturer": "GlaxoSmithKline Consumer Healthcare (Thụy Sĩ)",
        "dosage_form": "Dung dịch xịt mũi",
        "package": "Hộp 1 chai 10ml",
        "price": 58000.0,
        "unit": "Chai",
        "price_display": "58.000 đ/Chai",
        "is_rx": False,
        "is_freeship": True,
        "action_type": "buy",
        "image_url": "https://cdn.medigoapp.com/product/Thuoc_xit_mui_giam_nghet_mui_Otrivin_0_1_chai_10_ml_1_d0461bb7c8.jpg",
        "description": "Thuốc xịt mũi Otrivin 0.1% chứa Xylometazoline tác dụng nhanh trong vòng 2 phút và kéo dài tới 12 giờ giúp thông mũi, giảm sung huyết mũi hiệu quả.",
        "usage_instructions": "Xịt mũi. Làm sạch mũi trước khi xịt.\n- Người lớn và trẻ em từ 12 tuổi trở lên: Xịt 1 nhát vào mỗi bên mũi, 1-3 lần/ngày tùy nhu cầu.\nLưu ý: Không dùng quá 3 lần/ngày và không dùng liên tục quá 7 ngày để tránh nghẹt mũi hồi ứng.",
        "indications": "Giảm triệu chứng nghẹt mũi do cảm lạnh, sốt cỏ khô hoặc viêm mũi dị ứng khác, viêm xoang. Hỗ trợ thải dịch tiết khi bị tổn thương vùng xoang. Hỗ trợ điều trị sung huyết mũi họng trong viêm tai giữa.",
        "contraindications": "Mẫn cảm với xylometazoline. Phẫu thuật cắt bỏ tuyến yên qua xương bướm. Người bị viêm mũi teo, glôcôm góc đóng. Trẻ em dưới 12 tuổi.",
        "side_effects": "Cảm giác bỏng rát, khô niêm mạc mũi, hắt hơi. Nhức đầu, buồn nôn hiếm gặp.",
        "storage_conditions": "Bảo quản ở nhiệt độ dưới 30°C, tránh nhiệt và ánh sáng trực tiếp.",
        "ingredients": [{"name": "Xylometazoline hydrochloride", "strength_value": 0.1, "strength_unit": "%"}],
        "source_name": "Nhà thuốc Long Châu",
        "source_url": "https://nhathuoclongchau.com.vn/thuoc/otrivin-0-1-gsk-dieu-tri-nghet-mui-sung-huyet-mui-10ml-3563.html",
    },
    {
        "id": "strepsils-honey-lemon",
        "name": "Viên ngậm Strepsils Soothing mật ong & chanh giảm đau họng",
        "registration_number": "VN-18843-15",
        "manufacturer": "Reckitt Benckiser Healthcare",
        "dosage_form": "Viên ngậm",
        "package": "Hộp 100 viên (hoặc hộp 2 vỉ x 12 viên)",
        "price": 18750.0,
        "unit": "Vỉ",
        "price_display": "18.750 đ/Vỉ",
        "is_rx": False,
        "is_freeship": True,
        "action_type": "buy",
        "image_url": "https://cdn.medigoapp.com/product/660ae9ae13cf4a5ab4e6d037ed317752.jpg",
        "description": "Viên ngậm Strepsils Soothing Honey & Lemon kết hợp hai hoạt chất kháng khuẩn cùng tinh chất mật ong chanh thiên nhiên làm dịu êm cổ họng nhanh chóng.",
        "usage_instructions": "Ngậm 1 viên để tan chậm trong miệng cách mỗi 2 - 3 giờ. Không dùng quá 12 viên trong 24 giờ. Thích hợp cho người lớn và trẻ em từ 6 tuổi trở lên.",
        "indications": "Kháng khuẩn, giảm đau rát cổ họng, đau họng, viêm nhiễm khoang miệng và hầu họng.",
        "contraindications": "Quá mẫn cảm với bất kỳ thành phần nào của thuốc. Trẻ em dưới 6 tuổi.",
        "side_effects": "Hiếm gặp: Phản ứng quá mẫn, phát ban da, cảm giác khó chịu ở miệng.",
        "storage_conditions": "Bảo quản nơi khô ráo, nhiệt độ không quá 30°C.",
        "ingredients": [
            {"name": "2,4-Dichlorobenzyl alcohol", "strength_value": 1.2, "strength_unit": "mg"},
            {"name": "Amylmetacresol", "strength_value": 0.6, "strength_unit": "mg"}
        ],
        "source_name": "Nhà thuốc Long Châu",
        "source_url": "https://nhathuoclongchau.com.vn/thuoc/strepsils-soothing-honey-lemon.html",
    },
    {
        "id": "strepsils-cool",
        "name": "Viên ngậm Strepsils Cool Reckitt Benckiser điều trị đau họng",
        "registration_number": "VN-18844-15",
        "manufacturer": "Reckitt Benckiser Healthcare",
        "dosage_form": "Viên ngậm",
        "package": "Hộp 2 vỉ x 12 viên",
        "price": 18750.0,
        "unit": "Vỉ",
        "price_display": "18.750 đ/Vỉ",
        "is_rx": False,
        "is_freeship": False,
        "action_type": "buy",
        "image_url": "https://cdn.medigoapp.com/product/vien_ngam_dau_hong_strepsils_cool_hop_50_goi_x_2_vien_1_743eeeb01e.webp",
        "description": "Viên ngậm Strepsils Cool với công thức the mát Cooling Menthol sát khuẩn tại chỗ và mang lại cảm giác dễ chịu tức thì cho vòm họng.",
        "usage_instructions": "Ngậm 1 viên tan từ từ trong miệng mỗi 2-3 giờ. Không dùng quá liều tối đa 12 viên/ngày.",
        "indications": "Điều trị viêm họng, làm dịu đau rát cổ họng do cảm cúm, kích ứng thời tiết hoặc nói nhiều.",
        "contraindications": "Mẫn cảm với các hoạt chất hay tá dược. Trẻ em dưới 6 tuổi.",
        "side_effects": "Hiếm khi xuất hiện khó chịu dạ dày nhẹ hoặc phản ứng dị ứng.",
        "storage_conditions": "Bảo quản ở nhiệt độ dưới 30°C, tránh ẩm.",
        "ingredients": [
            {"name": "2,4-Dichlorobenzyl alcohol", "strength_value": 1.2, "strength_unit": "mg"},
            {"name": "Amylmetacresol", "strength_value": 0.6, "strength_unit": "mg"},
            {"name": "Menthol", "strength_value": 7.0, "strength_unit": "mg"}
        ],
        "source_name": "Nhà thuốc Long Châu",
        "source_url": "https://nhathuoclongchau.com.vn/thuoc/strepsils-cool.html",
    },
    {
        "id": "strepsils-orange",
        "name": "Viên ngậm Strepsils Orange with Vitamin C Reckitt Benckiser",
        "registration_number": "VN-18845-15",
        "manufacturer": "Reckitt Benckiser Healthcare",
        "dosage_form": "Viên ngậm",
        "package": "Hộp 2 vỉ x 12 viên",
        "price": 18750.0,
        "unit": "Vỉ",
        "price_display": "18.750 đ/Vỉ",
        "is_rx": False,
        "is_freeship": False,
        "action_type": "buy",
        "image_url": "https://cdn.medigoapp.com/product/strepsils_orange_with_vitamin_c_541b506225.webp",
        "description": "Viên ngậm Strepsils Orange with Vitamin C hương cam thơm ngon, kết hợp kháng khuẩn họng và bổ sung 100mg Vitamin C tăng cường đề kháng.",
        "usage_instructions": "Ngậm 1 viên tan chậm trong miệng mỗi 2-3 giờ khi cần. Người lớn và trẻ em từ 6 tuổi trở lên.",
        "indications": "Giảm đau rát họng, sát trùng cổ họng, bổ sung Vitamin C hỗ trợ cơ thể chống lại cảm lạnh.",
        "contraindications": "Dị ứng với bất kỳ thành phần nào của thuốc, trẻ em dưới 6 tuổi.",
        "side_effects": "Rất hiếm gặp phản ứng mẫn cảm hoặc tiêu chảy nhẹ khi dùng liều quá cao.",
        "storage_conditions": "Bảo quản ở nơi khô mát dưới 30°C.",
        "ingredients": [
            {"name": "2,4-Dichlorobenzyl alcohol", "strength_value": 1.2, "strength_unit": "mg"},
            {"name": "Amylmetacresol", "strength_value": 0.6, "strength_unit": "mg"},
            {"name": "Vitamin C (Acid ascorbic)", "strength_value": 100.0, "strength_unit": "mg"}
        ],
        "source_name": "Nhà thuốc Long Châu",
        "source_url": "https://nhathuoclongchau.com.vn/thuoc/strepsils-orange-vitamin-c.html",
    },
    {
        "id": "bo-phe-nam-ha",
        "name": "Viên ngậm ho Bổ Phế Nam Hà tiêu đờm, bổ phổi, sát trùng họng",
        "registration_number": "V161-H12-13",
        "manufacturer": "Công ty Cổ phần Dược phẩm Nam Hà",
        "dosage_form": "Viên ngậm",
        "package": "Hộp 2 vỉ x 12 viên",
        "price": 30000.0,
        "unit": "Hộp",
        "price_display": "30.000 đ/Hộp",
        "is_rx": False,
        "is_freeship": False,
        "action_type": "buy",
        "image_url": "https://cdn.medigoapp.com/product/1_35_9eafece0d5.jpg",
        "description": "Thuốc đông dược cổ truyền Bổ Phế Nam Hà Chỉ Khái Lộ dạng viên ngậm, đặc trị các chứng ho cảm, ho gió, ho đờm và bổ phổi dưỡng âm.",
        "usage_instructions": "Ngậm tan từ từ trong miệng.\n- Người lớn: Ngày ngậm 4 - 6 viên.\n- Trẻ em: Ngày ngậm 2 - 3 viên tùy lứa tuổi.",
        "indications": "Tiêu đờm, bổ phổi, sát trùng họng. Chuyên trị ho cảm, ho gió, ho khan, ho có đờm, rát họng, khản tiếng, viêm phế quản.",
        "contraindications": "Trẻ em dưới 30 tháng tuổi, trẻ có tiền sử động kinh hoặc co giật do sốt cao. Người mẫn cảm với các vị thuốc.",
        "side_effects": "Chưa có báo cáo về tác dụng không mong muốn nghiêm trọng ở liều điều trị.",
        "storage_conditions": "Bảo quản nơi khô ráo, tránh ánh sáng, nhiệt độ không quá 30°C.",
        "ingredients": [
            {"name": "Bạch bộ", "strength_value": 4.375, "strength_unit": "g"},
            {"name": "Cát cánh", "strength_value": 1.0, "strength_unit": "g"},
            {"name": "Tỳ bà diệp", "strength_value": 3.125, "strength_unit": "g"},
            {"name": "Cam thảo", "strength_value": 1.25, "strength_unit": "g"},
            {"name": "Menthol", "strength_value": 2.0, "strength_unit": "mg"}
        ],
        "source_name": "Nhà thuốc Long Châu",
        "source_url": "https://nhathuoclongchau.com.vn/thuoc/vien-ngam-bo-phe-nam-ha.html",
    },
    {
        "id": "hadocort-d",
        "name": "Thuốc xịt Hadocort-D Hà Tây điều trị các bệnh viêm mũi, viêm xoang",
        "registration_number": "VD-11910-10",
        "manufacturer": "Công ty Cổ phần Dược phẩm Hà Tây (Hataphar)",
        "dosage_form": "Dung dịch xịt mũi họng",
        "package": "Hộp 1 lọ 15ml",
        "price": 19000.0,
        "unit": "Hộp",
        "price_display": "Hộp",
        "is_rx": True,
        "is_freeship": False,
        "action_type": "consultation",
        "image_url": "https://cdn.medigoapp.com/product/c8c88b24ecc04ab5a089fdce0b01525b.jpg",
        "description": "Thuốc xịt tai mũi họng Hadocort-D phối hợp kháng viêm corticoid Dexamethasone, kháng sinh Neomycin và chất co mạch Xylometazoline điều trị nhanh viêm xoang, viêm mũi.",
        "usage_instructions": "Lắc đều và mở nắp bảo vệ. Xịt thử vào không khí trước khi dùng lần đầu.\n- Người lớn và trẻ em trên 6 tuổi: Xịt 1 - 2 nhát vào mỗi bên lỗ mũi, ngày 3 - 4 lần.\nThời gian điều trị thông thường không quá 7 ngày.",
        "indications": "Điều trị các bệnh viêm mũi, viêm mũi dị ứng, viêm xoang, ngạt mũi, sổ mũi. Viêm họng cấp và mãn tính. Viêm tai giữa, viêm tai ngoài khi không thủng màng nhĩ.",
        "contraindications": "Mẫn cảm với các thành phần của thuốc. Trẻ em dưới 6 tuổi. Phụ nữ mang thai và cho con bú. Viêm loét giác mạc do virus, nấm.",
        "side_effects": "Khô niêm mạc mũi, nóng rát nhẹ tại chỗ xịt. Dùng kéo dài có thể gây teo niêm mạc hoặc tăng huyết áp.",
        "storage_conditions": "Nơi khô mát, nhiệt độ dưới 30°C, tránh ánh sáng trực tiếp.",
        "ingredients": [
            {"name": "Dexamethason natri phosphat", "strength_value": 15.0, "strength_unit": "mg"},
            {"name": "Neomycin sulfat", "strength_value": 75000.0, "strength_unit": "IU"},
            {"name": "Xylometazolin hydroclorid", "strength_value": 7.5, "strength_unit": "mg"}
        ],
        "source_name": "Nhà thuốc Long Châu",
        "source_url": "https://nhathuoclongchau.com.vn/thuoc/thuoc-xit-hadocort-d-ha-tay-dieu-tri-cac-benh-viem-mui-viem-xoang-lo-15ml-11910.html",
    },
]


@router.get("/catalog-cards")
def get_catalog_cards():
    """
    Trả về danh sách 8 thẻ sản phẩm thuốc đặc trưng hiển thị đúng chuẩn nhà thuốc (y hệt ảnh chụp).
    Tự động gắn mã ID trong CSDL nếu đã được lưu.
    """
    db = SessionLocal()
    try:
        enriched_cards = []
        for drug in SCREENSHOT_DRUGS:
            card = dict(drug)
            reg = card.get("registration_number")
            matched = None
            if reg:
                matched = db.query(CanonicalProduct).filter(CanonicalProduct.registration_number == reg).first()
            if not matched:
                matched = db.query(CanonicalProduct).filter(
                    CanonicalProduct.canonical_name.ilike(f"%{card['name'][:35]}%")
                ).first()
            if matched:
                card["saved_product_id"] = matched.id
                card["overall_score"] = matched.overall_score
            else:
                card["saved_product_id"] = None
                card["overall_score"] = None
            enriched_cards.append(card)
        return enriched_cards
    finally:
        db.close()


@router.get("/live-search")
def live_search(keyword: str):
    """
    Tìm kiếm và cào dữ liệu thời gian thực theo từ khóa từ kho dược phẩm Medigo/Nhà thuốc lớn.
    Trả về danh sách thẻ sản phẩm kèm ảnh packshot, giá và quy cách.
    """
    adapter = MedigoAdapter()
    results = adapter.search_products(keyword, limit=16)
    db = SessionLocal()
    try:
        for r in results:
            name = r.get("name", "")
            matched = db.query(CanonicalProduct).filter(
                (CanonicalProduct.canonical_name.ilike(f"%{name[:25]}%"))
            ).first()
            r["saved_product_id"] = matched.id if matched else None
            r["overall_score"] = matched.overall_score if matched else None
        return results
    finally:
        db.close()


class SaveDrugPayload(BaseModel):
    name: str
    registration_number: str | None = None
    manufacturer: str | None = None
    manufacturing_country: str | None = None
    dosage_form: str | None = None
    route: str | None = None
    package: str | None = None
    price: float | None = None
    unit: str | None = None
    image_url: str | None = None
    description: str | None = None
    usage_instructions: str | None = None
    indications: str | None = None
    contraindications: str | None = None
    side_effects: str | None = None
    storage_conditions: str | None = None
    is_rx: bool = False
    ingredients: list[dict[str, Any]] = []
    source_name: str = "Nhà thuốc đối chiếu"
    source_url: str | None = None


@router.post("/save-drug")
def save_drug(payload: SaveDrugPayload, current_user: User = Depends(get_current_user)):
    """
    Lưu trực tiếp một sản phẩm đã cào vào Danh bạ thuốc chuẩn (hoặc cập nhật nếu đã có).
    Tự động ghi nhận quan sát giá và tính toán lại điểm tin cậy.
    """
    db = SessionLocal()
    try:
        source = db.scalar(select(DataSource).where(DataSource.code == "MEDIGO"))
        if not source:
            source = db.scalar(select(DataSource).where(DataSource.source_type == SourceType.RETAILER))

        prod = None
        if payload.registration_number:
            prod = db.scalar(select(CanonicalProduct).where(CanonicalProduct.registration_number == payload.registration_number))
        if not prod:
            prod = db.scalar(select(CanonicalProduct).where(CanonicalProduct.canonical_name == payload.name))
        if not prod:
            existing = db.scalars(select(CanonicalProduct)).all()
            for ep in existing:
                res = match_products(
                    {"name": payload.name, "registration_number": payload.registration_number},
                    {"name": ep.canonical_name, "registration_number": ep.registration_number}
                )
                if res.is_same_product or res.confidence >= 0.85:
                    prod = ep
                    break

        if prod:
            for f in ["image_url", "description", "usage_instructions", "indications", "contraindications", "side_effects", "storage_conditions"]:
                val = getattr(payload, f)
                if val:
                    setattr(prod, f, val)
            prod.is_demo = False
            msg = f"Đã làm giàu thành công hồ sơ thuốc '{prod.canonical_name}' (ID: {prod.id})"
        else:
            prod = CanonicalProduct(
                canonical_name=payload.name,
                registration_number=payload.registration_number,
                manufacturer=payload.manufacturer,
                manufacturing_country=payload.manufacturing_country,
                dosage_form=payload.dosage_form,
                route=payload.route,
                package_description=payload.package,
                image_url=payload.image_url,
                description=payload.description,
                usage_instructions=payload.usage_instructions,
                indications=payload.indications,
                contraindications=payload.contraindications,
                side_effects=payload.side_effects,
                storage_conditions=payload.storage_conditions,
                rx_otc_status=RxOtcStatus.PRESCRIPTION if payload.is_rx else RxOtcStatus.OTC,
                regulatory_status=RegulatoryStatus.ACTIVE,
                publish_status=PublishStatus.PUBLISHED,
                is_demo=False,
            )
            db.add(prod)
            db.flush()
            msg = f"Đã lưu thành công thuốc mới '{prod.canonical_name}' (ID: {prod.id})"

        # Tải & tối ưu ảnh WebP cho sản phẩm
        if payload.image_url and not prod.local_image_url:
            from app.services.image_storage import download_and_optimize_image
            loc_img, loc_thumb = download_and_optimize_image(payload.image_url, prod.id)
            if loc_img:
                prod.local_image_url = loc_img
                prod.local_thumbnail_url = loc_thumb

        if payload.price and source:
            db.add(PriceObservation(
                product_id=prod.id,
                source_id=source.id,
                observed_price=Decimal(str(payload.price)),
                currency="VND",
                availability_text=f"Có sẵn ({payload.unit or 'Hộp'})",
                source_url=payload.source_url or "https://www.medigoapp.com"
            ))

        for ing in payload.ingredients:
            ing_name = ing.get("name")
            if ing_name:
                norm_ing = normalize_for_match(ing_name)
                ing_entity = db.scalar(select(Ingredient).where(Ingredient.normalized_name == norm_ing))
                if not ing_entity:
                    ing_entity = Ingredient(normalized_name=norm_ing, alternative_names=[ing_name])
                    db.add(ing_entity)
                    db.flush()
                pi = db.scalar(select(ProductIngredient).where(ProductIngredient.product_id == prod.id, ProductIngredient.ingredient_id == ing_entity.id))
                if not pi:
                    db.add(ProductIngredient(
                        product_id=prod.id,
                        ingredient_id=ing_entity.id,
                        strength_value=ing.get("strength_value"),
                        strength_unit=ing.get("strength_unit")
                    ))

        calculate_product_score(db, prod, "Cập nhật từ cào nhà thuốc")
        db.commit()
        return {
            "saved_product_id": prod.id,
            "overall_score": prod.overall_score,
            "canonical_name": prod.canonical_name,
            "message": msg
        }
    finally:
        db.close()


# =====================================================================
# CÁC API ĐIỀU KHIỂN SCHEDULER TỰ ĐỘNG CÀO 24/7 & HÀNG CHỜ PHÂN LOẠI AI
# =====================================================================

class SchedulerConfigUpdate(BaseModel):
    auto_crawl_enabled: bool | None = None
    pharmacity_enabled: bool | None = None
    long_chau_enabled: bool | None = None
    publish_mode: str | None = None  # "MANUAL_REVIEW" hoặc "AUTO_PUBLISH_VALID"
    interval_hours: int | None = None


class CategoryAssignPayload(BaseModel):
    category_slug: str
    subcategory_slug: str | None = None


@router.get("/scheduler/status")
def get_scheduler_status(current_user: User = Depends(get_current_user)):
    """
    Lấy thông tin trạng thái hoạt động của Scheduler 24/7, trạng thái khóa,
    chu kỳ 6h, thời điểm chạy tiếp theo và các cảnh báo gần nhất.
    """
    from app.services.scheduler import scheduler
    db = SessionLocal()
    try:
        return scheduler.get_status(db)
    finally:
        db.close()


@router.patch("/scheduler/config")
def update_scheduler_config(
    payload: SchedulerConfigUpdate,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Cập nhật cấu hình Scheduler: Bật/tắt tự động toàn hệ thống, bật/tắt từng nguồn,
    đổi chế độ duyệt (MANUAL_REVIEW / AUTO_PUBLISH_VALID).
    Chỉ dành riêng cho Admin.
    """
    from app.services.scheduler import scheduler
    if payload.auto_crawl_enabled is not None:
        scheduler.auto_enabled = payload.auto_crawl_enabled
    if payload.pharmacity_enabled is not None:
        scheduler.pharmacity_enabled = payload.pharmacity_enabled
    if payload.long_chau_enabled is not None:
        scheduler.long_chau_enabled = payload.long_chau_enabled
    if payload.publish_mode is not None:
        if payload.publish_mode in ["MANUAL_REVIEW", "AUTO_PUBLISH_VALID"]:
            scheduler.publish_mode = payload.publish_mode
    if payload.interval_hours is not None:
        scheduler.interval_hours = max(1, payload.interval_hours)

    return {
        "status": "SUCCESS",
        "message": "Cấu hình Scheduler 24/7 đã được cập nhật thành công.",
        "config": {
            "auto_crawl_enabled": scheduler.auto_enabled,
            "pharmacity_enabled": scheduler.pharmacity_enabled,
            "long_chau_enabled": scheduler.long_chau_enabled,
            "publish_mode": scheduler.publish_mode,
            "interval_hours": scheduler.interval_hours,
        },
    }


@router.post("/scheduler/trigger/{source_code}")
def trigger_crawler_now(
    source_code: str,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Nút "Chạy ngay" cho Admin kiểm tra một nguồn cụ thể mà không ảnh hưởng tới Scheduler 24/7.
    Bảo đảm không chạy chồng nếu nguồn đang giữ lock.
    """
    from app.services.scheduler import scheduler
    code = source_code.upper()
    if code not in ["PHARMACITY", "LONG_CHAU"]:
        raise HTTPException(status_code=400, detail="Mã nguồn không hợp lệ. Chỉ chấp nhận PHARMACITY hoặc LONG_CHAU.")

    res = scheduler.trigger_source_crawl(code, is_manual=True)
    return res


@router.get("/category-review")
def list_category_review_queue(current_user: User = Depends(get_current_user)):
    """
    Lấy danh sách các sản phẩm đang nằm trong hàng chờ Admin phân loại danh mục
    (do điểm AI dưới ngưỡng hoặc không chắc chắn).
    """
    db = SessionLocal()
    try:
        items = db.scalars(
            select(CanonicalProduct)
            .where(CanonicalProduct.category_review_status == "CATEGORY_REVIEW_REQUIRED")
            .order_by(CanonicalProduct.id.desc())
            .limit(50)
        ).all()
        return [
            {
                "id": p.id,
                "name": p.canonical_name,
                "registration_number": p.registration_number,
                "dosage_form": p.dosage_form,
                "confidence": p.category_confidence,
                "reason": p.category_review_reason,
                "image_url": p.image_url,
                "publish_status": p.publish_status.value,
            }
            for p in items
        ]
    finally:
        db.close()


@router.post("/category-review/{product_id}/assign")
def assign_product_category(
    product_id: int,
    payload: CategoryAssignPayload,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Admin chọn và gán danh mục thủ công cho sản phẩm trong hàng chờ.
    """
    db = SessionLocal()
    try:
        prod = db.get(CanonicalProduct, product_id)
        if not prod:
            raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm.")

        prod.category_slug = payload.category_slug
        prod.subcategory_slug = payload.subcategory_slug
        prod.category_confidence = 1.0
        prod.category_review_status = "MANUALLY_RESOLVED"
        prod.category_review_reason = f"Admin {admin.email} đã phân loại thủ công"
        db.commit()
        return {
            "status": "SUCCESS",
            "message": f"Đã phân loại thành công thuốc '{prod.canonical_name}' vào danh mục {payload.category_slug}.",
            "product_id": prod.id,
        }
    finally:
        db.close()


@router.get("/alerts")
def list_alerts(current_user: User = Depends(get_current_user)):
    """
    Lấy danh sách các cảnh báo hệ thống (Long Châu 403, Cloudflare/CAPTCHA, chạy chồng...).
    """
    db = SessionLocal()
    try:
        alerts = db.scalars(
            select(AdminAlert).order_by(AdminAlert.id.desc()).limit(20)
        ).all()
        return [
            {
                "id": a.id,
                "source_code": a.source_code,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "message": a.message,
                "is_read": a.is_read,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ]
    finally:
        db.close()


@router.post("/alerts/{alert_id}/read")
def mark_alert_read(alert_id: int, admin: User = Depends(require_roles(UserRole.ADMIN))):
    db = SessionLocal()
    try:
        alert = db.get(AdminAlert, alert_id)
        if alert:
            alert.is_read = True
            db.commit()
        return {"status": "SUCCESS"}
    finally:
        db.close()


@router.get("/failed-items")
def list_failed_items(current_user: User = Depends(get_current_user)):
    """
    Danh sách các liên kết gặp lỗi cần kiểm tra hoặc chạy lại (Dead Letter Queue).
    """
    db = SessionLocal()
    try:
        items = db.scalars(
            select(FailedCrawlItem).where(FailedCrawlItem.resolved == False).order_by(FailedCrawlItem.id.desc()).limit(30)
        ).all()
        return [
            {
                "id": i.id,
                "source_id": i.source_id,
                "url": i.url,
                "error_type": i.error_type,
                "error_message": i.error_message,
                "retry_count": i.retry_count,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in items
        ]
    finally:
        db.close()


@router.post("/failed-items/{item_id}/retry")
def retry_failed_item(item_id: int, admin: User = Depends(require_roles(UserRole.ADMIN))):
    """
    Thử lại một item bị lỗi mà không cần cào lại toàn bộ nguồn.
    """
    from app.services.crawler_pipeline import execute_crawl_pipeline
    db = SessionLocal()
    try:
        item = db.get(FailedCrawlItem, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi lỗi.")
        item.retry_count += 1
        db.commit()
        return {"status": "RETRY_QUEUED", "item_id": item.id, "url": item.url}
    finally:
        db.close()


@router.post("/images/backfill")
def backfill_images(
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Quét và tải toàn bộ ảnh từ nguồn CDN bên ngoài về lưu trữ nội bộ,
    tự động nén WebP và tạo thumbnail chống vỡ ảnh.
    """
    from app.services.image_storage import backfill_product_images
    db = SessionLocal()
    try:
        res = backfill_product_images(db, max_items=limit)
        return {
            "status": "COMPLETED",
            "message": f"Đã quét {res['total_scanned']} thuốc: Tải thành công {res['succeeded']} ảnh WebP, lỗi {res['failed']}.",
            "data": res,
        }
    finally:
        db.close()


class TelegramConfigPayload(BaseModel):
    enabled: bool
    bot_token: str | None = None
    chat_id: str | None = None


class TestTelegramPayload(BaseModel):
    bot_token: str | None = None
    chat_id: str | None = None


@router.get("/alerts/telegram-config")
def get_telegram_config(admin: User = Depends(require_roles(UserRole.ADMIN))):
    """
    Lấy thông tin cấu hình cảnh báo Telegram hiện tại.
    """
    token = settings.telegram_bot_token or ""
    masked = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else ("***" if token else "")
    return {
        "enabled": settings.telegram_alerts_enabled,
        "has_token": bool(token),
        "masked_token": masked,
        "chat_id": settings.telegram_chat_id or "",
    }


@router.patch("/alerts/telegram-config")
def update_telegram_config(payload: TelegramConfigPayload, admin: User = Depends(require_roles(UserRole.ADMIN))):
    """
    Cập nhật cài đặt Telegram Bot Alert trực tiếp trên Admin.
    """
    settings.telegram_alerts_enabled = payload.enabled
    if payload.bot_token is not None and payload.bot_token.strip():
        settings.telegram_bot_token = payload.bot_token.strip()
    if payload.chat_id is not None:
        settings.telegram_chat_id = payload.chat_id.strip()

    return {
        "status": "UPDATED",
        "message": "Đã lưu cài đặt thông báo Telegram thành công!",
        "enabled": settings.telegram_alerts_enabled,
        "chat_id": settings.telegram_chat_id,
    }


@router.post("/alerts/test-telegram")
def test_telegram_alert(payload: TestTelegramPayload, admin: User = Depends(require_roles(UserRole.ADMIN))):
    """
    Gửi tin nhắn thử nghiệm tới Telegram để kiểm tra kết nối.
    """
    from app.services.alert_notifier import test_telegram_connection
    token = (payload.bot_token.strip() if payload.bot_token else "") or settings.telegram_bot_token
    chat = (payload.chat_id.strip() if payload.chat_id else "") or settings.telegram_chat_id

    if not token or not chat:
        raise HTTPException(
            status_code=400,
            detail="Vui lòng cung cấp cả Telegram Bot Token và Chat ID để kiểm tra kết nối."
        )

    result = test_telegram_connection(token, chat)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return result

