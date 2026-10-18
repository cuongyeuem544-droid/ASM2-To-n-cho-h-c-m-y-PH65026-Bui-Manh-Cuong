from __future__ import annotations

import re
import time
import unicodedata
from typing import Any, Dict, List, Optional

from app.services.chatbot.base import BaseChatProvider, ProviderResult, ProviderStatus


def remove_vietnamese_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để tìm kiếm từ khóa an toàn."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text.replace("đ", "d").replace("Đ", "D").lower().strip()


# Danh mục triệu chứng nguy hiểm khẩn cấp (Red Flags)
RED_FLAG_CONDITIONS = [
    {
        "keywords": ["dau that nguc", "tuc nguc", "kho tho du doi", "dau tim", "nghet tho"],
        "title": "Cảnh báo khẩn cấp: Dấu hiệu tim mạch / hô hấp cấp tính",
        "message": "Các triệu chứng đau tức ngực, nghẹt thở hoặc khó thở dữ dội là dấu hiệu nguy hiểm tiềm ẩn của cơn thiếu máu cơ tim hoặc thuyên tắc phổi cấp.",
        "action": "Hãy gọi ngay Cấp cứu 115 hoặc nhờ người thân đưa ngay tới cơ sở y tế gần nhất.",
    },
    {
        "keywords": ["sot cao co giat", "co giat", "sot li bi", "me sang"],
        "title": "Cảnh báo khẩn cấp: Sốt cao kèm co giật / rối loạn tri giác",
        "message": "Sốt cao co giật hoặc li bì là tình trạng cấp cứu, đặc biệt nguy hiểm ở trẻ nhỏ hoặc người cao tuổi.",
        "action": "Cởi bớt quần áo, lau mát bằng nước ấm và đưa đến phòng cấp cứu ngay lập tức. Không nhét dị vật vào miệng người bệnh.",
    },
    {
        "keywords": ["non ra mau", "di ngoai phan den", "xuat huyet tieu hoa", "non mau"],
        "title": "Cảnh báo khẩn cấp: Nghi ngờ xuất huyết đường tiêu hóa",
        "message": "Nôn ra máu hoặc đi cầu phân đen như bã cà phê là dấu hiệu của chảy máu tiêu hóa cấp.",
        "action": "Dừng ngay mọi loại thuốc giảm đau (đặc biệt NSAIDs như Aspirin, Ibuprofen) và đến bệnh viện cấp cứu.",
    },
    {
        "keywords": ["dau bung ho chau phai", "ruot thua", "dau bung duoi phai", "dau ho chau phai"],
        "title": "Cảnh báo: Dấu hiệu nghi ngờ viêm ruột thừa cấp",
        "message": "Đau dữ dội âm ỉ tăng dần ở vùng hố chậu phải (bụng dưới bên phải) kèm sốt nhẹ hoặc buồn nôn có thể là viêm ruột thừa.",
        "action": "Tuyệt đối KHÔNG tự uống thuốc giảm đau hay chườm nóng vì làm mờ triệu chứng. Đi khám ngoại khoa ngay.",
    },
    {
        "keywords": ["ngat", "ngat xiu", "bat tinh", "hon me", "mat y thuc"],
        "title": "Cảnh báo khẩn cấp: Mất ý thức / ngất xỉu",
        "message": "Mất tri giác hoặc ngất xỉu đột ngột phản ánh tưới máu não bị gián đoạn.",
        "action": "Đặt người bệnh nằm đầu thấp nghiêng sang một bên, đảm bảo đường thở thông thoáng và gọi 115 ngay.",
    },
]

# Cơ sở tri thức Dược lý chuẩn Quốc gia (H4CARE Certified OTC)
CERTIFIED_DRUG_KNOWLEDGE = {
    "paracetamol": {
        "names": ["paracetamol", "panadol", "efferalgan", "acetaminophen", "hapacol"],
        "active_substance": "Paracetamol",
        "indications": "Hạ sốt, giảm đau mức độ từ nhẹ đến vừa (đau đầu, đau răng, đau họng, nhức mỏi cơ do cảm cúm).",
        "dosage": "Người lớn: 500mg - 1000mg/lần, cách nhau ít nhất 4 - 6 giờ. Tối đa không quá 4g (4000mg)/ngày.",
        "contraindications": "Người mẫn cảm với paracetamol, người suy giảm chức năng gan nặng hoặc nghiện rượu.",
        "warnings": "QUAN TRỌNG: Không phối hợp nhiều chế phẩm cùng chứa Paracetamol (như Panadol + cảm cúm viên sủi) để tránh ngộ độc gan cấp.",
    },
    "ibuprofen": {
        "names": ["ibuprofen", "alaxan", "gofen", "brufen"],
        "active_substance": "Ibuprofen (NSAID)",
        "indications": "Kháng viêm, giảm đau (đau răng, đau khớp, đau bụng kinh, chấn thương mô mềm).",
        "dosage": "Người lớn: 200mg - 400mg/lần sau bữa ăn no, cách nhau 6 - 8 giờ. Tối đa không quá 1200mg/ngày khi tự điều trị.",
        "contraindications": "Tiền sử loét dạ dày tá tràng, suy thận nặng, phụ nữ có thai 3 tháng cuối.",
        "warnings": "Uống sau khi ăn no kèm nhiều nước. Thận trọng ở người có bệnh lý tim mạch, huyết áp.",
    },
    "vitamin_c": {
        "names": ["vitamin c", "cebion", "berocca", "c sủi"],
        "active_substance": "Ascorbic Acid (Vitamin C)",
        "indications": "Bổ sung vi chất, tăng sức đề kháng, hỗ trợ phòng ngừa và giảm mệt mỏi khi ốm dậy.",
        "dosage": "Người lớn nhu cầu hàng ngày 75 - 100mg/ngày. Liều tăng cường thông thường 500mg/ngày.",
        "contraindications": "Người thừa sắt, bệnh Thalassemia, tiền sử sỏi thận (oxalat).",
        "warnings": "Nên uống vào ban ngày (buổi sáng hoặc trưa sau ăn), tránh uống tối muộn vì có thể gây khó ngủ và tăng lắng đọng sỏi thận.",
    },
    "gaviscon": {
        "names": ["gaviscon", "gastropulgite", "chua da day", "trao nguoc"],
        "active_substance": "Sodium alginate, Sodium bicarbonate, Calcium carbonate",
        "indications": "Giảm triệu chứng trào ngược dạ dày thực quản (ợ nóng, ợ chua, đau rát sau xương ức).",
        "dosage": "Người lớn: 1 - 2 gói/lần sau 3 bữa ăn chính và trước khi đi ngủ.",
        "contraindications": "Người mẫn cảm với bất kỳ thành phần nào của thuốc, suy thận nặng.",
        "warnings": "Uống cách xa các thuốc khác ít nhất 2 giờ vì có thể làm giảm hấp thu các thuốc dùng kèm.",
    },
}


class H4CareExpertProvider(BaseChatProvider):
    """
    Bộ xử lý Dược sĩ AI Chuyên gia H4CARE độc lập.
    Đảm bảo 100% thời gian phản hồi an toàn y tế ngay cả khi mất kết nối mạng hoặc LLM bị lỗi.
    """

    def __init__(self):
        super().__init__(provider_id="h4care_expert", display_name="H4CARE Medical Expert Engine")

    def detect_red_flags(self, text: str) -> Optional[Dict[str, Any]]:
        clean_text = remove_vietnamese_accents(text)
        for item in RED_FLAG_CONDITIONS:
            for kw in item["keywords"]:
                if re.search(r"\b" + re.escape(kw) + r"\b", clean_text):
                    return {
                        "level": "CRITICAL",
                        "title": item["title"],
                        "message": item["message"],
                        "action": item["action"],
                        "emergency_number": "115",
                    }
        return None

    def match_drug_knowledge(self, text: str) -> Optional[Dict[str, Any]]:
        clean_text = remove_vietnamese_accents(text)
        for key, drug in CERTIFIED_DRUG_KNOWLEDGE.items():
            for name in drug["names"]:
                if re.search(r"\b" + re.escape(name) + r"\b", clean_text):
                    return drug
        return None

    async def generate_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 800,
        timeout_seconds: int = 25,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        start_time = time.perf_counter()

        # 1. Kiểm tra Red Flag
        red_flag = self.detect_red_flags(user_message)
        safety_flags = []
        if red_flag:
            safety_flags.append(red_flag)
            response_text = (
                f"🚨 **{red_flag['title']}**\n\n"
                f"{red_flag['message']}\n\n"
                f"👉 **Khuyến cáo hành động ngay:** {red_flag['action']}\n\n"
                f"📞 **Đường dây nóng Cấp cứu Y tế Toàn quốc:** `115`\n"
                f"🏥 **Hotline Dược sĩ H4CARE:** 1800 6828 (8:00 - 21:00, miễn phí)\n\n"
                f"*(Lưu ý: Tình trạng này vượt quá giới hạn tư vấn trực tuyến, Quý khách cần can thiệp y tế trực tiếp ngay lập tức!)*"
            )
            latency = int((time.perf_counter() - start_time) * 1000)
            return ProviderResult(
                text=response_text,
                provider="h4care_expert",
                model="expert-medical-rules-v1",
                latency_ms=latency,
                http_status=200,
                result="success",
                safety_flags=safety_flags,
                finish_reason="safety_alert",
            )

        # 2. Kiểm tra thông tin thuốc theo Dược thư
        matched_drug = self.match_drug_knowledge(user_message)
        if matched_drug:
            response_text = (
                f"Chào Quý khách! Dưới đây là thông tin y khoa chính thức về hoạt chất **{matched_drug['active_substance']}** "
                f"theo tiêu chuẩn Dược thư Quốc gia:\n\n"
                f"🔹 **Chỉ định:** {matched_drug['indications']}\n\n"
                f"🔹 **Liều dùng thông thường:** {matched_drug['dosage']}\n\n"
                f"⚠️ **Chống chỉ định:** {matched_drug['contraindications']}\n\n"
                f"❗ **Lưu ý an toàn:** {matched_drug['warnings']}\n\n"
                f"💡 *Quý khách cần đọc kỹ hướng dẫn sử dụng trong hộp thuốc và tham vấn Dược sĩ nếu có bệnh lý nền đi kèm.*"
            )
            latency = int((time.perf_counter() - start_time) * 1000)
            return ProviderResult(
                text=response_text,
                provider="h4care_expert",
                model="expert-medical-rules-v1",
                latency_ms=latency,
                http_status=200,
                result="success",
                finish_reason="knowledge_match",
            )

        # 3. Phản hồi hướng dẫn chung / Phân loại triệu chứng an toàn
        clean_msg = remove_vietnamese_accents(user_message)
        if any(term in clean_msg for term in ["chao", "xin chao", "alo", "hi", "hello"]):
            response_text = (
                "Kính chào Quý khách! Tôi là **Trợ lý Dược sĩ AI H4CARE**.\n\n"
                "Tôi có thể hỗ trợ Quý khách tra cứu thông tin thuốc OTC, hướng dẫn sử dụng an toàn, "
                "phân tích tương tác thuốc cơ bản và giải đáp chính sách nhà thuốc GPP H4CARE.\n\n"
                "Quý khách đang cần tìm hiểu về thuốc nào hoặc đang gặp triệu chứng sức khỏe gì ạ?"
            )
        elif any(term in clean_msg for term in ["gia", "ship", "phi van chuyen", "doi tra", "hoan tien", "giao hang"]):
            response_text = (
                "Về chính sách bán hàng và dịch vụ tại Nhà thuốc H4CARE:\n\n"
                "📦 **Giao hàng:** Miễn phí vận chuyển cho đơn hàng từ 300.000đ. Đơn nội thành HN và TP.HCM nhận trong 2 - 4 giờ.\n"
                "🔄 **Chính sách đổi trả:** Hỗ trợ đổi trả trong vòng 30 ngày đối với sản phẩm còn nguyên tem niêm phong.\n"
                "🛡️ **Cam kết 100% chính hãng:** Tất cả dược phẩm đều đạt chuẩn GPP, có hóa đơn và kiểm soát nguồn gốc nghiêm ngặt."
            )
        elif any(term in clean_msg for term in ["sot", "dau dau", "chong mat", "ho", "so mui", "viem hong"]):
            response_text = (
                "Dược sĩ H4CARE đã ghi nhận triệu chứng của Quý khách. Để tư vấn chính xác và an toàn nhất:\n\n"
                "1. Quý khách bị tình trạng này từ khi nào (mấy ngày qua)?\n"
                "2. Hiện tại có kèm theo dấu hiệu nào khác như sốt cao, khó thở hay mệt lả không?\n"
                "3. Quý khách có tiền sử dị ứng thuốc hay bệnh nền dạ dày, huyết áp, gan/thận không ạ?\n\n"
                "*(Nếu sốt trên 38.5°C kéo dài trên 2 ngày không hạ, Quý khách cần đến cơ sở y tế để được thăm khám trực tiếp.)*"
            )
        else:
            response_text = (
                "Cảm ơn Quý khách đã gửi câu hỏi đến Dược sĩ AI H4CARE.\n\n"
                "Để đảm bảo an toàn sử dụng thuốc theo quy chuẩn GPP, Quý khách vui lòng cung cấp thêm: "
                "tên thuốc cụ thể, độ tuổi của người sử dụng và các triệu chứng hiện tại.\n\n"
                "📞 Nếu cần tư vấn trực tiếp với Dược sĩ chuyên môn, Quý khách có thể liên hệ Tổng đài miễn cước: **1800 6828** (8:00 - 21:00)."
            )

        latency = int((time.perf_counter() - start_time) * 1000)
        return ProviderResult(
            text=response_text,
            provider="h4care_expert",
            model="expert-medical-rules-v1",
            latency_ms=latency,
            http_status=200,
            result="success",
            finish_reason="stop",
        )

    async def check_health(self) -> ProviderStatus:
        return ProviderStatus(
            provider="h4care_expert",
            name="H4CARE Medical Expert Engine (Quy chuẩn Dược lâm sàng)",
            is_configured=True,
            is_healthy=True,
            available_models=["expert-medical-rules-v1"],
            latency_ms=1,
            error_message=None,
        )
