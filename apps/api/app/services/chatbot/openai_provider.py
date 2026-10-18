from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.services.chatbot.base import BaseChatProvider, ProviderResult, ProviderStatus


class OpenAIChatProvider(BaseChatProvider):
    """
    Adapter cho OpenAI (gpt-4o-mini, gpt-4o, gpt-3.5-turbo).
    Không bao giờ trả HTTP 401 ra ngoài; bắt lỗi xác thực và chuyển mạch an toàn.
    """

    def __init__(self):
        super().__init__(provider_id="openai", display_name="OpenAI")
        self.default_model = "gpt-4o-mini"

    def _get_api_key(self) -> str:
        return (
            os.environ.get("OPENAI_API_KEY")
            or getattr(settings, "openai_api_key", None)
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
                provider="openai",
                model=target_model,
                latency_ms=latency,
                http_status=401,
                result="auth_error",
                safe_error_message="OpenAI API Key chưa được cấu hình trên máy chủ.",
            )

        url = "https://api.openai.com/v1/chat/completions"
        messages = [{"role": "system", "content": system_prompt}]

        for msg in conversation_history[-8:]:
            role = msg.get("role", "user")
            content = msg.get("content", "").strip()
            if content and role in ("user", "assistant", "system"):
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=float(timeout_seconds)) as client:
                res = await client.post(url, json=payload, headers=headers)
                latency = int((time.perf_counter() - start_time) * 1000)

                if res.status_code == 200:
                    data = res.json()
                    choices = data.get("choices", [])
                    if not choices:
                        return ProviderResult(
                            text="",
                            provider="openai",
                            model=target_model,
                            latency_ms=latency,
                            http_status=200,
                            result="blocked",
                            safe_error_message="OpenAI không trả về kết quả hợp lệ.",
                        )

                    choice = choices[0]
                    reply_text = choice.get("message", {}).get("content", "").strip()
                    finish_reason = choice.get("finish_reason", "stop")
                    usage = data.get("usage", {})

                    return ProviderResult(
                        text=reply_text,
                        provider="openai",
                        model=target_model,
                        latency_ms=latency,
                        http_status=200,
                        result="success",
                        input_tokens=usage.get("prompt_tokens"),
                        output_tokens=usage.get("completion_tokens"),
                        finish_reason=finish_reason,
                    )

                if res.status_code == 401:
                    return ProviderResult(
                        text="",
                        provider="openai",
                        model=target_model,
                        latency_ms=latency,
                        http_status=401,
                        result="auth_error",
                        safe_error_message="Khóa OpenAI API không hợp lệ hoặc đã hết hạn.",
                    )

                if res.status_code == 429:
                    return ProviderResult(
                        text="",
                        provider="openai",
                        model=target_model,
                        latency_ms=latency,
                        http_status=429,
                        result="rate_limited",
                        safe_error_message="OpenAI API vượt hạn mức tần suất (Rate limit).",
                    )

                return ProviderResult(
                    text="",
                    provider="openai",
                    model=target_model,
                    latency_ms=latency,
                    http_status=res.status_code,
                    result="server_error",
                    safe_error_message=f"OpenAI API trả về lỗi HTTP {res.status_code}.",
                )

        except httpx.TimeoutException:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ProviderResult(
                text="",
                provider="openai",
                model=target_model,
                latency_ms=latency,
                http_status=408,
                result="timeout",
                safe_error_message=f"Hết thời gian chờ phản hồi OpenAI ({timeout_seconds}s).",
            )
        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ProviderResult(
                text="",
                provider="openai",
                model=target_model,
                latency_ms=latency,
                http_status=500,
                result="server_error",
                safe_error_message=f"Lỗi kết nối OpenAI: {type(e).__name__}",
            )

    async def check_health(self) -> ProviderStatus:
        api_key = self._get_api_key()
        models = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
        if not api_key:
            return ProviderStatus(
                provider="openai",
                name="OpenAI",
                is_configured=False,
                is_healthy=False,
                available_models=models,
                error_message="Chưa cấu hình OPENAI_API_KEY trong môi trường máy chủ.",
            )

        start = time.perf_counter()
        try:
            url = "https://api.openai.com/v1/models"
            headers = {"Authorization": f"Bearer {api_key}"}
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(url, headers=headers)
                latency = int((time.perf_counter() - start) * 1000)
                if res.status_code == 200:
                    data = res.json()
                    found = [
                        m["id"]
                        for m in data.get("data", [])
                        if m.get("id", "").startswith(("gpt-4", "gpt-3.5"))
                    ]
                    return ProviderStatus(
                        provider="openai",
                        name="OpenAI",
                        is_configured=True,
                        is_healthy=True,
                        available_models=found[:10] if found else models,
                        latency_ms=latency,
                    )
                return ProviderStatus(
                    provider="openai",
                    name="OpenAI",
                    is_configured=True,
                    is_healthy=False,
                    available_models=models,
                    latency_ms=latency,
                    error_message=f"Lỗi HTTP {res.status_code} khi kiểm tra OpenAI.",
                )
        except Exception as e:
            latency = int((time.perf_counter() - start) * 1000)
            return ProviderStatus(
                provider="openai",
                name="OpenAI",
                is_configured=True,
                is_healthy=False,
                available_models=models,
                latency_ms=latency,
                error_message=str(e),
            )
