from __future__ import annotations

import abc

import httpx

from src.services.exceptions import AITimeoutError


class AIClient(abc.ABC):
    @abc.abstractmethod
    async def complete(self, messages: list[dict], model: str) -> str: ...

    async def __aenter__(self) -> AIClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        pass


class AnthropicClient(AIClient):
    def __init__(self, api_key: str, timeout: float = 60.0) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.anthropic.com",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=timeout,
        )

    async def complete(self, messages: list[dict], model: str) -> str:
        system = ""
        non_system: list[dict] = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                non_system.append(msg)

        body: dict = {
            "model": model,
            "max_tokens": 4096,
            "messages": non_system,
        }
        if system:
            body["system"] = system

        try:
            response = await self._client.post("/v1/messages", json=body)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AITimeoutError(
                f"Anthropic request timed out: {exc}"
            ) from exc

        data = response.json()
        return data["content"][0]["text"]

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self._client.aclose()


class OpenAIClient(AIClient):
    def __init__(self, api_key: str, timeout: float = 60.0) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def complete(self, messages: list[dict], model: str) -> str:
        body = {
            "model": model,
            "messages": messages,
        }

        try:
            response = await self._client.post("/v1/chat/completions", json=body)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AITimeoutError(
                f"OpenAI request timed out: {exc}"
            ) from exc

        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self._client.aclose()


def create_ai_client(provider: str, api_key: str, timeout: float = 60.0) -> AIClient:
    provider = provider.lower()
    if provider == "anthropic":
        return AnthropicClient(api_key, timeout=timeout)
    if provider == "openai":
        return OpenAIClient(api_key, timeout=timeout)
    raise ValueError(f"Unknown AI provider: {provider!r}")
