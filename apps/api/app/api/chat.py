import re
import unicodedata
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import CanonicalProduct, PriceObservation
from app.models.enums import PublishStatus, RxOtcStatus

router = APIRouter(prefix="/chat", tags=["AI Chatbot Tư Vấn Dược Sĩ"])


class ChatMessageSchema(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=2000)


class ChatRequestSchema(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_history: List[ChatMessageSchema] = Field(default_factory=list)


class RecommendedProductSchema(BaseModel):
    id: str
    name: str
    slug: str
    brand: str
    category_name: str
    price: int
    sale_price: Optional[int] = None
    image: str
    active_ingredient: str
    dosage_form: str
    stock: int
    is_prescription: bool
    short_description: str


class ChatResponseSchema(BaseModel):
    reply: str
    recommended_products: List[RecommendedProductSchema] = Field(default_factory=list)
    safety_alert: Optional[dict[str, Any]] = None
    quick_replies: List[str] = Field(default_factory=list)
    provider_used: str = "fastapi_h4care_expert"


ENTITY_MAP = {
    "aacute": "á", "agrave": "à", "atilde": "ã", "acirc": "â",
    "eacute": "é", "egrave": "è", "ecirc": "ê",
    "iacute": "í", "igrave": "ì",
    "oacute": "ó", "ograve": "ò", "otilde": "õ", "ocirc": "ô",
    "uacute": "ú", "ugrave": "ù",
    "yacute": "ý",
    "deg": "°", "ndash": "-", "mdash": "—", "hellip": "...",
    "nbsp": " ", "quot": '"', "amp": "&", "lt": "<", "gt": ">",
}


def remove_vietnamese_tones(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    return text.lower().strip()


def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    s = str(text)
    s = re.sub(r"\\?u003c", "<", s, flags=re.IGNORECASE)
    s = re.sub(r"\\?u003e", ">", s, flags=re.IGNORECASE)
    s = re.sub(r"\\?u0022", '"', s, flags=re.IGNORECASE)
    s = re.sub(r"\\?u0027", "'", s, flags=re.IGNORECASE)
    s = re.sub(r"\\?u002f", "/", s, flags=re.IGNORECASE)

    def decode_entity(match):
        ent = match.group(1).lower()
        return ENTITY_MAP.get(ent, match.group(0))

    s = re.sub(r"(?:\\?u0026|&)(?:amp;)?([a-z0-9#]+);?", decode_entity, s, flags=re.IGNORECASE)
    s = re.sub(
        r"([a-zA-ZđĐ]{1,2})\s+([áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵ])(?:\s+([cmnptiy]|ch|ng|nh))?(?=\s|[.,;:!?\-]|$)",
        lambda m: m.group(1) + m.group(2) + (m.group(3) or ""),
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"attributes\s+code\b.*$", "", s, flags=re.IGNORECASE)
    s = re.sub(
        r"\s*(?:t\s*[aá]\s*d[uư][oợ]c|tá\s+dược|ta\s+duoc|công\s+dụng|cong\s+dung|chỉ\s+định|chi\s+dinh|hướng\s+dẫn|huong\s+dan|liều\s+dùng|lieu\s+dung|đối\s+tượng|oi\s+tuong|thận\s+trọng|than\s+trong|chống\s+chỉ\s+định|chong\s+chi\s+dinh|tác\s+dụng\s+phụ|tac\s+dung\s+phu|bảo\s+quản|bao\s+quan|hạn\s+dùng|han\s+dung|quy\s+cách|quy\s+cach|xuất\s+xứ|xuat\s+xu|nhà\s+sản\s+xuất|nha\s+san\s+xuat|tiêu\s+chuẩn|tieu\s+chuan|thành\s+phần|thanh\s+phan)\b.*$",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"\s+", " ", s).strip()
    return s


RED_FLAG_KEYWORDS = [
    ("kho tho", "CẢNH BÁO: DẤU HIỆU SUY HÔ HẤP", "Triệu chứng khó thở cấp là dấu hiệu cấp cứu y tế. Hãy gọi 115 hoặc đến cơ sở y tế gần nhất lập tức."),
    ("dau that nguc", "CẢNH BÁO: NGUY CƠ NHỒI MÁU CƠ TIM", "Đau thắt ngực dữ dội có thể là dấu hiệu bệnh mạch vành cấp. Cần gọi 115 khẩn cấp."),
    ("co giat", "CẢNH BÁO: CO GIẬT", "Sốt cao kèm co giật cần được đưa tới bệnh viện ngay lập tức."),
    ("non ra mau", "CẢNH BÁO: XUẤT HUYẾT TIÊU HÓA", "Nôn ra máu hoặc đi ngoài phân đen cần cấp cứu y tế ngay lập tức."),
    ("meo mieng", "CẢNH BÁO: DẤU HIỆU ĐỘT QUỴ", "Dấu hiệu méo miệng, yếu liệt nửa người cần cấp cứu trong thời gian vàng 3-4 giờ."),
]


@router.post("", response_model=ChatResponseSchema)
def chat_with_pharmacist(
    payload: ChatRequestSchema,
    request: Request,
    db: Session = Depends(get_db),
):
    raw_msg = clean_text(payload.message).strip()
    norm_msg = remove_vietnamese_tones(raw_msg)

    # 1. Dấu hiệu nguy hiểm (Red flags)
    for kw, title, detail in RED_FLAG_KEYWORDS:
        if kw in norm_msg:
            safety_alert = {
                "level": "emergency",
                "title": title,
                "message": detail,
                "action_required": "Gọi cấp cứu 115 hoặc tới cơ sở y tế gần nhất.",
                "emergency_number": "115",
            }
            return ChatResponseSchema(
                reply=f"🚨 **{title}**\n\n{detail}\n\n👉 **HÀNH ĐỘNG CẦN THIẾT:** Hãy gọi cấp cứu 115 hoặc tới bệnh viện gần nhất ngay lập tức.",
                safety_alert=safety_alert,
                quick_replies=["📞 Gọi cấp cứu 115", "🏥 Tìm cơ sở y tế"],
                provider_used="fastapi_safety_guard",
            )

    # 2. Câu lệnh HTML thô (u003ch2...)
    if re.search(r"^u003c|<[^>]+>|\\u003c", raw_msg, re.IGNORECASE):
        return ChatResponseSchema(
            reply="Dạ mình chưa hiểu rõ câu hỏi của bạn. Bạn có thể diễn đạt lại hoặc cho mình biết bạn đang cần tìm thuốc hay tư vấn triệu chứng gì không ạ?",
            quick_replies=["🔍 Tra cứu thuốc", "📦 Chính sách đổi trả"],
            provider_used="fastapi_h4care_expert",
        )

    # 3. Chào hỏi (GREETING)
    if re.search(r"^(hi|hello|hey|xin chao|chao ban|chao shop|chao duoc si|chao em|chao|alo)(\s+(ban|shop|duoc si|em|anh|chi|bot|nha|oi|a|nhe))*[\s!.,?~]*$", norm_msg, re.IGNORECASE):
        return ChatResponseSchema(
            reply="Xin chào! Mình là trợ lý H4CARE. Mình có thể giúp bạn tìm kiếm sản phẩm, tra cứu thông tin thuốc hoặc hướng dẫn mua hàng. Bạn cần hỗ trợ gì ạ?",
            quick_replies=["🔍 Tra cứu Vitamin C", "💊 Tìm thuốc hạ sốt", "📦 Phí giao hàng bao nhiêu?"],
            provider_used="fastapi_h4care_expert",
        )

    # 4. Định danh (IDENTITY)
    if re.search(r"\b(ban la ai|ban ten gi|ten ban la gi|ai tao ra ban)\b", norm_msg, re.IGNORECASE):
        return ChatResponseSchema(
            reply="Mình là **Trợ lý Dược sĩ AI H4CARE** – hệ thống tư vấn thông tin thuốc và hỗ trợ khách hàng của Hệ thống Nhà thuốc trực tuyến chuẩn GPP H4CARE. Mình luôn sẵn sàng hỗ trợ bạn 24/7.",
            quick_replies=["🔍 Tra cứu thông tin thuốc", "🚚 Chính sách giao hàng"],
            provider_used="fastapi_h4care_expert",
        )

    # 5. Cảm ơn (GRATITUDE)
    if re.search(r"\b(cam on|thank you|thanks|tks)\b", norm_msg, re.IGNORECASE):
        return ChatResponseSchema(
            reply="Dạ không có gì ạ! Rất vui được hỗ trợ bạn. Nếu cần tìm hiểu thêm về bất kỳ loại thuốc hay sản phẩm chăm sóc sức khỏe nào, bạn cứ nhắn cho mình nhé. Chúc bạn nhiều sức khỏe!",
            quick_replies=["🔍 Tra cứu sản phẩm khác", "📦 Hướng dẫn đặt hàng"],
            provider_used="fastapi_h4care_expert",
        )

    # 6. Hỏi giá không rõ sản phẩm (UNCLEAR PRICING)
    if re.search(r"^(thuoc nay|san pham nay|cai nay)?\s*(bao nhieu tien|gia bao nhieu|bao nhieu)[\s?]*$", norm_msg, re.IGNORECASE):
        return ChatResponseSchema(
            reply="Bạn đang muốn hỏi giá của loại thuốc hay sản phẩm nào ạ? Bạn hãy cho mình xin tên thuốc cụ thể (ví dụ: Panadol, Efferalgan, Vitamin C...) để mình tra cứu giá chính xác trong hệ thống nhé!",
            quick_replies=["💊 Giá Panadol Extra", "🍊 Giá Vitamin C DHC"],
            provider_used="fastapi_h4care_expert",
        )

    # 7. Chính sách Giao hàng & Phí ship (SHIPPING_POLICY)
    if re.search(r"\b(phi giao hang|phi ship|tien ship|phi van chuyen|thoi gian giao hang)\b", norm_msg, re.IGNORECASE):
        return ChatResponseSchema(
            reply="Dạ về **Chính sách giao hàng và Phí ship tại H4CARE**:\n\n- **Thời gian giao hàng:** 1 - 3 ngày làm việc trên toàn quốc.\n- **Phí giao hàng:** Đồng giá **25.000 đ** nội tỉnh, **35.000 đ** liên tỉnh. Miễn phí vận chuyển cho đơn hàng từ 300.000 đ trở lên.\n- **Đổi trả hàng lỗi:** 100% miễn phí thu hồi nếu lỗi do nhà thuốc hoặc hàng cận date (< 6 tháng).",
            quick_replies=["💳 Các phương thức thanh toán", "📦 Chính sách đổi trả 7 ngày"],
            provider_used="fastapi_h4care_expert",
        )

    # 8. Triệu chứng sức khỏe (SYMPTOM_CONSULTATION)
    if "dau bung" in norm_msg:
        return ChatResponseSchema(
            reply="Chào bạn, tình trạng đau bụng có thể do nhiều nguyên nhân khác nhau. Bạn cho mình hỏi: **Cơn đau xuất hiện ở vị trí nào (vùng trên rốn, quanh rốn hay bụng dưới) và đau âm ỉ hay quặn từng cơn ạ?**\n\n*(Nếu đau dữ dội đột ngột, bụng cứng hoặc kèm sốt, nôn mửa, bạn cần đến bệnh viện ngay nhé).*",
            quick_replies=["Đau vùng trên rốn", "Đau quặn quanh rốn", "Đau âm ỉ bụng dưới"],
            provider_used="fastapi_h4care_expert",
        )

    if "dau dau" in norm_msg:
        return ChatResponseSchema(
            reply="Chào bạn, tình trạng đau đầu kéo dài cần được theo dõi cẩn thận. Bạn cho mình hỏi thêm: **Bạn đau ở mức độ nào (đau âm ỉ cả đầu hay đau nhói nửa đầu) và có kèm theo sốt, chóng mặt hay buồn nôn không ạ?** Người bệnh là người lớn hay trẻ em vậy ạ?",
            quick_replies=["Đau âm ỉ, không sốt", "Đau nửa đầu", "Dành cho trẻ em"],
            provider_used="fastapi_h4care_expert",
        )

    # 9. Tìm kiếm thuốc trong cơ sở dữ liệu
    recommended_products = []
    try:
        stop_words = {"mua", "tim", "thuoc", "co", "ban", "cho", "toi", "minh", "em", "shop", "khong", "a", "nay", "do", "la", "gi"}
        search_terms = [t for t in norm_msg.split() if len(t) >= 2 and t not in stop_words]
        
        if search_terms:
            conditions = [CanonicalProduct.canonical_name.ilike(f"%{term}%") for term in search_terms[:3]]
            query = select(CanonicalProduct).where(CanonicalProduct.publish_status == PublishStatus.PUBLISHED)
            
            # Nếu chỉ 1 từ: khớp ilike; nếu >= 2 từ: phải khớp đồng thời ít nhất 2 từ hoặc cả cụm
            exact_clean = raw_msg.replace("thuốc", "").replace("thuoc", "").strip()
            if len(search_terms) == 1:
                query = query.where(conditions[0])
            else:
                from sqlalchemy import and_
                query = query.where(or_(CanonicalProduct.canonical_name.ilike(f"%{exact_clean}%"), and_(*conditions[:2])))

            products = db.scalars(query.limit(4)).all()

            for p in products:
                price_obs = db.scalars(
                    select(PriceObservation)
                    .where(PriceObservation.canonical_product_id == p.id)
                    .order_by(PriceObservation.observed_at.desc())
                ).first()

                price = int(price_obs.price) if price_obs and price_obs.price else 50000
                is_rx = p.rx_otc_status == RxOtcStatus.PRESCRIPTION

                recommended_products.append(
                    RecommendedProductSchema(
                        id=str(p.id),
                        name=clean_text(p.canonical_name),
                        slug=f"product-{p.id}",
                        brand=clean_text(p.manufacturer) or "H4CARE",
                        category_name="Thuốc Kê Đơn" if is_rx else "Thuốc Không Kê Đơn",
                        price=price,
                        image="https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=800",
                        active_ingredient=clean_text(p.active_ingredient)[:80] or "Theo công bố",
                        dosage_form="Viên nén",
                        stock=50,
                        is_prescription=is_rx,
                        short_description=clean_text(p.indications)[:120] or "Sản phẩm chính hãng H4CARE chuẩn GPP.",
                    )
                )
    except Exception:
        pass

    if recommended_products:
        reply = (
            "Dạ H4CARE tìm thấy các sản phẩm phù hợp trong hệ thống:\n\n"
            + "\n".join([f"- **{p.name}** ({'Thuốc kê đơn Rx' if p.is_prescription else 'OTC'}): {p.price:,} đ" for p in recommended_products])
            + "\n\n*Lưu ý: Quý khách cần đọc kỹ hướng dẫn sử dụng và tham vấn dược sĩ/bác sĩ trước khi dùng thuốc.*"
        )
        return ChatResponseSchema(
            reply=reply,
            recommended_products=recommended_products,
            quick_replies=["📖 Xem chi tiết liều dùng", "📦 Cách đặt hàng"],
            provider_used="fastapi_h4care_expert",
        )

    # 10. Mặc định: thừa nhận chưa có thông tin
    return ChatResponseSchema(
        reply=f"Dạ hiện tại H4CARE chưa tìm thấy thông tin sản phẩm trùng khớp với '{raw_msg}' trong danh mục hệ thống. Bạn có thể thử tìm theo tên hoạt chất hoặc liên hệ Dược sĩ qua email duocsi@h4care.vn nhé!",
        quick_replies=["🔍 Tìm thuốc hạ sốt", "🔍 Tra cứu Vitamin C", "📞 Kênh tư vấn Dược sĩ"],
        provider_used="fastapi_h4care_expert",
    )


@router.get("/health")
def chat_health():
    return {
        "status": "healthy",
        "service": "FastAPI H4CARE AI Chat Service",
        "version": "2.0.0",
    }
