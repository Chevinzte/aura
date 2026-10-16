from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx


class BackendAPIError(RuntimeError):
    """A stable error response or transport failure from the AURA backend."""

    def __init__(self, code: str, *, status_code: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class AuraBackendClient:
    """HTTP adapter used by Telegram; contains no AURA business logic."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
            headers={"User-Agent": "aura-telegram-bot/0.1"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def upload_owned_item(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        image: bytes,
        filename: str,
        item_name: str | None,
    ) -> dict[str, Any]:
        return await self._upload_item(
            path="/v1/items/owned",
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            image=image,
            filename=filename,
            item_name=item_name,
        )

    async def upload_candidate_item(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        image: bytes,
        filename: str,
        item_name: str | None,
    ) -> dict[str, Any]:
        return await self._upload_item(
            path="/v1/items/candidates",
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            image=image,
            filename=filename,
            item_name=item_name,
        )

    async def submit_feedback(
        self,
        *,
        telegram_user_id: int,
        match_id: UUID,
        feedback_type: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/matches/{match_id}/feedback",
            headers=self._identity_headers(telegram_user_id, None),
            json={"feedback_type": feedback_type},
        )

    async def get_profile(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/v1/profile",
            headers=self._identity_headers(telegram_user_id, display_name),
        )

    async def list_profile_items(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/v1/profile/items",
            headers=self._identity_headers(telegram_user_id, display_name),
        )

    async def remove_profile_item(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
    ) -> dict[str, Any]:
        return await self._request(
            "DELETE",
            f"/v1/profile/items/{item_id}",
            headers=self._identity_headers(telegram_user_id, display_name),
        )

    async def reset_profile(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
    ) -> dict[str, Any]:
        return await self._request(
            "DELETE",
            "/v1/profile",
            headers=self._identity_headers(telegram_user_id, display_name),
        )

    async def _upload_item(
        self,
        *,
        path: str,
        telegram_user_id: int,
        display_name: str | None,
        image: bytes,
        filename: str,
        item_name: str | None,
    ) -> dict[str, Any]:
        data = {"item_name": item_name} if item_name else None
        return await self._request(
            "POST",
            path,
            headers=self._identity_headers(telegram_user_id, display_name),
            files={"file": (filename, image, "image/jpeg")},
            data=data,
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as error:
            raise BackendAPIError("BACKEND_UNAVAILABLE") from error

        if response.is_error:
            code = self._error_code(response)
            raise BackendAPIError(code, status_code=response.status_code)
        try:
            payload = response.json()
        except ValueError as error:
            raise BackendAPIError(
                "INVALID_BACKEND_RESPONSE",
                status_code=response.status_code,
            ) from error
        if not isinstance(payload, dict):
            raise BackendAPIError(
                "INVALID_BACKEND_RESPONSE",
                status_code=response.status_code,
            )
        return payload

    def _identity_headers(
        self,
        telegram_user_id: int,
        display_name: str | None,
    ) -> dict[str, str]:
        headers = {"X-Telegram-User-Id": str(telegram_user_id)}
        if display_name:
            headers["X-Telegram-Display-Name"] = display_name
        return headers

    def _error_code(self, response: httpx.Response) -> str:
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None
        return detail if isinstance(detail, str) else "BACKEND_REQUEST_FAILED"
