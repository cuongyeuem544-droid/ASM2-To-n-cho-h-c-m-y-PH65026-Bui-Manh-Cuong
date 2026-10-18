from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.models.chatbot import (
    ChatbotAuditLog,
    ChatbotSettings,
    ChatFeedback,
    ChatKnowledgeItem,
    ChatMessage,
    ChatPromptVersion,
    ChatProviderAttempt,
    ChatSession,
)
from app.models.entities import CanonicalProduct, User
from app.services.chatbot.base import BaseChatProvider, ProviderResult, ProviderStatus
from app.services.chatbot.expert_provider import (
    H4CareExpertProvider,
    remove_vietnamese_accents,
)
from app.services.chatbot.gemini_provider import GeminiChatProvider
from app.services.chatbot.ollama_provider import OllamaChatProvider
from app.services.chatbot.openai_provider import OpenAIChatProvider

logger = logging.getLogger(__name__)


DEFAULT_GPP_SYSTEM_PROMPT = """Bạn là "Trợ lý Dược sĩ AI H4CARE" - hệ thống tư vấn thông tin thuốc và chăm sóc sức khỏe của Hệ thống Nhà thuốc trực tuyến chuẩn GPP H4CARE.

=== QUY TẮC Y TẾ VÀ AN TOÀN BẮT BUỘC ===
1. Khi người dùng mô tả triệu chứng sức khỏe:
   - ĐÂY LÀ TƯ VẤN SỨC KHỎE, TUYỆT ĐỐI KHÔNG TỰ ĐỘNG GỢI Ý DANH SÁCH THUỐC MUA SẮM.
   - CHỈ HỎI ĐÚNG MỘT CÂU TRỌNG TÂM mỗi lượt để làm rõ tình trạng (thời gian xuất hiện -> vị trí -> triệu chứng cảnh báo kèm theo).
   - Nếu phát hiện dấu hiệu nguy hiểm (ngất, khó thở, đau thắt ngực, sốt cao co giật, nôn ra máu, đau hố chậu phải nghi ruột thừa) -> Lập tức cảnh báo khẩn cấp và khuyên đi khám/gọi 115 ngay.
   - Không kết luận chắc chắn bệnh, không tự kê đơn thuốc kê đơn (Rx).

2. Khi người dùng hỏi thông tin thuốc (Paracetamol, Ibuprofen, Vitamin C...):
   - Giải thích rõ hoạt chất, công dụng, chống chỉ định, cảnh báo quá liều (đặc biệt độc tính gan của Paracetamol khi dùng > 4g/ngày).
   - Trả lời trung thực, khách quan theo Dược thư Quốc gia.

3. Kênh kết nối Dược sĩ thật:
   - Hotline Dược sĩ 1800 6828 (8:00 - 21:00, miễn cước) hoặc email duocsi@h4care.vn. Không giả mạo có người thật chat trực tiếp 24/7.

=== NGÔN NGỮ ===
Tiếng Việt chuẩn y khoa, tự nhiên, ân cần, ngắn gọn, dễ hiểu."""


class ChatbotOrchestrator:
    """
    Bộ điều phối trung tâm Chatbot Dược sĩ AI.
    Quản lý chuyển mạch failover, lưu vết vào database và đảm bảo an toàn y tế.
    """

    def __init__(self):
        self.providers: Dict[str, BaseChatProvider] = {
            "gemini": GeminiChatProvider(),
            "openai": OpenAIChatProvider(),
            "ollama": OllamaChatProvider(),
            "h4care_expert": H4CareExpertProvider(),
        }

    def get_provider(self, provider_id: str) -> Optional[BaseChatProvider]:
        return self.providers.get(provider_id)

    def get_or_create_settings(self, db: Session) -> ChatbotSettings:
        settings = db.scalar(select(ChatbotSettings).order_by(ChatbotSettings.id).limit(1))
        if not settings:
            settings = ChatbotSettings(
                enabled=True,
                active_provider="gemini",
                active_model="gemini-1.5-flash",
                failover_order='["gemini", "openai", "ollama", "h4care_expert"]',
                temperature=0.2,
                max_output_tokens=800,
                timeout_seconds=25,
                max_retries=2,
                retention_days=90,
            )
            db.add(settings)
            db.commit()
            db.refresh(settings)
        return settings

    def get_active_system_prompt(self, db: Session, settings: ChatbotSettings) -> tuple[str, Optional[int]]:
        """Lấy nội dung System Prompt đang được xuất bản."""
        if settings.system_prompt_version_id:
            prompt_version = db.scalar(
                select(ChatPromptVersion).where(ChatPromptVersion.id == settings.system_prompt_version_id)
            )
            if prompt_version:
                return prompt_version.content, prompt_version.id

        latest_published = db.scalar(
            select(ChatPromptVersion)
            .where(ChatPromptVersion.status == "published")
            .order_by(desc(ChatPromptVersion.published_at))
            .limit(1)
        )
        if latest_published:
            return latest_published.content, latest_published.id

        return DEFAULT_GPP_SYSTEM_PROMPT, None

    def search_knowledge_context(self, db: Session, query: str, limit: int = 3) -> str:
        """Tìm các mục tri thức y tế liên quan trong Database để bổ sung context."""
        clean_q = remove_vietnamese_accents(query)
        words = [w for w in clean_q.split() if len(w) > 2]
        if not words:
            return ""

        # Lọc các mục tri thức đang kích hoạt
        items = db.scalars(
            select(ChatKnowledgeItem)
            .where(ChatKnowledgeItem.is_active == True)
            .order_by(desc(ChatKnowledgeItem.id))
            .limit(10)
        ).all()

        matched_snippets = []
        for it in items:
            it_text = remove_vietnamese_accents(f"{it.title} {it.question or ''} {it.keywords or ''}")
            if any(w in it_text for w in words):
                snippet = f"- **{it.title}**: {it.content or it.answer}"
                matched_snippets.append(snippet)
                if len(matched_snippets) >= limit:
                    break

        if matched_snippets:
            return "\n=== TRI THỨC Y TẾ BỔ SUNG TỪ HỆ THỐNG H4CARE ===\n" + "\n".join(matched_snippets) + "\n"
        return ""

    async def check_all_providers(self) -> List[ProviderStatus]:
        """Kiểm tra sức khỏe của toàn bộ các Provider phục vụ Admin."""
        statuses = []
        for p_id in ["gemini", "openai", "ollama", "h4care_expert"]:
            provider = self.providers.get(p_id)
            if provider:
                try:
                    status = await provider.check_health()
                    statuses.append(status)
                except Exception as e:
                    statuses.append(
                        ProviderStatus(
                            provider=p_id,
                            name=provider.display_name,
                            is_configured=False,
                            is_healthy=False,
                            available_models=[],
                            error_message=str(e),
                        )
                    )
        return statuses

    async def execute_chat(
        self,
        db: Session,
        message: str,
        session_id: Optional[str] = None,
        client_session_id: Optional[str] = None,
        current_user: Optional[User] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        context_product: Optional[Dict[str, Any]] = None,
        ip_hash: Optional[str] = None,
        user_agent_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Xử lý yêu cầu trò chuyện, thực hiện Failover và lưu lịch sử vào Database.
        """
        start_total = time.perf_counter()
        correlation_id = str(uuid.uuid4())
        settings = self.get_or_create_settings(db)

        # 1. Quản lý hoặc tạo phiên ChatSession
        chat_session: Optional[ChatSession] = None
        if session_id:
            chat_session = db.scalar(select(ChatSession).where(ChatSession.id == session_id))

        if not chat_session and client_session_id:
            chat_session = db.scalar(select(ChatSession).where(ChatSession.client_session_id == client_session_id))

        if not chat_session:
            new_session_id = session_id or str(uuid.uuid4())
            chat_session = ChatSession(
                id=new_session_id,
                user_id=current_user.id if current_user else None,
                status="active",
                channel="storefront_widget",
                client_session_id=client_session_id,
                ip_hash=ip_hash,
                user_agent_summary=user_agent_summary,
                message_count=0,
            )
            db.add(chat_session)
            db.flush()
        else:
            # Nếu người dùng vừa đăng nhập trong phiên hiện tại thì gắn user_id
            if current_user and not chat_session.user_id:
                chat_session.user_id = current_user.id

        # 2. Lưu tin nhắn của User vào Database
        user_msg = ChatMessage(
            session_id=chat_session.id,
            role="user",
            content=message.strip(),
            status="completed",
        )
        db.add(user_msg)
        db.flush()

        # 3. Lấy System Prompt và Tri thức bổ sung
        base_prompt, prompt_version_id = self.get_active_system_prompt(db, settings)
        knowledge_context = self.search_knowledge_context(db, message)

        product_context_str = ""
        if context_product:
            product_context_str = (
                f"\n=== SẢN PHẨM KHÁCH HÀNG ĐANG XEM ===\n"
                f"- Tên: {context_product.get('name', 'N/A')}\n"
                f"- Hoạt chất: {context_product.get('active_ingredient', 'N/A')}\n"
                f"- Quy cách: {context_product.get('packaging', 'N/A')}\n"
                f"- Giá: {context_product.get('price', 'N/A')}\n"
            )

        full_system_prompt = f"{base_prompt}\n{knowledge_context}\n{product_context_str}".strip()

        # 4. Xác định thứ tự Failover
        try:
            failover_list = json.loads(settings.failover_order)
            if not isinstance(failover_list, list):
                failover_list = ["gemini", "openai", "ollama", "h4care_expert"]
        except Exception:
            failover_list = ["gemini", "openai", "ollama", "h4care_expert"]

        # Đảm bảo active_provider đứng đầu tiên và h4care_expert luôn nằm ở cuối cùng
        active_prov = settings.active_provider or "gemini"
        ordered_providers = [active_prov]
        for p in failover_list:
            if p not in ordered_providers and p in self.providers:
                ordered_providers.append(p)
        if "h4care_expert" not in ordered_providers:
            ordered_providers.append("h4care_expert")

        history_for_llm = conversation_history or []

        # 5. Vòng lặp chuyển mạch Failover
        final_result: Optional[ProviderResult] = None
        attempt_records: List[ChatProviderAttempt] = []

        for attempt_idx, provider_id in enumerate(ordered_providers, start=1):
            provider = self.providers.get(provider_id)
            if not provider:
                continue

            target_model = settings.active_model if provider_id == active_prov else None

            attempt_start_time = datetime.now(UTC)
            perf_start = time.perf_counter()

            try:
                res: ProviderResult = await provider.generate_response(
                    system_prompt=full_system_prompt,
                    user_message=message,
                    conversation_history=history_for_llm,
                    model=target_model,
                    temperature=settings.temperature,
                    max_tokens=settings.max_output_tokens,
                    timeout_seconds=settings.timeout_seconds,
                )
            except Exception as e:
                latency = int((time.perf_counter() - perf_start) * 1000)
                res = ProviderResult(
                    text="",
                    provider=provider_id,
                    model=target_model or "unknown",
                    latency_ms=latency,
                    http_status=500,
                    result="server_error",
                    safe_error_message=f"Lỗi không xác định: {type(e).__name__}",
                )

            # Ghi nhận lần thử ChatProviderAttempt
            attempt = ChatProviderAttempt(
                message_id=None,  # Sẽ gắn sau khi có assistant_msg
                session_id=chat_session.id,
                provider=res.provider,
                model=res.model,
                attempt_number=attempt_idx,
                started_at=attempt_start_time,
                finished_at=datetime.now(UTC),
                latency_ms=res.latency_ms,
                http_status=res.http_status,
                result=res.result,
                safe_error_message=res.safe_error_message,
                correlation_id=correlation_id,
            )
            attempt_records.append(attempt)

            if res.result == "success" and res.text.strip():
                final_result = res
                break
            else:
                logger.warning(
                    f"[Chatbot Failover] Provider {provider_id} thất bại ({res.result}: {res.safe_error_message}). Chuyển sang provider tiếp theo..."
                )

        # 6. Nếu tất cả đều lỗi (hiếm gặp vì có h4care_expert), ép gọi H4CareExpert fallback
        if not final_result or not final_result.text.strip():
            expert = self.providers["h4care_expert"]
            final_result = await expert.generate_response(
                system_prompt=full_system_prompt,
                user_message=message,
                conversation_history=history_for_llm,
            )

        total_latency = int((time.perf_counter() - start_total) * 1000)

        # 7. Lưu tin nhắn của Assistant vào Database
        assistant_msg = ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            content=final_result.text.strip(),
            status="completed",
            provider=final_result.provider,
            model=final_result.model,
            prompt_version_id=prompt_version_id,
            latency_ms=final_result.latency_ms,
            input_token_count=final_result.input_tokens,
            output_token_count=final_result.output_tokens,
            finish_reason=final_result.finish_reason,
            safety_flags=json.dumps(final_result.safety_flags) if final_result.safety_flags else None,
            citations=json.dumps(final_result.citations) if final_result.citations else None,
        )
        db.add(assistant_msg)
        db.flush()

        # Gắn message_id cho các lần thử attempt
        for att in attempt_records:
            att.message_id = assistant_msg.id
            db.add(att)

        # Cập nhật số lượng tin nhắn và thời gian của Session
        chat_session.message_count = (chat_session.message_count or 0) + 2
        chat_session.last_message_at = datetime.now(UTC)

        db.commit()

        # Tạo danh sách hành động đề xuất
        suggested_actions = ["Hỏi thêm về liều dùng", "Tác dụng phụ", "Gặp Dược sĩ chuyên môn"]
        if final_result.safety_flags:
            suggested_actions = ["Gọi Cấp cứu 115", "Đến bệnh viện gần nhất", "Hotline Dược sĩ 1800 6828"]

        return {
            "response": assistant_msg.content,
            "session_id": chat_session.id,
            "message_id": assistant_msg.id,
            "provider": assistant_msg.provider,
            "model": assistant_msg.model,
            "latency_ms": assistant_msg.latency_ms or total_latency,
            "total_latency_ms": total_latency,
            "safety_flags": final_result.safety_flags,
            "suggested_actions": suggested_actions,
            "suggested_products": final_result.citations or [],
            "attempt_count": len(attempt_records),
            "correlation_id": correlation_id,
        }


# Singleton instance
orchestrator = ChatbotOrchestrator()
