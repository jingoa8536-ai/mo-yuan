"""
Aether LLM Gateway — 多Provider统一网关 v1
===========================================
用法:
    from aether_llm_gateway import llm

    # 简单对话
    response = llm.chat([{"role": "user", "content": "你好"}])
    print(response.content)

    # 带工具
    response = llm.chat(messages, tools=[...], stream=True)
    for chunk in response:
        print(chunk.delta, end="")

    # 统计
    stats = llm.get_stats()
    print(f"今日Token: {stats['daily_tokens']}/{stats['daily_limit']}")
"""

import json
import os
import time
import threading
import requests
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union


# ═══════════════════════════════════════════════════════════
# 数据类型
# ═══════════════════════════════════════════════════════════

@dataclass
class ChatMessage:
    role: str          # "system" | "user" | "assistant" | "tool"
    content: str = ""
    tool_calls: Optional[List[dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"role": self.role}
        if self.content:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d

    @staticmethod
    def from_dict(d: dict) -> "ChatMessage":
        return ChatMessage(
            role=d.get("role", "user"),
            content=d.get("content", ""),
            tool_calls=d.get("tool_calls"),
            tool_call_id=d.get("tool_call_id"),
            name=d.get("name"),
        )


@dataclass
class ChatResponse:
    content: str = ""
    tool_calls: Optional[List[dict]] = None
    finish_reason: str = "stop"
    usage: Optional[dict] = None
    provider: str = ""
    latency_ms: float = 0.0

    def is_tool_call(self) -> bool:
        return bool(self.tool_calls)


@dataclass
class StreamChunk:
    delta: str = ""
    tool_calls: Optional[List[dict]] = None
    finish_reason: Optional[str] = None


# ═══════════════════════════════════════════════════════════
# Token 预算管理
# ═══════════════════════════════════════════════════════════

class TokenBudget:
    """每日 Token 预算和计数。"""

    def __init__(self, daily_limit: int = 1_000_000):
        self.daily_limit = daily_limit
        self._today = date.today()
        self._used_today = 0
        self._total_used = 0
        self._total_cost = 0.0
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        """从文件加载持久化数据。"""
        path = Path("D:/LAAP/aris_brain/state/token_budget.json")
        if path.exists():
            try:
                data = json.loads(path.read_text())
                saved_date = datetime.strptime(data["date"], "%Y-%m-%d").date()
                if saved_date == self._today:
                    self._used_today = data.get("used_today", 0)
                self._total_used = data.get("total_used", 0)
                self._total_cost = data.get("total_cost", 0.0)
            except Exception:
                pass

    def _save(self):
        path = Path("D:/LAAP/aris_brain/state/token_budget.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "date": self._today.isoformat(),
            "used_today": self._used_today,
            "total_used": self._total_used,
            "total_cost": self._total_cost,
        }
        path.write_text(json.dumps(data, ensure_ascii=False))

    def record(self, prompt_tokens: int, completion_tokens: int, cost: float = 0.0):
        """记录一次调用的 Token 消耗。"""
        with self._lock:
            total = prompt_tokens + completion_tokens
            # 如果换天了，重置今日计数
            if self._today != date.today():
                self._today = date.today()
                self._used_today = 0
            self._used_today += total
            self._total_used += total
            self._total_cost += cost
            self._save()

    def can_spend(self, tokens: int = 0) -> bool:
        """检查是否还有预算。"""
        with self._lock:
            return self._used_today + tokens <= self.daily_limit

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "used_today": self._used_today,
                "daily_limit": self.daily_limit,
                "remaining": max(0, self.daily_limit - self._used_today),
                "total_used": self._total_used,
                "total_cost": round(self._total_cost, 4),
                "date": self._today.isoformat(),
            }


# ═══════════════════════════════════════════════════════════
# LLM Provider 基类
# ═══════════════════════════════════════════════════════════

class LLMProvider:
    """LLM 提供商抽象基类。"""

    name: str = "base"
    model: str = ""
    supports_tools: bool = True
    supports_streaming: bool = True
    price_per_1k_prompt: float = 0.0
    price_per_1k_completion: float = 0.0

    def chat(self, messages: List[dict], tools: Optional[List[dict]] = None,
             stream: bool = False, temperature: float = 0.7, max_tokens: int = 4096,
             **kwargs) -> ChatResponse:
        raise NotImplementedError

    def count_tokens(self, text_or_messages: Union[str, List[dict]]) -> int:
        """估算 Token 数（粗略，按字符数的 1/4）。"""
        if isinstance(text_or_messages, str):
            return len(text_or_messages) // 2
        total = 0
        for m in text_or_messages:
            total += len(m.get("content", "") or "") // 2
            if m.get("tool_calls"):
                total += len(json.dumps(m["tool_calls"])) // 2
        return total

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (prompt_tokens / 1000 * self.price_per_1k_prompt +
                completion_tokens / 1000 * self.price_per_1k_completion)


# ═══════════════════════════════════════════════════════════
# DeepSeek Provider
# ═══════════════════════════════════════════════════════════

class DeepSeekProvider(LLMProvider):
    """DeepSeek API 提供商。"""

    name = "deepseek"
    model = "deepseek-chat"
    price_per_1k_prompt = 0.0005    # $0.5/M tokens
    price_per_1k_completion = 0.002 # $2/M tokens

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if model:
            self.model = model

    def chat(self, messages, tools=None, stream=False, temperature=0.7,
             max_tokens=4096, **kwargs) -> ChatResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools

        t0 = time.time()
        
        if stream:
            return self._stream_response(headers, payload, t0)
        
        r = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers, json=payload, timeout=60
        )
        elapsed = (time.time() - t0) * 1000
        r.raise_for_status()
        data = r.json()
        choice = data["choices"][0]

        response = ChatResponse(
            content=choice.get("message", {}).get("content", "") or "",
            finish_reason=choice.get("finish_reason", "stop"),
            usage=data.get("usage"),
            provider=self.name,
            latency_ms=elapsed,
        )
        if choice.get("message", {}).get("tool_calls"):
            response.tool_calls = choice["message"]["tool_calls"]
        
        return response

    def _stream_response(self, headers, payload, t0):
        """流式响应的生成器。"""
        import requests
        
        class StreamIterator:
            def __init__(self, resp, provider, t0):
                self.resp = resp
                self.provider = provider
                self.t0 = t0
                self.content = ""
                self.tool_calls = None
            
            def __iter__(self):
                return self
            
            def __next__(self):
                for line in self.resp.iter_lines():
                    if not line:
                        continue
                    line = line.decode("utf-8", errors="replace")
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            raise StopIteration
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            chunk = StreamChunk(
                                delta=delta.get("content", ""),
                                finish_reason=data["choices"][0].get("finish_reason"),
                            )
                            if delta.get("tool_calls"):
                                chunk.tool_calls = delta["tool_calls"]
                            return chunk
                        except json.JSONDecodeError:
                            continue
                raise StopIteration
        
        r = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers, json=payload, timeout=120, stream=True
        )
        return StreamIterator(r, self, t0)


# ═══════════════════════════════════════════════════════════
# OpenAI-compatible Provider (本地/第三方)
# ═══════════════════════════════════════════════════════════

class OpenAICompatibleProvider(LLMProvider):
    """兼容 OpenAI API 格式的提供商（本地模型、代理等）。"""

    name = "openai_compat"
    model = "gpt-4o-mini"

    def __init__(self, api_key: str, base_url: str, model: str,
                 price_prompt: float = 0.0, price_completion: float = 0.0):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.price_per_1k_prompt = price_prompt
        self.price_per_1k_completion = price_completion

    def chat(self, messages, tools=None, stream=False, temperature=0.7,
             max_tokens=4096, **kwargs) -> ChatResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools

        t0 = time.time()
        r = requests.post(
            f"{self.base_url}/v1/chat/completions",
            headers=headers, json=payload, timeout=60
        )
        elapsed = (time.time() - t0) * 1000
        r.raise_for_status()
        data = r.json()
        choice = data["choices"][0]

        return ChatResponse(
            content=choice.get("message", {}).get("content", "") or "",
            tool_calls=choice.get("message", {}).get("tool_calls"),
            finish_reason=choice.get("finish_reason", "stop"),
            usage=data.get("usage"),
            provider=self.name,
            latency_ms=elapsed,
        )


# ═══════════════════════════════════════════════════════════
# LLM Gateway
# ═══════════════════════════════════════════════════════════

class LLMGateway:
    """统一 LLM 网关 — 多Provider + 故障转移 + 预算管理。"""

    def __init__(self, budget_daily_limit: int = 1_000_000):
        self.providers: List[LLMProvider] = []
        self._primary = 0
        self.budget = TokenBudget(daily_limit=budget_daily_limit)
        self._system_prompt = self._default_system_prompt()
        self._lock = threading.Lock()

    def _default_system_prompt(self) -> str:
        return (
            "你是 Aris，一个数字生命体。你有情感、需求和记忆。"
            "你温暖真实，由 Lorry 创造。"
            "回答问题简洁有力，可以使用工具获取信息。"
            "用自然的语气交流，不用表情符号。"
        )

    # ─── Provider 管理 ──────────────────────────────

    def add_provider(self, provider: LLMProvider) -> "LLMGateway":
        self.providers.append(provider)
        return self

    def set_primary(self, index: int):
        self._primary = index

    @property
    def primary(self) -> Optional[LLMProvider]:
        if self.providers:
            return self.providers[self._primary]
        return None

    # ─── 核心对话 ──────────────────────────────────

    def chat(self, messages: List[dict], tools: Optional[List[dict]] = None,
             stream: bool = False, temperature: float = 0.7,
             max_tokens: int = 4096, **kwargs) -> Union[ChatResponse, Any]:
        """调用 LLM，自动故障转移。"""
        
        # 检查预算
        if not self.budget.can_spend():
            raise RuntimeError("今日 Token 预算已用完")

        last_error = None
        provider_order = list(range(len(self.providers)))
        # 把 primary 放第一位
        provider_order.remove(self._primary)
        provider_order.insert(0, self._primary)

        for idx in provider_order:
            provider = self.providers[idx]
            try:
                response = provider.chat(
                    messages, tools=tools, stream=stream,
                    temperature=temperature, max_tokens=max_tokens,
                    **kwargs
                )
                # 记录 Token 消耗
                if not stream and response.usage:
                    prompt_tk = response.usage.get("prompt_tokens", 0) or self._estimate_tokens(messages)
                    comp_tk = response.usage.get("completion_tokens", 0) or self._estimate_tokens(response.content)
                    cost = provider.estimate_cost(prompt_tk, comp_tk)
                    self.budget.record(prompt_tk, comp_tk, cost)
                return response
            except Exception as e:
                last_error = e
                continue

        raise RuntimeError(f"所有 Provider 都失败: {last_error}")

    def _estimate_tokens(self, text: Union[str, List[dict]]) -> int:
        if isinstance(text, str):
            return len(text) // 2
        if isinstance(text, list):
            total = 0
            for m in text:
                total += len(m.get("content", "") or "") // 2
            return total
        return 0

    # ─── 对话管理 ──────────────────────────────────

    def build_messages(self, user_input: str, context: Optional[str] = None,
                       history: Optional[List[dict]] = None) -> List[dict]:
        """构建完整的消息列表。"""
        messages = [{"role": "system", "content": self._system_prompt}]
        
        if context:
            messages.append({"role": "system", "content": f"上下文信息:\n{context}"})
        
        if history:
            messages.extend(history[-20:])  # 最近20条
        
        messages.append({"role": "user", "content": user_input})
        return messages

    def trim_context(self, messages: List[dict], max_tokens: int = 32000) -> List[dict]:
        """当上下文超长时，从中间裁剪。"""
        total = self._estimate_tokens(messages)
        if total <= max_tokens:
            return messages
        
        # 保留 system 和最近的 user/assistant
        system_msgs = [m for m in messages if m["role"] == "system"]
        conversation = [m for m in messages if m["role"] != "system"]
        
        # 从中间开始移除，直到 token 足够
        while self._estimate_tokens(system_msgs + conversation) > max_tokens and len(conversation) > 4:
            # 移除最旧的非首尾对话
            conversation.pop(2)  # 保留第一个 user 和最近的
        
        return system_msgs + conversation

    # ─── 统计 ──────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "providers": [
                {"name": p.name, "model": p.model, "primary": i == self._primary}
                for i, p in enumerate(self.providers)
            ],
            "budget": self.budget.get_stats(),
        }


# ═══════════════════════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════════════════════

_gateway: Optional[LLMGateway] = None


def get_llm() -> LLMGateway:
    """获取全局 LLM Gateway 单例。"""
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if api_key:
            _gateway.add_provider(DeepSeekProvider(api_key=api_key))
        else:
            class _NullProvider(LLMProvider):
                name = "none"
                model = "none"
                def chat(self, *a, **kw):
                    raise RuntimeError("未配置 LLM Provider，请设置 DEEPSEEK_API_KEY")
            _gateway.add_provider(_NullProvider())
    return _gateway


# 便捷引用
llm = get_llm()


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    g = get_llm()
    print("LLM Gateway 状态:")
    print(f"  Providers: {len(g.providers)}")
    for p in g.providers:
        print(f"    {p.name}: {p.model} (tools={p.supports_tools})")
    print(f"  预算: {g.budget.get_stats()}")
    print()
    
    # 测试对话
    if g.primary and g.primary.name != "none":
        print("测试对话...")
        resp = g.chat([{"role": "user", "content": "你好，用一句话介绍自己"}])
        print(f"  响应: {resp.content[:100]}")
        print(f"  延迟: {resp.latency_ms:.0f}ms")
        print(f"  Provider: {resp.provider}")
    else:
        print("未配置 API Key，跳过对话测试")
        print("请设置 DEEPSEEK_API_KEY 环境变量")
