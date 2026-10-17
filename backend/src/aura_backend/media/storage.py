from __future__ import annotations

from typing import Protocol

from supabase import Client


class ImageStorage(Protocol):
    def upload(self, *, path: str, data: bytes, mime_type: str) -> None: ...

    def download(self, path: str) -> bytes: ...

    def delete(self, path: str) -> None: ...


class SupabaseImageStorage:
    """Store original item images in AURA's private Supabase bucket."""

    def __init__(self, client: Client, *, bucket: str = "item-images") -> None:
        self._bucket = client.storage.from_(bucket)

    def upload(self, *, path: str, data: bytes, mime_type: str) -> None:
        self._bucket.upload(
            path,
            data,
            {"content-type": mime_type, "upsert": "false"},
        )

    def download(self, path: str) -> bytes:
        return self._bucket.download(path)

    def delete(self, path: str) -> None:
        self._bucket.remove([path])
