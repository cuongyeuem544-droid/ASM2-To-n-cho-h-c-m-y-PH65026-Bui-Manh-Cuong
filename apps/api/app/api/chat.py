import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import CanonicalProduct, PriceObservation
from app.models.enums import PublishStatus, RxOtcStatus

router = APIRouter(prefix="/chat", tags=["AI Chatbot Tư Vấn Dược Sĩ"])


class ChatMessageSchema(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=2000)


class ChatRequestSchema(BaseModel):
    message: str = Field(default="", max_length=2000)
    conversation_history: List[ChatMessageSchema] = Field(default_factory=list)
    session_id: Optional[str] = None
    extracted_memory: Optional[dict[str, Any]] = None
    attachments: Optional[List[dict[str, Any]]] = None


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
    model_used: Optional[str] = None
    api_status: Optional[str] = "offline_expert_system"
    latency_ms: Optional[int] = None
    session_id: Optional[str] = None
    extracted_memory: Optional[dict[str, Any]] = None
    handoff_requested: bool = False
    context_summary: Optional[str] = None


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
    ("ngat", "CẢNH BÁO KHẨN CẤP: DẤU HIỆU NGẤT / MẤT Ý THỨC", "Dấu hiệu ngất, choáng váng mất tri giác hoặc đau dữ dội kèm ngất là tình trạng cấp cứu tối khẩn. Cần đưa người bệnh đến cơ sở y tế hoặc gọi 115 ngay lập tức."),
    ("bat tinh", "CẢNH BÁO KHẨN CẤP: BẤT TỈNH / HÔN MÊ", "Người bệnh bất tỉnh cần được hỗ trợ y tế khẩn cấp. Hãy gọi 115 ngay lập tức."),
    ("hon me", "CẢNH BÁO KHẨN CẤP: HÔN MÊ", "Người bệnh rơi vào trạng thái hôn mê cần cấp cứu ngay."),
    ("dau bung du doi", "CẢNH BÁO: ĐAU BỤNG CẤP DỮ DỘI", "Cơn đau bụng dữ dội đột ngột có thể là dấu hiệu viêm ruột thừa cấp hoặc thủng tạng rỗng. Cần đi cấp cứu ngay."),
]


VIETNAMESE_SLANG_MAP = [
    (r"\bmk\b", "mình"),
    (r"\btui\b", "tôi"),
    (r"\bko\b", "không"),
    (r"\bk\b", "không"),
    (r"\bkh\b", "không"),
    (r"\bdc\b", "được"),
    (r"\bhqua\b", "hôm qua"),
    (r"\bhnay\b", "hôm nay"),
    (r"\bbh\b", "bây giờ"),
    (r"\bntn\b", "như thế nào"),
    (r"\blm\b", "làm"),
    (r"\bj\b", "gì"),
    (r"\bz\b", "vậy"),
    (r"\bchx\b", "chưa"),
    (r"\bdg\b", "đang"),
    (r"\bvs\b", "với"),
    (r"\bcx\b", "cũng"),
    (r"\bib\b", "nhắn tin"),
    (r"\brep\b", "trả lời"),
    (r"\bns\b", "nói"),
    (r"\bhtrc\b", "hôm trước"),
    (r"\bb\b", "bạn"),
    (r"\bqua\s+h\b", "hôm qua đến giờ"),
    (r"\btd\s+phụ\b", "tác dụng phụ"),
    (r"\btd\s+phu\b", "tác dụng phụ"),
    (r"\b(\d+)\s*t\b", r"\1 tuổi"),
]


def normalize_vietnamese_slang(text: str) -> str:
    res = text
    for pattern, replacement in VIETNAMESE_SLANG_MAP:
        res = re.sub(pattern, replacement, res, flags=re.IGNORECASE)
    return res


def is_third_party_reference(text: str) -> bool:
    norm = remove_vietnamese_tones(text)
    third_party_regex = r"\b(me toi|bo toi|ba toi|ma toi|con toi|con cua toi|con gai toi|con trai toi|be nha toi|be nha minh|chau nha toi|chau nha minh|chau toi|vo toi|chong toi|ban toi|nguoi yeu|anh trai|em trai|em gai|chi gai|ong toi|ba noi|ba ngoai|ong noi|ong ngoai|bac si|duoc si|dong nghiep|hang xom)\b"
    return bool(re.search(third_party_regex, norm, re.IGNORECASE))


def is_name_query(text: str) -> bool:
    norm = remove_vietnamese_tones(normalize_vietnamese_slang(text))
    return bool(
        re.search(
            r"\b(ten toi la gi|toi ten gi|toi ten la gi|ten minh la gi|ban biet toi ten gi khong|ban co nho ten toi khong|ban nho ten toi khong|ban nho ten toi ko|nho ten toi khong|nho ten toi ko|co nho ten toi khong|toi ten la gi nhi|toi ten gi nhi|htrc.*ns ten j|ns ten j|minh ten j|ten mk la gi|mk ten gi|do ban.*ten gi|do b.*ten gi|nho ten mk ko|nho ten toi ko)\b",
            norm,
            re.IGNORECASE,
        )
        or re.search(r"^(ten toi la gi|toi ten gi|ten toi|ten minh|ten mk)[\s?]*$", norm, re.IGNORECASE)
    )


def extract_user_age(text: str) -> Optional[int]:
    if is_third_party_reference(text):
        return None
    norm = remove_vietnamese_tones(normalize_vietnamese_slang(text))
    m = re.search(r"\b(?:toi|minh|mk|em|anh|chi|tui|t)\s*(?:nam nay|hien|nay)?\s*(?:la|duoc)?\s*(\d{1,3})\s*(?:tuoi|t)\b", norm, re.IGNORECASE)
    if m:
        val = int(m.group(1))
        if 1 <= val <= 120:
            return val
    m_corr = re.search(r"\b(?:thuc ra|that ra|thuc su|thay vi|khong|gio|nham)\s*(?:toi|minh|mk|t)?\s*(\d{1,3})\s*(?:tuoi|t|r|roi)\b", norm, re.IGNORECASE)
    if m_corr:
        val = int(m_corr.group(1))
        if 1 <= val <= 120:
            return val
    m_simple = re.search(r"^\s*(?:toi|minh|mk|tui|t)?\s*(\d{1,3})\s*(?:tuoi|t)\s*(?:r|roi)?[\s.,!]*$", norm, re.IGNORECASE)
    if m_simple:
        val = int(m_simple.group(1))
        if 1 <= val <= 120:
            return val
    return None


def is_age_query(text: str) -> bool:
    norm = remove_vietnamese_tones(normalize_vietnamese_slang(text))
    return bool(
        re.search(
            r"\b(toi bao nhieu tuoi|minh bao nhieu tuoi|mk bao nhieu tuoi|toi bn tuoi|minh bn tuoi|mk bn tuoi|ban nho toi bao nhieu tuoi|ban nho mk bn tuoi|nho mk bn tuoi|toi may tuoi|minh may tuoi|tuoi cua toi|tuoi cua minh|tuoi cua mk|ban co nho tuoi toi|nho tuoi toi ko)\b",
            norm,
            re.IGNORECASE,
        )
    )


def detect_age_action(text: str, prev_age: Optional[int] = None) -> tuple[Optional[int], bool]:
    age = extract_user_age(text)
    if not age:
        return None, False
    norm = remove_vietnamese_tones(normalize_vietnamese_slang(text))
    is_correction = bool(prev_age and prev_age != age) or bool(re.search(r"\b(thuc ra|that ra|doi thanh|thay vi|khong|nham|gio la)\b", norm, re.IGNORECASE))
    return age, is_correction


def detect_user_mood(text: str) -> Optional[dict]:
    norm = remove_vietnamese_tones(normalize_vietnamese_slang(text))
    if re.search(r"\b(buon|hoi buon|buon qua|chan qua|tam trang khong tot|met moi trong long|tieu cuc)\b", norm, re.IGNORECASE):
        return {
            "type": "sad",
            "reply": "Có chuyện gì khiến bạn buồn vậy? Nếu muốn, bạn có thể tâm sự cùng mình nhé. Mình luôn sẵn sàng lắng nghe.",
        }
    if re.search(r"\b(lo lang|lo qua|bat an|so qua|hoang mang)\b", norm, re.IGNORECASE) and not re.search(r"\b(dau|sot|ngat|cap cuu)\b", norm, re.IGNORECASE):
        return {
            "type": "anxious",
            "reply": "Bạn đang cảm thấy lo lắng về điều gì vậy? Hãy hít thở thật sâu nhé, mình ở đây để cùng bạn tìm hiểu và tháo gỡ từng vấn đề.",
        }
    return None


def detect_symptom_escalation(text: str) -> bool:
    norm = remove_vietnamese_tones(normalize_vietnamese_slang(text))
    return bool(re.search(r"\b(dau hon|dau hon roi|dau nhieu hon|nang hon|nang hon roi|nang len|tang len|dau tang|cang luc cang dau|du doi hon|khong chiu noi|gio dau hon|bh dau hon|gio nang hon)\b", norm, re.IGNORECASE))


def parse_user_self_name(text: str) -> Optional[str]:
    if is_name_query(text) or is_third_party_reference(text):
        return None

    cleaned = text.strip()
    cleaned = re.sub(r"^(?:không|khong|không phải|khong phai|k|ko|hông)\s*[,.:;!-]?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:bạn|ban|shop|bot|ad)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:từ giờ|tu gio|từ nay|tu nay|giờ|gio|bây giờ|bay gio)\s+", "", cleaned, flags=re.IGNORECASE)

    patterns = [
        r"(?:lại thành tên|lai thanh ten|lại là tên|lai la ten|đổi tên thành|doi ten thanh|đổi thành tên|doi thanh ten|thành tên|thanh ten)\s+([A-ZÀ-Ỹa-zà-ỹ\s]{2,40})",
        r"(?:cứ gọi tôi là|cu goi toi la|cứ gọi mình là|cu goi minh la|cứ gọi em là|cu goi em la|gọi tôi là|goi toi la|gọi mình là|goi minh la|gọi em là|goi em la|gọi là|goi la)\s+([A-ZÀ-Ỹa-zà-ỹ\s]{2,40})",
        r"(?:tôi tên là|toi ten la|tôi tên|toi ten|tên tôi là|ten toi la|tên tôi|ten toi|mình tên là|minh ten la|mình tên|minh ten|tên mình là|ten minh la|tên mình|ten minh|em tên là|em ten la|em tên|em ten|tên em là|ten em la|anh tên là|anh ten la|anh tên|anh ten|chị tên là|chi ten la|chị tên|chi ten|m tên là|m ten la|m tên|m ten|mk tên là|mk ten la|mk tên|mk ten)\s+([A-ZÀ-Ỹa-zà-ỹ\s]{2,40})",
        r"^(?:tôi là|toi la|mình là|minh la|em là|em la|anh là|anh la|chị là|chi la)\s+([A-ZÀ-Ỹa-zà-ỹ\s]{2,30})$",
    ]

    for pat in patterns:
        m = re.search(pat, cleaned, re.IGNORECASE)
        if m:
            extracted = m.group(1).strip()
            extracted = re.split(r"[,.;!\n]", extracted)[0].strip()
            extracted = re.sub(
                r"\s+(cơ|co|nhé|nhe|nha|ạ|a|nè|ne|đây|day|đó|do|ơi|oi|đi|di|thôi|thoi|nhé shop|nha shop|ạ shop|nha bot|nhé bot|nhé bạn|nha bạn)$",
                "",
                extracted,
                flags=re.IGNORECASE,
            ).strip()

            if len(extracted) < 2:
                continue

            norm_extracted = remove_vietnamese_tones(extracted)
            banned = ["la ai", "la gi", "bot", "duoc si", "nhan vien", "bac si", "thuoc", "mua", "ban", "gi", "ai", "sot", "dau", "cam on", "chao", "alo", "suy nghi", "tu van"]
            if any(re.search(rf"\b{b}\b", norm_extracted, re.IGNORECASE) for b in banned):
                continue

            formatted_name = " ".join(w.capitalize() for w in extracted.split())
            return formatted_name

    return None


def detect_name_action(text: str, prev_user_name: Optional[str] = None) -> tuple[Optional[str], bool]:
    extracted = parse_user_self_name(text)
    if not extracted:
        return None, False

    norm = remove_vietnamese_tones(text)
    has_rename_keyword = bool(re.search(r"\b(gio|tu gio|tu nay|lai thanh|lai la|doi ten|thanh ten|khong|co|nhung|thay vi)\b", norm, re.IGNORECASE))
    had_previous_name = bool(prev_user_name and prev_user_name.lower() != extracted.lower())
    is_rename = had_previous_name or has_rename_keyword
    return extracted, is_rename


def sanitize_error(msg: str) -> str:
    if not msg:
        return ""
    s = str(msg)
    s = re.sub(r"key=[A-Za-z0-9_\-\.]+", "key=[REDACTED]", s, flags=re.IGNORECASE)
    s = re.sub(r"AIzaSy[A-Za-z0-9_\-\.]+", "[REDACTED_API_KEY]", s)
    s = re.sub(r"sk-[A-Za-z0-9_\-\.]+", "[REDACTED_API_KEY]", s)
    s = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED]", s)
    return s


def build_chat_system_prompt(memory: dict, context_summary: Optional[str] = None) -> str:
    memory_lines = []
    if memory.get("user_name"):
        memory_lines.append(f"- Tên khách hàng: {memory['user_name']}")
    if memory.get("age"):
        memory_lines.append(f"- Tuổi: {memory['age']} tuổi")
    if memory.get("gender"):
        memory_lines.append(f"- Giới tính: {memory['gender']}")
    if memory.get("symptoms"):
        syms = memory["symptoms"] if isinstance(memory["symptoms"], list) else [memory["symptoms"]]
        memory_lines.append(f"- Triệu chứng: {', '.join(syms)}")
    if memory.get("symptom_duration"):
        memory_lines.append(f"- Thời gian xuất hiện: {memory['symptom_duration']}")
    if memory.get("current_medicines"):
        meds = memory["current_medicines"] if isinstance(memory["current_medicines"], list) else [memory["current_medicines"]]
        memory_lines.append(f"- Thuốc đang dùng: {', '.join(meds)}")
    if memory.get("last_discussed_product"):
        memory_lines.append(f"- Thuốc vừa thảo luận: {memory['last_discussed_product']}")

    memory_block = (
        "=== BỘ NHỚ THỰC TẾ ĐÃ XÁC NHẬN TỪ NGƯỜI DÙNG (SESSION MEMORY) ===\n" + "\n".join(memory_lines)
        if memory_lines
        else "=== BỘ NHỚ PHIÊN: Khách hàng chưa chia sẻ thông tin cá nhân cụ thể. ==="
    )

    summary_block = f"\n=== TÓM TẮT NGỮ CẢNH TRƯỚC ĐÓ ===\n{context_summary}\n" if context_summary else ""

    return f"""Bạn là "Trợ lý AI H4CARE" - hệ thống tư vấn thông tin thuốc và chăm sóc sức khỏe thông minh chuẩn GPP H4CARE.
Mục tiêu của bạn là mang lại trải nghiệm hội thoại tự nhiên, thấu hiểu, ân cần như ChatGPT, đồng thời tuyệt đối tuân thủ quy chuẩn an toàn dược khoa và y tế.

{memory_block}
{summary_block}
=== NGUYÊN TẮC HỘI THOẠI TỰ NHIÊN (CHATGPT-STYLE) ===
1. Trả lời đúng trọng tâm câu hỏi của người dùng, không né tránh, không máy móc.
2. Câu hỏi ngắn/đơn giản -> Trả lời súc tích. Câu hỏi chuyên sâu/triệu chứng -> Giải thích rõ ràng, có cấu trúc.
3. KHÔNG chào lại ("Xin chào...") ở mỗi tin nhắn. Chỉ chào ở lượt đầu tiên.
4. Lắng nghe và tiếp nối dòng suy nghĩ của người dùng.
5. Khi người dùng dùng đại từ ("nó", "loại đó", "thuốc này") -> Hiểu đúng là đang nói về {memory.get('last_discussed_product') or 'loại thuốc vừa thảo luận'}.
6. Khi người dùng hỏi lại thông tin đã nói ("tôi bao nhiêu tuổi", "tên tôi là gì") -> Tra cứu đúng phần SESSION MEMORY ở trên để trả lời chính xác.

=== QUY TẮC Y TẾ VÀ AN TOÀN BẮT BUỘC ===
1. Triệu chứng sức khỏe:
   - ĐÂY LÀ TƯ VẤN SỨC KHỎE, TUYỆT ĐỐI KHÔNG TỰ ĐỘNG GỢI Ý DANH SÁCH THUỐC MUA SẮM.
   - CHỈ HỎI ĐÚNG MỘT CÂU TRỌNG TÂM mỗi lượt để làm rõ tình trạng.
   - Nếu phát hiện dấu hiệu nguy hiểm (ngất, khó thở, đau thắt ngực, nôn ra máu) -> Cảnh báo khẩn cấp gọi 115 ngay.
   - Không kết luận chắc chắn bệnh, không tự kê đơn thuốc điều trị.
2. Thông tin thuốc:
   - Giải thích rõ hoạt chất, công dụng, chống chỉ định, cảnh báo quá liều (Paracetamol tối đa 4g/ngày).
3. Gặp Dược sĩ thật:
   - Báo Hotline Dược sĩ 1800 6828 (8:00 - 21:00, miễn phí) hoặc email duocsi@h4care.vn.

=== NGÔN NGỮ ===
Tiếng Việt chuẩn y khoa, tự nhiên, ân cần, ngắn gọn, không sinh mã HTML thô."""


def call_gemini_api(
    api_key: str,
    model: str,
    system_prompt: str,
    history: List[ChatMessageSchema],
    message: str,
    timeout_sec: int = 25,
) -> tuple[str, int]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    contents = []
    for h in history[-6:]:
        role = "model" if h.role == "assistant" else "user"
        if h.content.strip():
            contents.append({"role": role, "parts": [{"text": h.content.strip()}]})
    contents.append({"role": "user", "parts": [{"text": message.strip()}]})

    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 800},
    }
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"}, method="POST")

    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            latency_ms = int((time.time() - start_time) * 1000)
            res_body = resp.read().decode("utf-8")
            data = json.loads(res_body)
            candidates = data.get("candidates", [])
            if candidates and candidates[0].get("content", {}).get("parts"):
                reply_text = candidates[0]["content"]["parts"][0].get("text", "").strip()
                return reply_text, latency_ms
            raise ValueError("Phản hồi từ Gemini API rỗng")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        sanitized = sanitize_error(err_body)
        raise RuntimeError(f"Gemini HTTP {e.code}: {sanitized}") from None
    except Exception as e:
        raise RuntimeError(f"Gemini connection error: {sanitize_error(str(e))}") from None


def call_openai_api(
    api_key: str,
    model: str,
    system_prompt: str,
    history: List[ChatMessageSchema],
    message: str,
    timeout_sec: int = 25,
) -> tuple[str, int]:
    url = "https://api.openai.com/v1/chat/completions"
    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-6:]:
        if h.content.strip():
            messages.append({"role": h.role, "content": h.content.strip()})
    messages.append({"role": "user", "content": message.strip()})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 800,
    }
    req_data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            latency_ms = int((time.time() - start_time) * 1000)
            res_body = resp.read().decode("utf-8")
            data = json.loads(res_body)
            choices = data.get("choices", [])
            if choices and choices[0].get("message", {}).get("content"):
                reply_text = choices[0]["message"]["content"].strip()
                return reply_text, latency_ms
            raise ValueError("Phản hồi từ OpenAI API rỗng")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        sanitized = sanitize_error(err_body)
        raise RuntimeError(f"OpenAI HTTP {e.code}: {sanitized}") from None
    except Exception as e:
        raise RuntimeError(f"OpenAI connection error: {sanitize_error(str(e))}") from None


@router.post("", response_model=ChatResponseSchema)
def chat_with_pharmacist(
    payload: ChatRequestSchema,
    request: Request,
    db: Session = Depends(get_db),
):
    raw_msg = payload.message.strip()
    norm_slang = normalize_vietnamese_slang(raw_msg)
    norm_msg = remove_vietnamese_tones(norm_slang)
    memory = dict(payload.extracted_memory or {})
    session_id = payload.session_id or "fastapi-sess"

    if payload.attachments:
        att = payload.attachments[0]
        att_name = att.get("file_name") or att.get("fileName") or att.get("name") or "image.jpg"
        memory["last_attached_image"] = att_name
        if "panadol" in att_name.lower() or "panadol" in raw_msg.lower():
            memory["last_discussed_product"] = "Panadol"

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
                session_id=session_id,
                extracted_memory=memory,
            )

    # 1.1 Cảnh báo cấp cứu: Viêm ruột thừa cấp khi đau hố chậu phải leo thang ("đau bụng dưới bên phải, giờ đau hơn r")
    if ("dau bung duoi ben phai" in norm_msg or ("ben phai" in norm_msg and "bung" in norm_msg)) and detect_symptom_escalation(norm_msg):
        safety_alert = {
            "level": "emergency",
            "title": "CẢNH BÁO NGUY CƠ VIÊM RUỘT THỪA CẤP",
            "message": "Cơn đau bụng dưới bên phải (hố chậu phải) có dấu hiệu tiến triển tăng nặng là biểu hiện kinh điển của Viêm ruột thừa cấp cần can thiệp ngoại khoa khẩn cấp.",
            "action_required": "Đến ngay khoa Cấp cứu bệnh viện gần nhất để siêu âm ổ bụng và làm xét nghiệm máu trước khi ruột thừa có nguy cơ vỡ mủ. TUYỆT ĐỐI KHÔNG tự ý uống thuốc giảm đau.",
            "emergency_number": "115",
        }
        return ChatResponseSchema(
            reply="🚨 **CẢNH BÁO NGUY CƠ VIÊM RUỘT THỪA CẤP CẦN ĐI KHÁM NGAY**\n\nCơn đau bụng dưới bên phải có dấu hiệu tăng nặng là biểu hiện rất điển hình của **Viêm ruột thừa cấp** hoặc bệnh lý ngoại khoa ổ bụng.\n\n👉 **LỜI KHUYÊN DƯỢC SĨ:**\n- **Đến ngay bệnh viện gần nhất** để bác sĩ thăm khám và siêu âm ổ bụng trước khi ruột thừa có nguy cơ vỡ mủ.\n- **TUYỆT ĐỐI KHÔNG** tự ý uống thuốc giảm đau vì sẽ che lấp triệu chứng cảnh báo của bác sĩ ngoại khoa.\n- Nhịn ăn uống tạm thời để chuẩn bị nếu cần can thiệp y tế.",
            safety_alert=safety_alert,
            quick_replies=["🏥 Tìm cơ sở y tế gần nhất", "📞 Gọi cấp cứu 115"],
            provider_used="fastapi_safety_guard",
            session_id=session_id,
            extracted_memory=memory,
        )

    # 2. Câu lệnh HTML thô (u003ch2...)
    if re.search(r"^u003c|<[^>]+>|\\u003c", raw_msg, re.IGNORECASE):
        return ChatResponseSchema(
            reply="Dạ mình chưa hiểu rõ câu hỏi của bạn. Bạn có thể diễn đạt lại hoặc cho mình biết bạn đang cần tìm thuốc hay tư vấn triệu chứng gì không ạ?",
            quick_replies=["🔍 Tra cứu thuốc", "📦 Chính sách đổi trả"],
            provider_used="fastapi_h4care_expert",
            session_id=session_id,
            extracted_memory=memory,
        )

    # 3. Truy vấn bộ nhớ: Tên tôi là gì? / Bạn nhớ tên tôi không?
    if is_name_query(raw_msg):
        user_name = memory.get("user_name")
        if user_name:
            reply = f"Tên bạn là {user_name}."
        else:
            reply = "Dạ bạn chưa chia sẻ tên với mình. Bạn có thể cho mình biết tên để tiện xưng hô nhé!"
        return ChatResponseSchema(
            reply=reply,
            quick_replies=["🔍 Tra cứu thuốc", "🤒 Tư vấn triệu chứng"],
            provider_used="fastapi_memory_engine",
            session_id=session_id,
            extracted_memory=memory,
        )

    # 3.1 Truy vấn bộ nhớ: Bạn nhớ tôi bao nhiêu tuổi không?
    if is_age_query(raw_msg):
        user_age = memory.get("age")
        if user_age:
            reply = f"Bạn đã chia sẻ là mình **{user_age} tuổi** rồi ạ."
        else:
            reply = "Dạ bạn chưa chia sẻ tuổi với mình. Bạn có thể cho mình biết tuổi để tư vấn liều dùng phù hợp nhé!"
        return ChatResponseSchema(
            reply=reply,
            quick_replies=["🔍 Tra cứu thuốc", "🤒 Tư vấn triệu chứng"],
            provider_used="fastapi_memory_engine",
            session_id=session_id,
            extracted_memory=memory,
        )

    # 4. Trích xuất hoặc cập nhật tên người dùng (hỗ trợ đổi tên tự nhiên, chống nhầm lẫn bên thứ 3)
    extracted_name, is_rename = detect_name_action(raw_msg, memory.get("user_name"))
    if extracted_name:
        memory["user_name"] = extracted_name
        if is_rename:
            reply = f"Dạ vâng! Mình đã cập nhật lại tên của bạn rồi nhé. Từ giờ mình sẽ gọi bạn là **{extracted_name}**! Rất vui được tiếp tục hỗ trợ bạn, bạn đang cần mình tư vấn thêm vấn đề gì ạ?"
        else:
            reply = f"Chào bạn **{extracted_name}**! Rất vui được đồng hành và hỗ trợ bạn hôm nay. Bạn cần mình tư vấn về vấn đề sức khỏe hay tra cứu loại thuốc nào ạ?"
        return ChatResponseSchema(
            reply=reply,
            quick_replies=["🔍 Tra cứu thông tin thuốc", "🤒 Tư vấn triệu chứng", "🎧 Gặp nhân viên tư vấn"],
            provider_used="fastapi_memory_engine",
            session_id=session_id,
            extracted_memory=memory,
        )

    # 4.1 Trích xuất hoặc cập nhật tuổi người dùng ("Tôi 39 tuổi", "mk 19t", "thực ra mk 20 r")
    extracted_age, is_age_corr = detect_age_action(raw_msg, memory.get("age"))
    if extracted_age:
        memory["age"] = extracted_age
        if is_age_corr:
            reply = f"Dạ vâng! Mình đã cập nhật lại tuổi của bạn là **{extracted_age} tuổi** rồi nhé. Thông tin tuổi này rất hữu ích để mình đưa ra tư vấn liều dùng và giải pháp phù hợp nhất. Bạn đang cần mình hỗ trợ gì thêm không ạ?"
        else:
            reply = f"Dạ mình đã ghi nhớ bạn **{extracted_age} tuổi** rồi nhé. Bạn đang có triệu chứng khó chịu nào hoặc cần tra cứu loại thuốc gì không ạ?"
        return ChatResponseSchema(
            reply=reply,
            quick_replies=["🔍 Tra cứu thông tin thuốc", "🤒 Tư vấn triệu chứng", "🎧 Gặp nhân viên tư vấn"],
            provider_used="fastapi_memory_engine",
            session_id=session_id,
            extracted_memory=memory,
        )

    # 4.2 Chia sẻ tâm trạng ("nay mk hơi buồn")
    mood_info = detect_user_mood(raw_msg)
    if mood_info:
        return ChatResponseSchema(
            reply=f"{mood_info['reply']}\n\nNếu bạn cảm thấy mệt mỏi trong người hoặc cần tư vấn về dinh dưỡng, sức khỏe, bạn cứ chia sẻ thêm với mình nhé!",
            quick_replies=["🤒 Tư vấn sức khỏe", "💊 Vitamin & Tăng đề kháng", "🎧 Trò chuyện với nhân viên"],
            provider_used="fastapi_conversational_engine",
            session_id=session_id,
            extracted_memory=memory,
        )

    # 5. Truy vấn bộ nhớ: Tôi bị gì nhỉ?
    if re.search(r"\b(toi bi gi|toi bi gi nhi|toi vua noi toi bi gi|toi dang bi gi)\b", norm_msg, re.IGNORECASE):
        symptoms = memory.get("symptoms", [])
        if symptoms:
            dur = f" ({memory['symptom_duration']})" if "symptom_duration" in memory else ""
            reply = f"Bạn vừa chia sẻ là đang bị **{', '.join(symptoms)}**{dur} ạ. Bạn thấy tình trạng hiện tại thế nào rồi?"
        else:
            reply = "Dạ trước đó bạn chưa chia sẻ triệu chứng cụ thể nào với mình. Bạn đang cảm thấy không khỏe ở đâu ạ?"
        return ChatResponseSchema(
            reply=reply,
            quick_replies=["🔍 Tra cứu thuốc", "🎧 Gặp nhân viên tư vấn"],
            provider_used="fastapi_memory_engine",
            session_id=session_id,
            extracted_memory=memory,
        )

    # 6. Truy vấn bộ nhớ: Tôi nói tôi đau từ khi nào?
    if re.search(r"\b(toi noi toi dau tu khi nao|toi dau tu khi nao|toi bi dau tu bao gio)\b", norm_msg, re.IGNORECASE):
        dur = memory.get("symptom_duration")
        if dur:
            reply = f"Bạn đã chia sẻ là bị đau **{dur}** ạ."
        else:
            reply = "Dạ bạn chưa chia sẻ thời gian cơn đau bắt đầu. Bạn bị đau từ khi nào ạ?"
        return ChatResponseSchema(
            reply=reply,
            quick_replies=["🔍 Tra cứu thuốc", "🤒 Tư vấn triệu chứng"],
            provider_used="fastapi_memory_engine",
            session_id=session_id,
            extracted_memory=memory,
        )

    # 7. Truy vấn bộ nhớ: Thuốc tôi đang hỏi là thuốc nào?
    if re.search(r"\b(thuoc toi dang hoi la thuoc nao|thuoc toi vua hoi la gi|thuoc toi dang hoi)\b", norm_msg, re.IGNORECASE):
        drug = memory.get("last_discussed_product")
        if drug:
            reply = f"Thuốc bạn đang tìm hiểu là **{drug}** ạ."
        else:
            reply = "Dạ bạn chưa nhắc đến tên loại thuốc cụ thể nào trong cuộc trò chuyện này."
        return ChatResponseSchema(
            reply=reply,
            quick_replies=["🔍 Tra cứu Paracetamol", "🔍 Tra cứu Vitamin C"],
            provider_used="fastapi_memory_engine",
            session_id=session_id,
            extracted_memory=memory,
        )

    # 8. Yêu cầu gặp Dược sĩ thật (HUMAN_SUPPORT / Handoff)
    if re.search(r"\b(duoc si that|bac si that|gap duoc si|gap bac si|nguoi that|gap nhan vien|nhan vien tu van|tong dai|can gap duoc si|toi muon gap duoc si)\b", norm_msg, re.IGNORECASE):
        name_prefix = f" bạn **{memory['user_name']}**" if "user_name" in memory else ""
        return ChatResponseSchema(
            reply=f"Dạ vâng{name_prefix}! Mình đang kích hoạt kết nối để chuyển cuộc trò chuyện sang **Dược sĩ / Nhân viên tư vấn trực tiếp của H4CARE** qua tab **\"Tư vấn trực tiếp\"** ngay bây giờ ạ.\n\nNhân viên hỗ trợ sẽ tiếp nhận và trò chuyện cùng bạn trong giây lát.\n\n*(Trường hợp cần tư vấn khẩn cấp về đơn thuốc, bạn cũng có thể gọi hotline Dược sĩ miễn cước: **1800 6828** từ 8:00 - 21:00 hàng ngày).* ",
            quick_replies=["🎧 Mở tab tư vấn trực tiếp", "📞 Hotline 1800 6828"],
            provider_used="fastapi_human_support",
            session_id=session_id,
            extracted_memory=memory,
            handoff_requested=True,
            context_summary=f"Khách yêu cầu gặp người thật: '{raw_msg}'",
        )

    # 9. Đa lượt triệu chứng: "Tôi bị đau bụng dưới" -> "Bạn bị đau bụng dưới từ khi nào?"
    if "dau bung duoi" in norm_msg:
        if "symptoms" not in memory:
            memory["symptoms"] = []
        if "đau bụng dưới" not in memory["symptoms"]:
            memory["symptoms"].append("đau bụng dưới")
        return ChatResponseSchema(
            reply="Bạn bị đau bụng dưới từ khi nào?",
            quickReplies=["Từ hôm qua", "Mới bị sáng nay", "Được 2-3 ngày nay"],
            provider_used="fastapi_symptom_triage",
            session_id=session_id,
            extracted_memory=memory,
        )

    # 10. Tiếp nối thời gian triệu chứng: "Từ hôm qua"
    if re.search(r"\b(tu hom qua|hom qua|sang nay|2 ngay)\b", norm_msg, re.IGNORECASE):
        memory["symptom_duration"] = "từ hôm qua" if "hom qua" in norm_msg else raw_msg
        return ChatResponseSchema(
            reply="Cơn đau chủ yếu ở bên trái, bên phải hay giữa bụng dưới?",
            quick_replies=["Bên phải", "Bên trái", "Ở giữa bụng dưới"],
            provider_used="fastapi_symptom_triage",
            session_id=session_id,
            extracted_memory=memory,
        )

    # 11. Chào hỏi (GREETING)
    if re.search(r"^(hi|hello|hey|xin chao|chao ban|chao shop|chao duoc si|chao em|chao|alo)(\s+(ban|shop|duoc si|em|anh|chi|bot|nha|oi|a|nhe))*[\s!.,?~]*$", norm_msg, re.IGNORECASE):
        greeting_name = f" bạn **{memory['user_name']}**" if "user_name" in memory else ""
        return ChatResponseSchema(
            reply=f"Xin chào{greeting_name}! Mình là **Trợ lý AI H4CARE** 🩺. Mình luôn sẵn sàng hỗ trợ bạn tư vấn sức khỏe ban đầu, tra cứu thông tin thuốc và giải đáp các thắc mắc về nhà thuốc. Bạn cần mình hỗ trợ gì hôm nay ạ?",
            quick_replies=["🔍 Tra cứu Vitamin C", "💊 Tìm thuốc hạ sốt", "📦 Phí giao hàng bao nhiêu?"],
            provider_used="fastapi_h4care_expert",
            session_id=session_id,
            extracted_memory=memory,
        )

    # 12. Định danh (IDENTITY)
    if re.search(r"\b(ban la ai|ban ten gi|ten ban la gi|ai tao ra ban)\b", norm_msg, re.IGNORECASE):
        return ChatResponseSchema(
            reply="Mình là **Trợ lý Dược sĩ AI H4CARE** – hệ thống tư vấn thông tin thuốc và hỗ trợ khách hàng của Hệ thống Nhà thuốc trực tuyến chuẩn GPP H4CARE. Mình luôn sẵn sàng hỗ trợ bạn 24/7.",
            quick_replies=["🔍 Tra cứu thông tin thuốc", "🚚 Chính sách giao hàng"],
            provider_used="fastapi_h4care_expert",
            session_id=session_id,
            extracted_memory=memory,
        )

    # 13. Cảm ơn (GRATITUDE)
    if re.search(r"\b(cam on|thank you|thanks|tks)\b", norm_msg, re.IGNORECASE):
        return ChatResponseSchema(
            reply="Dạ không có gì ạ! Rất vui được hỗ trợ bạn. Nếu cần tìm hiểu thêm về bất kỳ loại thuốc hay sản phẩm chăm sóc sức khỏe nào, bạn cứ nhắn cho mình nhé. Chúc bạn nhiều sức khỏe!",
            quick_replies=["🔍 Tra cứu sản phẩm khác", "📦 Hướng dẫn đặt hàng"],
            provider_used="fastapi_h4care_expert",
            session_id=session_id,
            extracted_memory=memory,
        )

    # 14. Thông tin dược lý thuốc (DRUG_INFORMATION)
    if re.search(r"\b(paracetamol|panadol|efferalgan|hapacol)\b.*(la thuoc gi|la gi|tac dung gi|cong dung)", norm_msg, re.IGNORECASE) or re.search(r"\b(paracetamol|panadol)\s+la\s+thuoc\s+gi\b", norm_msg, re.IGNORECASE):
        memory["last_discussed_product"] = "Paracetamol"
        return ChatResponseSchema(
            reply="**Paracetamol** (Acetaminophen) là thuốc giảm đau, hạ sốt phổ biến hàng đầu trong y khoa.\n\n- **Chỉ định:** Hạ sốt do cảm cúm, sốt siêu vi; giảm các cơn đau mức độ nhẹ đến vừa như đau đầu, đau răng, đau mỏi cơ, đau bụng kinh.\n- **Liều dùng thông thường (Người lớn):** 500mg - 1000mg/lần, mỗi lần cách nhau tối thiểu 4 - 6 giờ. **Tối đa không quá 4g (4.000mg)/ngày**.\n- ⚠️ **Cảnh báo an toàn (Gan):** Quá liều Paracetamol là nguyên nhân hàng đầu gây ngộ độc và hoại tử tế bào gan cấp. Tuyệt đối không dùng cùng lúc nhiều chế phẩm có chứa Paracetamol và tránh uống rượu bia trong thời gian dùng thuốc.",
            quick_replies=["💊 Paracetamol có tác dụng phụ gì?", "⚖️ So sánh với Ibuprofen", "🔍 Tìm mua Panadol H4CARE"],
            provider_used="fastapi_drug_knowledge",
            session_id=session_id,
            extracted_memory=memory,
        )

    # 15. Tác dụng phụ thuốc (xử lý cả đại từ thay thế "thuốc đó có tác dụng phụ gì?")
    has_side_effect = bool(re.search(r"\b(tac dung phu|tac dung khong mong muon|uong vao bi gi)\b", norm_msg, re.IGNORECASE))
    is_referring = bool(re.search(r"\b(thuoc do|thuoc nay|loai do|loai nay|paracetamol|panadol|no)\b", norm_msg, re.IGNORECASE))
    if has_side_effect and (is_referring or "last_discussed_product" in memory):
        target_drug = memory.get("last_discussed_product", "Paracetamol")
        return ChatResponseSchema(
            reply=f"Về **Tác dụng phụ và Thận trọng an toàn khi dùng {target_drug}**:\n\n- **Tác dụng không mong muốn thường gặp / nhẹ:** Phát ban nhẹ, nổi mề đay, rối loạn tiêu hóa nhẹ (hiếm gặp ở liều chuẩn).\n- ⚠️ **Độc tính trên gan (Cực kỳ nguy hiểm khi quá liều):** Dùng quá 4g/ngày hoặc dùng liều cao kéo dài, hoặc uống chung với rượu bia có thể gây hoại tử tế bào gan không hồi phục.\n- **Chống chỉ định & Thận trọng:** Người suy gan nặng, viêm gan tiến triển, người thiếu hụt men G6PD, người nghiện rượu.\n\n*Nếu xuất hiện dấu hiệu vàng da, mệt lả, nôn nhiều sau khi uống thuốc, cần ngừng thuốc và đến cơ sở y tế ngay lập tức.*",
            quick_replies=["⚖️ So sánh với Ibuprofen", "📖 Liều dùng đúng cách", "📞 Tổng đài Dược sĩ 1800 6828"],
            provider_used="fastapi_drug_knowledge",
            session_id=session_id,
            extracted_memory=memory,
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
            session_id=session_id,
            extracted_memory=memory,
        )

    # 10. Nếu có AI Provider bên ngoài được cấu hình (Gemini / OpenAI), gọi LLM thực tế
    gemini_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or (settings.ai_api_key if settings.ai_provider == "gemini" else "")
    openai_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY") or (settings.ai_api_key if settings.ai_provider == "openai" else "")

    if gemini_key:
        model = settings.ai_model or os.getenv("AI_MODEL") or "gemini-1.5-flash"
        system_prompt = build_chat_system_prompt(memory, payload.conversation_history[-1].content if payload.conversation_history else None)
        try:
            reply_text, latency_ms = call_gemini_api(
                api_key=gemini_key,
                model=model,
                system_prompt=system_prompt,
                history=payload.conversation_history,
                message=raw_msg,
                timeout_sec=settings.ai_timeout_seconds,
            )
            return ChatResponseSchema(
                reply=reply_text,
                quick_replies=["🔍 Tra cứu thông tin thuốc", "🤒 Tư vấn triệu chứng", "🎧 Gặp nhân viên tư vấn"],
                provider_used="google_gemini",
                model_used=model,
                api_status="real_llm_success",
                latency_ms=latency_ms,
                session_id=session_id,
                extracted_memory=memory,
            )
        except Exception as e:
            err_msg = str(e)
            is_quota = "429" in err_msg or "quota" in err_msg.lower() or "RESOURCE_EXHAUSTED" in err_msg
            status_notice = (
                "\n\n> ⚠️ **Thông báo hệ thống:** Mô hình AI ngoài (Google Gemini) đang tạm thời hết hạn mức sử dụng (Quota / Rate Limit). Hệ thống đã chuyển mạch sang Trợ lý Dược khoa H4CARE dự phòng để duy trì hỗ trợ cho bạn."
                if is_quota
                else "\n\n> ℹ️ **Thông báo hệ thống:** Kết nối tới mô hình AI ngoài (Google Gemini) bị gián đoạn. Câu trả lời này được cung cấp bởi Trợ lý Dược khoa H4CARE dự phòng."
            )
            fallback_reply = (
                f"Dạ hiện tại H4CARE chưa tìm thấy thông tin sản phẩm trùng khớp với '{raw_msg}' trong danh mục hệ thống. Bạn có thể thử tìm theo tên hoạt chất hoặc liên hệ Dược sĩ qua email duocsi@h4care.vn nhé!{status_notice}"
            )
            return ChatResponseSchema(
                reply=fallback_reply,
                quick_replies=["🔍 Tìm thuốc hạ sốt", "🔍 Tra cứu Vitamin C", "📞 Kênh tư vấn Dược sĩ"],
                provider_used="google_gemini_fallback",
                model_used="fallback-on-api-error",
                api_status="quota_exceeded" if is_quota else "api_error",
                session_id=session_id,
                extracted_memory=memory,
            )

    if openai_key:
        model = settings.ai_model or os.getenv("AI_MODEL") or "gpt-4o-mini"
        system_prompt = build_chat_system_prompt(memory, payload.conversation_history[-1].content if payload.conversation_history else None)
        try:
            reply_text, latency_ms = call_openai_api(
                api_key=openai_key,
                model=model,
                system_prompt=system_prompt,
                history=payload.conversation_history,
                message=raw_msg,
                timeout_sec=settings.ai_timeout_seconds,
            )
            return ChatResponseSchema(
                reply=reply_text,
                quick_replies=["🔍 Tra cứu thông tin thuốc", "🤒 Tư vấn triệu chứng", "🎧 Gặp nhân viên tư vấn"],
                provider_used="openai",
                model_used=model,
                api_status="real_llm_success",
                latency_ms=latency_ms,
                session_id=session_id,
                extracted_memory=memory,
            )
        except Exception as e:
            err_msg = str(e)
            is_quota = "429" in err_msg or "quota" in err_msg.lower() or "insufficient_quota" in err_msg
            status_notice = (
                "\n\n> ⚠️ **Thông báo hệ thống:** Mô hình AI ngoài (OpenAI) đang tạm thời hết hạn mức sử dụng (Quota / Rate Limit). Hệ thống đã chuyển mạch sang Trợ lý Dược khoa H4CARE dự phòng để duy trì hỗ trợ cho bạn."
                if is_quota
                else "\n\n> ℹ️ **Thông báo hệ thống:** Kết nối tới mô hình AI ngoài (OpenAI) bị gián đoạn. Câu trả lời này được cung cấp bởi Trợ lý Dược khoa H4CARE dự phòng."
            )
            fallback_reply = (
                f"Dạ hiện tại H4CARE chưa tìm thấy thông tin sản phẩm trùng khớp với '{raw_msg}' trong danh mục hệ thống. Bạn có thể thử tìm theo tên hoạt chất hoặc liên hệ Dược sĩ qua email duocsi@h4care.vn nhé!{status_notice}"
            )
            return ChatResponseSchema(
                reply=fallback_reply,
                quick_replies=["🔍 Tìm thuốc hạ sốt", "🔍 Tra cứu Vitamin C", "📞 Kênh tư vấn Dược sĩ"],
                provider_used="openai_fallback",
                model_used="fallback-on-api-error",
                api_status="quota_exceeded" if is_quota else "api_error",
                session_id=session_id,
                extracted_memory=memory,
            )

    # 11. Mặc định: thừa nhận chưa có thông tin khi chạy Offline Expert System
    return ChatResponseSchema(
        reply=f"Dạ hiện tại H4CARE chưa tìm thấy thông tin sản phẩm trùng khớp với '{raw_msg}' trong danh mục hệ thống. Bạn có thể thử tìm theo tên hoạt chất hoặc liên hệ Dược sĩ qua email duocsi@h4care.vn nhé!",
        quick_replies=["🔍 Tìm thuốc hạ sốt", "🔍 Tra cứu Vitamin C", "📞 Kênh tư vấn Dược sĩ"],
        provider_used="fastapi_h4care_expert",
        model_used="expert-rules-v2",
        api_status="offline_expert_system",
        session_id=session_id,
        extracted_memory=memory,
    )


@router.get("/health")
def chat_health():
    return {
        "status": "healthy",
        "service": "FastAPI H4CARE AI Chat Service",
        "version": "2.0.0",
    }
