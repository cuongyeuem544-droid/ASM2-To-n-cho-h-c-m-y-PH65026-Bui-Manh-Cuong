from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProviderResult:
    """Kết quả phản hồi từ một AI Provider."""
    text: str
    provider: str
    model: str
    latency_ms: int
    http_status: Optional[int] = 200
    result: str = "success"  # success, timeout, rate_limited, auth_error, server_error, blocked
    safe_error_message: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    finish_reason: Optional[str] = None
    safety_flags: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ProviderStatus:
    """Trạng thái hoạt động của Provider phục vụ Admin Dashboard."""
    provider: str
    name: str
    is_configured: bool
    is_healthy: bool
    available_models: List[str]
    latency_ms: Optional[int] = None
    error_message: Optional[str] = None


class BaseChatProvider(ABC):
    """Lớp cơ sở cho các AI Provider."""

    def __init__(self, provider_id: str, display_name: str):
        self.provider_id = provider_id
        self.display_name = display_name

    @abstractmethod
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
        """Sinh câu trả lời từ Provider."""
        raise NotImplementedError

    @abstractmethod
    async def check_health(self) -> ProviderStatus:
        """Kiểm tra kết nối và tính sẵn sàng của Provider."""
        raise NotImplementedError
