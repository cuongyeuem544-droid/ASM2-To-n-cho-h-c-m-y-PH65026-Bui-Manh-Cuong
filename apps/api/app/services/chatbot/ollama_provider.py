from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.services.chatbot.base import BaseChatProvider, ProviderResult, ProviderStatus


ALLOWED_OLLAMA_HOSTS = {
    "localhost",
    "127.0.0.1",
    "host.docker.internal",
    "0.0.0.0",
}


def is_safe_ollama_url(url: str) -> bool:
    """Kiểm tra URL Ollama ngăn chặn tấn công SSRF."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = (parsed.hostname or "").lower()
        if hostname in ALLOWED_OLLAMA_HOSTS:
            return True
        # Cho phép private subnet an toàn nếu cấu hình nội bộ
        if hostname.startswith("192.168.") or hostname.startswith("10.") or hostname.startswith("172."):
            return True
        return False
    except Exception:
        return False


class OllamaChatProvider(BaseChatProvider):
    """
    Adapter cho Ollama Local (qwen2.5:3b, llama3.2...).
    Có bảo vệ SSRF tuyệt đối không gọi ra IP nguy hại.
    """

    def __init__(self):
        super().__init__(provider_id="ollama", display_name="Ollama Local LLM")
        self.default_model = getattr(settings, "ollama_model", "qwen2.5:3b")

    def _get_base_url(self) -> str:
        url = (
            os.environ.get("OLLAMA_BASE_URL")
            or getattr(settings, "ollama_base_url", "http://localhost:11434")
        ).strip()
        if not is_safe_ollama_url(url):
            return "http://localhost:11434"
        return url.rstrip("/")

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
        base_url = self._get_base_url()

        if not is_safe_ollama_url(base_url):
            latency = int((time.perf_counter() - start_time) * 1000)
            return ProviderResult(
                text="",
                provider="ollama",
                model=target_model,
                latency_ms=latency,
                http_status=400,
                result="blocked",
                safe_error_message="OLLAMA_BASE_URL không hợp lệ hoặc bị chặn bởi bộ lọc bảo mật SSRF.",
            )

        endpoint = f"{base_url}/api/chat"
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
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=float(timeout_seconds)) as client:
                res = await client.post(endpoint, json=payload)
                latency = int((time.perf_counter() - start_time) * 1000)

                if res.status_code == 200:
                    data = res.json()
                    msg = data.get("message", {})
                    reply_text = msg.get("content", "").strip()

                    return ProviderResult(
                        text=reply_text,
                        provider="ollama",
                        model=target_model,
                        latency_ms=latency,
                        http_status=200,
                        result="success",
                        input_tokens=data.get("prompt_eval_count"),
                        output_tokens=data.get("eval_count"),
                        finish_reason="stop",
                    )

                return ProviderResult(
                    text="",
                    provider="ollama",
                    model=target_model,
                    latency_ms=latency,
                    http_status=res.status_code,
                    result="server_error",
                    safe_error_message=f"Ollama trả về mã lỗi HTTP {res.status_code}.",
                )

        except httpx.ConnectError:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ProviderResult(
                text="",
                provider="ollama",
                model=target_model,
                latency_ms=latency,
                http_status=503,
                result="server_error",
                safe_error_message="Không thể kết nối đến máy chủ Ollama local (Dịch vụ chưa chạy).",
            )
        except httpx.TimeoutException:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ProviderResult(
                text="",
                provider="ollama",
                model=target_model,
                latency_ms=latency,
                http_status=408,
                result="timeout",
                safe_error_message=f"Hết thời gian chờ phản hồi từ Ollama ({timeout_seconds}s).",
            )
        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ProviderResult(
                text="",
                provider="ollama",
                model=target_model,
                latency_ms=latency,
                http_status=500,
                result="server_error",
                safe_error_message=f"Lỗi Ollama: {type(e).__name__}",
            )

    async def check_health(self) -> ProviderStatus:
        base_url = self._get_base_url()
        models = [self.default_model]

        if not is_safe_ollama_url(base_url):
            return ProviderStatus(
                provider="ollama",
                name="Ollama Local LLM",
                is_configured=False,
                is_healthy=False,
                available_models=models,
                error_message="URL Ollama không nằm trong danh sách máy chủ an toàn cho phép.",
            )

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{base_url}/api/tags")
                latency = int((time.perf_counter() - start) * 1000)
                if res.status_code == 200:
                    data = res.json()
                    found = [m.get("name") for m in data.get("models", []) if m.get("name")]
                    return ProviderStatus(
                        provider="ollama",
                        name="Ollama Local LLM",
                        is_configured=True,
                        is_healthy=True,
                        available_models=found if found else models,
                        latency_ms=latency,
                    )
                return ProviderStatus(
                    provider="ollama",
                    name="Ollama Local LLM",
                    is_configured=True,
                    is_healthy=False,
                    available_models=models,
                    latency_ms=latency,
                    error_message=f"Lỗi HTTP {res.status_code} khi kiểm tra Ollama.",
                )
        except Exception as e:
            latency = int((time.perf_counter() - start) * 1000)
            return ProviderStatus(
                provider="ollama",
                name="Ollama Local LLM",
                is_configured=True,
                is_healthy=False,
                available_models=models,
                latency_ms=latency,
                error_message=f"Không thể kết nối máy chủ Ollama ({type(e).__name__}).",
            )
