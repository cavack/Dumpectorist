from typing import Any

import httpx


class HttpClient:
    def __init__(self, timeout_seconds: float = 10.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = timeout_seconds

    async def get_json_value(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        timeout = httpx.Timeout(self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = await self.get_json_value(url, params=params)
        if not isinstance(payload, dict):
            raise ValueError("expected object response")
        return payload
