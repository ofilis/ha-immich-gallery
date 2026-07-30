"""Tests for the privacy-sensitive Immich API client."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from custom_components.immich_gallery.api import (
    ImageTooLarge,
    ImmichApiClient,
    InvalidResponse,
    InvalidUrlError,
    MissingPermission,
    normalize_base_url,
)
from custom_components.immich_gallery.const import MAX_IMAGE_BYTES
from custom_components.immich_gallery.models import GallerySource, SourceKind

ASSET_ID_1 = "11111111-1111-4111-8111-111111111111"
ASSET_ID_2 = "22222222-2222-4222-8222-222222222222"
ASSET_ID_3 = "33333333-3333-4333-8333-333333333333"
ASSET_ID_4 = "44444444-4444-4444-8444-444444444444"
ASSET_ID_5 = "55555555-5555-4555-8555-555555555555"
ASSET_ID_6 = "66666666-6666-4666-8666-666666666666"
ALBUM_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


class FakeContent:
    """Minimal streamed response content."""

    def __init__(self, chunks: tuple[bytes, ...]) -> None:
        """Store response chunks."""
        self._chunks = chunks

    async def iter_chunked(self, size: int) -> AsyncIterator[bytes]:
        """Yield the configured response chunks."""
        for chunk in self._chunks:
            yield chunk


class FakeResponse:
    """Minimal aiohttp response context manager."""

    def __init__(
        self,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
        payload: Any = None,
        chunks: tuple[bytes, ...] = (),
        content_length: int | None = None,
    ) -> None:
        """Initialize a fake response."""
        self.status = status
        self.headers = headers or {}
        self._payload = payload
        self.content = FakeContent(chunks)
        self.content_length = content_length

    async def __aenter__(self) -> FakeResponse:
        """Enter the response context."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit the response context."""

    async def json(self, *, content_type: str | None = None) -> Any:
        """Return the configured JSON payload."""
        return self._payload


class FakeSession:
    """Record requests and return queued fake responses."""

    def __init__(self, *responses: FakeResponse) -> None:
        """Initialize a fake session."""
        self._responses = list(responses)
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        """Record a request and return the next response."""
        self.requests.append((method, url, kwargs))
        return self._responses.pop(0)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://immich.example.com", "https://immich.example.com"),
        ("https://immich.example.com/", "https://immich.example.com"),
        ("https://immich.example.com/api", "https://immich.example.com"),
        ("http://192.168.1.42:2283/api/", "http://192.168.1.42:2283"),
        ("http://100.64.12.34:2283/api", "http://100.64.12.34:2283"),
        (
            "https://immich.my-tailnet.ts.net",
            "https://immich.my-tailnet.ts.net",
        ),
        (
            "http://[fd7a:115c:a1e0::1234]:2283/api",
            "http://[fd7a:115c:a1e0::1234]:2283",
        ),
        (
            "https://example.com/immich/api",
            "https://example.com/immich",
        ),
    ],
)
def test_normalize_base_url(raw: str, expected: str) -> None:
    """Root and /api URLs normalize to one stable origin."""
    assert normalize_base_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "ftp://immich.example.com",
        "https://user:password@immich.example.com",
        "https://immich.example.com?apiKey=secret",
        "https://immich.example.com/#fragment",
        "not a url",
    ],
)
def test_normalize_base_url_rejects_unsafe_values(raw: str) -> None:
    """Credentials and other leak-prone URL components are rejected."""
    with pytest.raises(InvalidUrlError):
        normalize_base_url(raw)


@pytest.mark.asyncio
async def test_favorites_search_uses_header_and_json_boolean() -> None:
    """The API key stays in a header and favorite search uses a JSON boolean."""
    session = FakeSession(
        FakeResponse(payload=[{"id": ASSET_ID_1, "type": "IMAGE"}]),
    )
    client = ImmichApiClient(
        session,  # type: ignore[arg-type]
        "https://immich.example.com",
        "private-key",
    )
    source = GallerySource(
        key="favorites",
        kind=SourceKind.FAVORITES,
        name="Random favorites",
    )

    asset = await client.async_get_random_asset(
        source,
        candidate_count=30,
    )

    assert asset.asset_id == ASSET_ID_1
    method, url, kwargs = session.requests[0]
    assert method == "POST"
    assert url == "https://immich.example.com/api/search/random"
    assert "private-key" not in url
    assert kwargs["headers"]["x-api-key"] == "private-key"
    assert kwargs["json"]["isFavorite"] is True
    assert kwargs["json"]["size"] == 30
    assert kwargs["allow_redirects"] is False


@pytest.mark.asyncio
async def test_album_search_uses_album_id_array() -> None:
    """Album random search sends the current Immich album filter shape."""
    session = FakeSession(
        FakeResponse(payload=[{"id": ASSET_ID_2, "type": "IMAGE"}]),
    )
    client = ImmichApiClient(
        session,  # type: ignore[arg-type]
        "https://immich.example.com",
        "private-key",
    )
    source = GallerySource(
        key=f"album:{ALBUM_ID}",
        kind=SourceKind.ALBUM,
        name="Family",
        album_id=ALBUM_ID,
    )

    await client.async_get_random_asset(
        source,
        candidate_count=30,
    )

    assert session.requests[0][2]["json"]["albumIds"] == [ALBUM_ID]


@pytest.mark.asyncio
async def test_randomization_avoids_recent_assets_when_possible() -> None:
    """A server-random batch is filtered against the per-source history."""
    session = FakeSession(
        FakeResponse(
            payload=[
                {"id": ASSET_ID_1, "type": "IMAGE"},
                {"id": ASSET_ID_2, "type": "IMAGE"},
                {"id": ASSET_ID_3, "type": "IMAGE"},
            ]
        ),
    )
    client = ImmichApiClient(
        session,  # type: ignore[arg-type]
        "https://immich.example.com",
        "private-key",
    )
    source = GallerySource(
        key="library",
        kind=SourceKind.LIBRARY,
        name="Random library",
    )

    asset = await client.async_get_random_asset(
        source,
        recent_asset_ids=(ASSET_ID_1, ASSET_ID_2),
        candidate_count=30,
    )

    assert asset.asset_id == ASSET_ID_3


@pytest.mark.asyncio
async def test_randomization_uses_oldest_candidate_after_full_cycle() -> None:
    """Small sources fall back to the least recently displayed candidate."""
    session = FakeSession(
        FakeResponse(
            payload=[
                {"id": ASSET_ID_1, "type": "IMAGE"},
                {"id": ASSET_ID_2, "type": "IMAGE"},
            ]
        ),
    )
    client = ImmichApiClient(
        session,  # type: ignore[arg-type]
        "https://immich.example.com",
        "private-key",
    )
    source = GallerySource(
        key="library",
        kind=SourceKind.LIBRARY,
        name="Random library",
    )

    asset = await client.async_get_random_asset(
        source,
        recent_asset_ids=(ASSET_ID_2, ASSET_ID_1),
        candidate_count=30,
    )

    assert asset.asset_id == ASSET_ID_2


@pytest.mark.asyncio
async def test_randomization_deduplicates_server_candidates() -> None:
    """Duplicate API rows cannot increase one asset's selection weight."""
    session = FakeSession(
        FakeResponse(
            payload=[
                {"id": ASSET_ID_5, "type": "IMAGE"},
                {"id": ASSET_ID_5, "type": "IMAGE"},
                {"id": ASSET_ID_6, "type": "IMAGE"},
            ]
        ),
    )
    client = ImmichApiClient(
        session,  # type: ignore[arg-type]
        "https://immich.example.com",
        "private-key",
    )
    source = GallerySource(
        key="library",
        kind=SourceKind.LIBRARY,
        name="Random library",
    )

    asset = await client.async_get_random_asset(
        source,
        recent_asset_ids=(ASSET_ID_5,),
        candidate_count=30,
    )

    assert asset.asset_id == ASSET_ID_6


@pytest.mark.asyncio
async def test_preview_is_bounded_and_redirects_are_disabled() -> None:
    """Preview downloads use a bounded stream and never follow redirects."""
    session = FakeSession(
        FakeResponse(
            headers={"Content-Type": "image/webp"},
            chunks=(b"first-", b"second"),
            content_length=12,
        ),
    )
    client = ImmichApiClient(
        session,  # type: ignore[arg-type]
        "https://immich.example.com",
        "private-key",
    )

    content, content_type = await client.async_download_preview(ASSET_ID_3)

    assert content == b"first-second"
    assert content_type == "image/webp"
    _, url, kwargs = session.requests[0]
    assert url == (f"https://immich.example.com/api/assets/{ASSET_ID_3}/thumbnail")
    assert kwargs["params"] == {"size": "preview"}
    assert kwargs["allow_redirects"] is False


@pytest.mark.asyncio
async def test_preview_rejects_oversized_content_length() -> None:
    """An oversized response is rejected before its body is buffered."""
    session = FakeSession(
        FakeResponse(
            headers={"Content-Type": "image/jpeg"},
            content_length=MAX_IMAGE_BYTES + 1,
        ),
    )
    client = ImmichApiClient(
        session,  # type: ignore[arg-type]
        "https://immich.example.com",
        "private-key",
    )

    with pytest.raises(ImageTooLarge):
        await client.async_download_preview(ASSET_ID_4)


@pytest.mark.asyncio
async def test_preview_reports_missing_asset_view_permission() -> None:
    """A forbidden preview reports the exact least-privilege permission."""
    session = FakeSession(FakeResponse(status=403))
    client = ImmichApiClient(
        session,  # type: ignore[arg-type]
        "https://immich.example.com",
        "private-key",
    )

    with pytest.raises(MissingPermission, match=r"asset\.view"):
        await client.async_download_preview(ASSET_ID_5)


@pytest.mark.asyncio
async def test_preview_rejects_path_injection_before_request() -> None:
    """A server-provided identifier can never alter the API request path."""
    session = FakeSession()
    client = ImmichApiClient(
        session,  # type: ignore[arg-type]
        "https://immich.example.com",
        "private-key",
    )

    with pytest.raises(InvalidResponse):
        await client.async_download_preview("../../users/me")

    assert session.requests == []
