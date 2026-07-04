"""LLM client adapter interface and OpenAI-compatible implementation."""

import json
import os
from typing import Any

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None  # type: ignore[assignment,misc]


class LLMResponse:
    def __init__(self, text: str, tokens_in: int = 0, tokens_out: int = 0):
        self.text = text
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out


class LLMClient:
    async def complete(self, system: str, user: str) -> LLMResponse:
        raise NotImplementedError

    async def stream_complete(self, system: str, user: str, tools: list[dict] | None = None):
        raise NotImplementedError

    async def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
        raise NotImplementedError


class OpenAICompatClient(LLMClient):
    def __init__(self, base_url: str, model: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key) if AsyncOpenAI else None  # type: ignore[call-arg]

    async def complete(self, system: str, user: str) -> LLMResponse:
        if not self.client:
            return LLMResponse(text="Error: openai package not installed", tokens_in=0, tokens_out=0)
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.7,
                max_tokens=4096,
            )
            content = resp.choices[0].message.content or ""
            usage = resp.usage
            return LLMResponse(
                text=content,
                tokens_in=usage.prompt_tokens if usage else 0,
                tokens_out=usage.completion_tokens if usage else 0,
            )
        except Exception as e:
            return LLMResponse(text=f"LLM error: {e}", tokens_in=0, tokens_out=0)

    async def stream_complete(self, system: str, user: str, tools: list[dict] | None = None):  # type: ignore[override]
        if not self.client:
            yield "Error: openai package not installed"
            return
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": True,
                "temperature": 0.7,
                "max_tokens": 4096,
            }
            if tools:
                kwargs["tools"] = [json.dumps(t) if isinstance(t, dict) else t for t in tools]
            stream = await self.client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"Error: {e}"

    async def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
        if not self.client:
            return {"error": "openai package not installed"}
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                temperature=0.7,
                max_tokens=4096,
            )
            message = resp.choices[0].message
            result: dict[str, Any] = {
                "role": message.role,
                "content": message.content or "",
            }
            if hasattr(message, "tool_calls") and message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ]
            result["tokens_in"] = resp.usage.prompt_tokens if resp.usage else 0
            result["tokens_out"] = resp.usage.completion_tokens if resp.usage else 0
            return result
        except Exception as e:
            return {"error": str(e)}


class MockLLMClient(LLMClient):
    """Mock for testing - returns canned responses."""

    def __init__(self, canned_response: str = "Mock response"):
        self.canned_response = canned_response
        self.call_count = 0

    async def complete(self, system: str, user: str) -> LLMResponse:
        self.call_count += 1
        return LLMResponse(text=self.canned_response, tokens_in=len(user) // 4, tokens_out=10)

    async def stream_complete(self, system: str, user: str, tools: list[dict] | None = None):  # type: ignore[override]
        yield self.canned_response

    async def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
        self.call_count += 1
        return {"role": "assistant", "content": self.canned_response, "tokens_in": 0, "tokens_out": 10}


def create_llm_client(config: dict) -> LLMClient:
    protocol = config.get("protocol", "openai-compatible")
    base_url = os.environ.get("LLM_ENDPOINT_URL") or config.get("base_url") or "http://localhost:8000/v1"
    model = os.environ.get("LLM_MODEL") or config.get("model") or "gpt-4o"
    api_key = os.environ.get("LLM_API_KEY") or "sk-mock"
    if protocol == "mock":
        return MockLLMClient()
    return OpenAICompatClient(base_url=base_url, model=model, api_key=api_key)
