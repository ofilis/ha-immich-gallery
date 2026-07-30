"""Small asynchronous client for the Immich endpoints used by this integration."""

from __future__ import annotations

import secrets
from typing import Any
from uuid import UUID

import aiohttp
from yarl import URL

from .const import API_TIMEOUT, IMAGE_TIMEOUT, MAX_IMAGE_BYTES
from .models import Album, AssetMetadata, GallerySource, SourceKind, ValidationResult

_API_KEY_HEADER = "x-api-key"
_ALLOWED_IMAGE_TYPES = frozenset(
    {
        "image/avif",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)


def _normalize_immich_id(value: Any) -> str | None:
    """Return a canonical UUID or reject an unsafe server-provided identifier."""
    if not isinstance(value, str):
        return None
    try:
        return str(UUID(value))
    except ValueError:
        return None


class ImmichGalleryError(Exception):
    """Base exception for Immich Gallery."""


class InvalidUrlError(ImmichGalleryError):
    """The configured URL is unsafe or invalid."""


class CannotConnect(ImmichGalleryError):
    """The configured Immich server cannot be reached."""


class InvalidAuth(ImmichGalleryError):
    """The Immich API key is invalid or revoked."""


class MissingPermission(ImmichGalleryError):
    """The API key does not have a required permission."""

    def __init__(self, permission: str) -> None:
        """Initialize the missing-permission error."""
        self.permission = permission
        super().__init__(permission)


class ApiError(ImmichGalleryError):
    """Immich returned an unexpected API error."""


class InvalidResponse(ImmichGalleryError):
    """Immich returned an invalid response."""


class NoAssets(ImmichGalleryError):
    """The configured source has no displayable images."""


class RateLimited(ImmichGalleryError):
    """Immich asked the client to reduce its request rate."""

    def __init__(self, retry_after: float = 60) -> None:
        """Initialize the rate-limit error."""
        self.retry_after = retry_after
        super().__init__("rate_limited")


class ImageTooLarge(ImmichGalleryError):
    """The returned preview exceeds the configured memory limit."""


class UnsupportedImage(ImmichGalleryError):
    """The returned preview has an unsupported media type."""


def normalize_base_url(raw_url: str) -> str:
    """Normalize an Immich root URL without retaining credentials or queries."""
    try:
        parsed = URL(raw_url.strip())
        port = parsed.port
    except (TypeError, ValueError) as err:
        raise InvalidUrlError from err

    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.host
        or parsed.user is not None
        or parsed.password is not None
        or parsed.query_string
        or parsed.fragment
    ):
        raise InvalidUrlError

    path = parsed.path.rstrip("/")
    if path.endswith("/api"):
        path = path[:-4].rstrip("/")

    try:
        normalized = URL.build(
            scheme=parsed.scheme,
            host=parsed.host,
            port=port,
            path=path or "/",
        )
    except ValueError as err:
        raise InvalidUrlError from err

    return str(normalized).rstrip("/")


class ImmichApiClient:
    """API client limited to the read-only calls required by the integration."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        api_key: str,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self.base_url = normalize_base_url(base_url)
        self._headers = {
            "Accept": "application/json",
            _API_KEY_HEADER: api_key,
        }

    def _url(self, path: str) -> str:
        """Build an API URL on the configured origin."""
        return f"{self.base_url}/api/{path.lstrip('/')}"

    @staticmethod
    def _retry_after(response: aiohttp.ClientResponse) -> float:
        """Return a bounded Retry-After value."""
        value = response.headers.get("Retry-After")
        try:
            parsed = float(value) if value is not None else 60
        except ValueError:
            return 60
        return min(max(parsed, 5), 3600)

    @staticmethod
    def _check_status(
        response: aiohttp.ClientResponse,
        permission: str | None,
    ) -> None:
        """Map HTTP status codes without reading or logging response bodies."""
        if response.status == 401:
            raise InvalidAuth
        if response.status == 403:
            raise MissingPermission(permission or "unknown")
        if response.status == 429:
            raise RateLimited(ImmichApiClient._retry_after(response))
        if response.status >= 500:
            raise CannotConnect
        if response.status < 200 or response.status >= 300:
            raise ApiError

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        permission: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        """Request JSON while refusing redirects to another origin."""
        request_kwargs: dict[str, Any] = {
            "allow_redirects": False,
            "headers": self._headers,
            "timeout": aiohttp.ClientTimeout(total=API_TIMEOUT),
        }
        if payload is not None:
            request_kwargs["json"] = payload

        try:
            async with self._session.request(
                method,
                self._url(path),
                **request_kwargs,
            ) as response:
                self._check_status(response, permission)
                try:
                    return await response.json(content_type=None)
                except (aiohttp.ContentTypeError, TypeError, ValueError) as err:
                    raise InvalidResponse from err
        except InvalidAuth, MissingPermission, RateLimited, ApiError, InvalidResponse:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CannotConnect from err

    async def async_get_server_version(self) -> str:
        """Return the Immich server version."""
        result = await self._request_json("GET", "server/version")
        if not isinstance(result, dict):
            raise InvalidResponse

        try:
            major = int(result["major"])
            minor = int(result["minor"])
            patch = int(result["patch"])
        except (KeyError, TypeError, ValueError) as err:
            raise InvalidResponse from err
        return f"{major}.{minor}.{patch}"

    async def async_get_current_user(self) -> tuple[str, str]:
        """Return the stable user ID and local display name."""
        result = await self._request_json(
            "GET",
            "users/me",
            permission="user.read",
        )
        if not isinstance(result, dict):
            raise InvalidResponse

        user_id = _normalize_immich_id(result.get("id"))
        user_name = result.get("name")
        if user_id is None:
            raise InvalidResponse
        return user_id, user_name if isinstance(user_name, str) else "Immich"

    async def async_get_albums(self) -> tuple[Album, ...]:
        """Return albums visible to the API-key owner."""
        result = await self._request_json(
            "GET",
            "albums",
            permission="album.read",
        )
        if not isinstance(result, list):
            raise InvalidResponse

        albums: list[Album] = []
        for item in result:
            if not isinstance(item, dict):
                continue
            album_id = _normalize_immich_id(item.get("id"))
            name = item.get("albumName")
            if album_id is not None and isinstance(name, str):
                albums.append(Album(album_id=album_id, name=name))
        return tuple(sorted(albums, key=lambda album: album.name.casefold()))

    async def _async_search_random(
        self,
        source: GallerySource,
        *,
        size: int,
    ) -> list[AssetMetadata]:
        """Return a small random batch for a source."""
        payload: dict[str, Any] = {
            "size": size,
            "type": "IMAGE",
        }
        if source.kind is SourceKind.FAVORITES:
            payload["isFavorite"] = True
        elif source.kind is SourceKind.ALBUM:
            if source.album_id is None:
                raise InvalidResponse
            payload["albumIds"] = [source.album_id]

        result = await self._request_json(
            "POST",
            "search/random",
            permission="asset.read",
            payload=payload,
        )
        if not isinstance(result, list):
            raise InvalidResponse

        assets_by_id: dict[str, AssetMetadata] = {}
        for item in result:
            if not isinstance(item, dict) or item.get("type") != "IMAGE":
                continue
            asset_id = _normalize_immich_id(item.get("id"))
            if asset_id is None:
                continue
            assets_by_id.setdefault(asset_id, AssetMetadata(asset_id=asset_id))
        return list(assets_by_id.values())

    async def async_get_random_asset(
        self,
        source: GallerySource,
        *,
        recent_asset_ids: tuple[str, ...] = (),
        candidate_count: int,
    ) -> AssetMetadata:
        """Choose uniformly from server-random candidates outside recent history."""
        assets = await self._async_search_random(source, size=candidate_count)
        if not assets:
            raise NoAssets

        recent_set = set(recent_asset_ids)
        alternatives = [asset for asset in assets if asset.asset_id not in recent_set]
        if alternatives:
            return secrets.choice(alternatives)

        if recent_asset_ids:
            recency = {
                asset_id: index for index, asset_id in enumerate(recent_asset_ids)
            }
            return min(
                assets,
                key=lambda asset: recency.get(asset.asset_id, -1),
            )

        return secrets.choice(assets)

    async def async_download_preview(self, asset_id: str) -> tuple[bytes, str]:
        """Download a bounded browser-safe preview image."""
        normalized_asset_id = _normalize_immich_id(asset_id)
        if normalized_asset_id is None:
            raise InvalidResponse

        try:
            async with self._session.request(
                "GET",
                self._url(f"assets/{normalized_asset_id}/thumbnail"),
                allow_redirects=False,
                headers=self._headers,
                params={"size": "preview"},
                timeout=aiohttp.ClientTimeout(total=IMAGE_TIMEOUT),
            ) as response:
                self._check_status(response, "asset.view")

                content_type = (
                    response.headers.get("Content-Type", "")
                    .partition(";")[0]
                    .strip()
                    .lower()
                )
                if content_type not in _ALLOWED_IMAGE_TYPES:
                    raise UnsupportedImage
                if (
                    response.content_length is not None
                    and response.content_length > MAX_IMAGE_BYTES
                ):
                    raise ImageTooLarge

                content = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    content.extend(chunk)
                    if len(content) > MAX_IMAGE_BYTES:
                        raise ImageTooLarge
                if not content:
                    raise InvalidResponse
                return bytes(content), content_type
        except (
            InvalidAuth,
            MissingPermission,
            RateLimited,
            ApiError,
            InvalidResponse,
            ImageTooLarge,
            UnsupportedImage,
        ):
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CannotConnect from err

    async def async_validate(self) -> ValidationResult:
        """Validate the server and all required read-only permissions."""
        server_version = await self.async_get_server_version()
        user_id, user_name = await self.async_get_current_user()
        albums = await self.async_get_albums()

        library = GallerySource(
            key="library",
            kind=SourceKind.LIBRARY,
            name="Random library",
        )
        assets = await self._async_search_random(library, size=1)
        if assets:
            await self.async_download_preview(assets[0].asset_id)

        return ValidationResult(
            user_id=user_id,
            user_name=user_name,
            server_version=server_version,
            albums=albums,
        )
