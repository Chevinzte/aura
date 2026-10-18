from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import httpx


class BackendAPIError(RuntimeError):
    """A stable error response or transport failure from the AURA backend."""

    def __init__(
        self,
        code: str,
        *,
        status_code: int | None = None,
        reference_id: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.reference_id = reference_id


class AuraBackendClient:
    """HTTP adapter used by Telegram; contains no AURA business logic."""

    def __init__(
        self,
        *,
        base_url: str,
        internal_api_key: str | None = None,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        headers = {"User-Agent": "aura-telegram-bot/0.1"}
        if internal_api_key:
            headers["Authorization"] = f"Bearer {internal_api_key}"
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
            headers=headers,
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

    async def get_preferences(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/v1/preferences",
            headers=self._identity_headers(telegram_user_id, display_name),
        )

    async def update_fashion_presentation(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        fashion_presentation: str,
    ) -> dict[str, Any]:
        return await self._request(
            "PUT",
            "/v1/preferences/fashion-presentation",
            headers=self._identity_headers(telegram_user_id, display_name),
            json={"fashion_presentation": fashion_presentation},
        )

    async def list_profile_items(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        page: int = 1,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/v1/profile/items",
            headers=self._identity_headers(telegram_user_id, display_name),
            params={"page": page},
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

    async def generate_suggestions(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        intent: str,
        category: str,
        count: int,
        exclude_labels: list[str],
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/suggestions",
            headers=self._identity_headers(telegram_user_id, display_name),
            json={
                "intent": intent,
                "category": category,
                "count": count,
                "exclude_labels": exclude_labels,
            },
        )

    async def list_wardrobe_items(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        page: int = 1,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/v1/wardrobe",
            headers=self._identity_headers(telegram_user_id, display_name),
            params={"page": page},
        )

    async def get_wardrobe_item(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/v1/wardrobe/items/{item_id}",
            headers=self._identity_headers(telegram_user_id, display_name),
        )

    async def get_wardrobe_item_image(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
    ) -> tuple[bytes, str]:
        return await self._request_bytes(
            "GET",
            f"/v1/wardrobe/items/{item_id}/image",
            headers=self._identity_headers(telegram_user_id, display_name),
        )

    async def get_correction_options(
        self,
        *,
        telegram_user_id: int,
    ) -> list[dict[str, Any]]:
        return await self._request_list(
            "GET",
            "/v1/wardrobe/correction-options",
            headers=self._identity_headers(telegram_user_id, None),
        )

    async def preview_item_correction(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
        field: str,
        values: list[str],
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/wardrobe/items/{item_id}/corrections/preview",
            headers=self._identity_headers(telegram_user_id, display_name),
            json={"field": field, "values": values},
        )

    async def apply_item_correction(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
        field: str,
        values: list[str],
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/wardrobe/items/{item_id}/corrections",
            headers=self._identity_headers(telegram_user_id, display_name),
            json={"field": field, "values": values},
        )

    async def preview_item_reanalysis(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/wardrobe/items/{item_id}/reanalysis/preview",
            headers=self._identity_headers(telegram_user_id, display_name),
        )

    async def confirm_item_reanalysis(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
        preview_id: UUID,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/wardrobe/items/{item_id}/reanalysis/{preview_id}/confirm",
            headers=self._identity_headers(telegram_user_id, display_name),
        )

    async def discard_item_reanalysis(
        self,
        *,
        telegram_user_id: int,
        display_name: str | None,
        item_id: UUID,
        preview_id: UUID,
    ) -> None:
        await self._raw_request(
            "DELETE",
            f"/v1/wardrobe/items/{item_id}/reanalysis/{preview_id}",
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
        reference_id = self._add_request_reference(kwargs)
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as error:
            raise BackendAPIError(
                "BACKEND_UNAVAILABLE",
                reference_id=reference_id,
            ) from error

        response_reference = response.headers.get("X-Request-ID", reference_id)
        if response.is_error:
            code = self._error_code(response)
            raise BackendAPIError(
                code,
                status_code=response.status_code,
                reference_id=response_reference,
            )
        try:
            payload = response.json()
        except ValueError as error:
            raise BackendAPIError(
                "INVALID_BACKEND_RESPONSE",
                status_code=response.status_code,
                reference_id=response_reference,
            ) from error
        if not isinstance(payload, dict):
            raise BackendAPIError(
                "INVALID_BACKEND_RESPONSE",
                status_code=response.status_code,
                reference_id=response_reference,
            )
        return payload

    async def _request_list(
        self, method: str, path: str, **kwargs: Any
    ) -> list[dict[str, Any]]:
        response = await self._raw_request(method, path, **kwargs)
        try:
            payload = response.json()
        except ValueError as error:
            raise BackendAPIError(
                "INVALID_BACKEND_RESPONSE",
                status_code=response.status_code,
                reference_id=response.headers.get("X-Request-ID"),
            ) from error
        if not isinstance(payload, list) or not all(
            isinstance(item, dict) for item in payload
        ):
            raise BackendAPIError(
                "INVALID_BACKEND_RESPONSE",
                status_code=response.status_code,
                reference_id=response.headers.get("X-Request-ID"),
            )
        return payload

    async def _request_bytes(
        self, method: str, path: str, **kwargs: Any
    ) -> tuple[bytes, str]:
        response = await self._raw_request(method, path, **kwargs)
        mime_type = response.headers.get("Content-Type", "application/octet-stream")
        return response.content, mime_type.split(";", 1)[0]

    async def _raw_request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        reference_id = self._add_request_reference(kwargs)
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as error:
            raise BackendAPIError(
                "BACKEND_UNAVAILABLE",
                reference_id=reference_id,
            ) from error
        if response.is_error:
            code = self._error_code(response)
            raise BackendAPIError(
                code,
                status_code=response.status_code,
                reference_id=response.headers.get("X-Request-ID", reference_id),
            )
        return response

    def _add_request_reference(self, kwargs: dict[str, Any]) -> str:
        reference_id = uuid4().hex[:12].upper()
        headers = dict(kwargs.get("headers") or {})
        headers["X-Request-ID"] = reference_id
        kwargs["headers"] = headers
        return reference_id

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
