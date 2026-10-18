from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.services.chatbot.base import BaseChatProvider, ProviderResult, ProviderStatus


class GeminiChatProvider(BaseChatProvider):
    """
    Adapter cho Google Gemini (gemini-1.5-flash, gemini-1.5-pro, gemini-2.0-flash).
    Không bao giờ trả HTTP 401 ra ngoài; bắt lỗi xác thực và chuyển mạch an toàn.
    """

    def __init__(self):
        super().__init__(provider_id="gemini", display_name="Google Gemini")
        self.default_model = "gemini-3.5-flash"

    def _get_api_key(self) -> str:
        return (
            os.environ.get("GEMINI_API_KEY")
            or getattr(settings, "gemini_api_key", None)
            or os.environ.get("AI_API_KEY")
            or getattr(settings, "ai_api_key", None)
            or ""
        ).strip()

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
        target_model = model or self.default_model
        api_key = self._get_api_key()

        if not api_key:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ProviderResult(
                text="",
                provider="gemini",
                model=target_model,
                latency_ms=latency,
                http_status=401,
                result="auth_error",
                safe_error_message="Google Gemini API Key chưa được cấu hình trên máy chủ.",
            )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"

        # Xây dựng contents theo chuẩn turn role của Gemini API
        contents = []
        for msg in conversation_history[-8:]:
            role = "model" if msg.get("role") == "assistant" else "user"
            content = msg.get("content", "").strip()
            if content:
                contents.append({"role": role, "parts": [{"text": content}]})

        contents.append({"role": "user", "parts": [{"text": user_message}]})

        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": 0.95,
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ],
        }

        async def _call_gemini(m_name: str) -> httpx.Response:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{m_name}:generateContent?key={api_key}"
            async with httpx.AsyncClient(timeout=float(timeout_seconds)) as client:
                return await client.post(endpoint, json=payload)

        try:
            res = await _call_gemini(target_model)
            # Tự động fallback sang gemini-3.5-flash nếu model được yêu cầu bị 404 do deprecated
            if res.status_code == 404 and target_model != "gemini-3.5-flash":
                fallback_res = await _call_gemini("gemini-3.5-flash")
                if fallback_res.status_code == 200:
                    res = fallback_res
                    target_model = "gemini-3.5-flash"

            latency = int((time.perf_counter() - start_time) * 1000)

            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    return ProviderResult(
                        text="",
                        provider="gemini",
                        model=target_model,
                        latency_ms=latency,
                        http_status=200,
                        result="blocked",
                        safe_error_message="Phản hồi bị chặn bởi bộ lọc an toàn Gemini.",
                    )

                candidate = candidates[0]
                finish_reason = candidate.get("finishReason", "STOP")
                parts = candidate.get("content", {}).get("parts", [])
                reply_text = "".join(part.get("text", "") for part in parts).strip()

                usage = data.get("usageMetadata", {})
                return ProviderResult(
                    text=reply_text,
                    provider="gemini",
                    model=target_model,
                    latency_ms=latency,
                    http_status=200,
                    result="success",
                    input_tokens=usage.get("promptTokenCount"),
                    output_tokens=usage.get("candidatesTokenCount"),
                    finish_reason=finish_reason,
                )

            if res.status_code in (401, 403):
                return ProviderResult(
                    text="",
                    provider="gemini",
                    model=target_model,
                    latency_ms=latency,
                    http_status=res.status_code,
                    result="auth_error",
                    safe_error_message="Khóa Gemini API không hợp lệ hoặc bị từ chối quyền truy cập.",
                )

            if res.status_code == 429:
                return ProviderResult(
                    text="",
                    provider="gemini",
                    model=target_model,
                    latency_ms=latency,
                    http_status=429,
                    result="rate_limited",
                    safe_error_message="Gemini API đạt giới hạn tần suất (Quota Exceeded).",
                )

            return ProviderResult(
                text="",
                provider="gemini",
                model=target_model,
                latency_ms=latency,
                http_status=res.status_code,
                result="server_error",
                safe_error_message=f"Gemini API phản hồi lỗi HTTP {res.status_code}.",
            )

        except httpx.TimeoutException:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ProviderResult(
                text="",
                provider="gemini",
                model=target_model,
                latency_ms=latency,
                http_status=408,
                result="timeout",
                safe_error_message=f"Hết thời gian chờ phản hồi Gemini ({timeout_seconds}s).",
            )
        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ProviderResult(
                text="",
                provider="gemini",
                model=target_model,
                latency_ms=latency,
                http_status=500,
                result="server_error",
                safe_error_message=f"Lỗi kết nối Gemini: {type(e).__name__}",
            )

    async def check_health(self) -> ProviderStatus:
        api_key = self._get_api_key()
        models = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-2.5-flash"]
        if not api_key:
            return ProviderStatus(
                provider="gemini",
                name="Google Gemini",
                is_configured=False,
                is_healthy=False,
                available_models=models,
                error_message="Chưa cấu hình GEMINI_API_KEY trong môi trường máy chủ.",
            )

        start = time.perf_counter()
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(url)
                latency = int((time.perf_counter() - start) * 1000)
                if res.status_code == 200:
                    data = res.json()
                    found_models = [
                        m["name"].replace("models/", "")
                        for m in data.get("models", [])
                        if "generateContent" in m.get("supportedGenerationMethods", [])
                        and ("gemini" in m.get("name", ""))
                    ]
                    return ProviderStatus(
                        provider="gemini",
                        name="Google Gemini",
                        is_configured=True,
                        is_healthy=True,
                        available_models=found_models[:10] if found_models else models,
                        latency_ms=latency,
                    )

                # Bóc tách lỗi chi tiết từ Google API
                err_detail = ""
                try:
                    err_json = res.json()
                    err_detail = err_json.get("error", {}).get("message", "")
                except Exception:
                    pass

                err_text = f"Lỗi HTTP {res.status_code}"
                if "API key not valid" in err_detail or "API_KEY_INVALID" in err_detail:
                    err_text += ": Khóa API Key không hợp lệ. Vui lòng kiểm tra lại khóa Gemini."
                elif err_detail:
                    err_text += f": {err_detail[:120]}"
                else:
                    err_text += " khi kiểm tra danh sách model."

                return ProviderStatus(
                    provider="gemini",
                    name="Google Gemini",
                    is_configured=True,
                    is_healthy=False,
                    available_models=models,
                    latency_ms=latency,
                    error_message=err_text,
                )
        except Exception as e:
            latency = int((time.perf_counter() - start) * 1000)
            return ProviderStatus(
                provider="gemini",
                name="Google Gemini",
                is_configured=True,
                is_healthy=False,
                available_models=models,
                latency_ms=latency,
                error_message=str(e),
            )
