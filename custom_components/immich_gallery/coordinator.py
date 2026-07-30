"""Data coordinator for Immich Gallery."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ApiError,
    CannotConnect,
    ImageTooLarge,
    ImmichApiClient,
    InvalidAuth,
    InvalidResponse,
    MissingPermission,
    NoAssets,
    RateLimited,
    UnsupportedImage,
)
from .const import (
    CONF_ALBUM_IDS,
    CONF_INCLUDE_FAVORITES,
    CONF_INCLUDE_LIBRARY,
    CONF_REFRESH_INTERVAL,
    CONF_REPEAT_WINDOW,
    DEFAULT_INCLUDE_FAVORITES,
    DEFAULT_INCLUDE_LIBRARY,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_REPEAT_WINDOW,
    DOMAIN,
    MAX_RANDOM_CANDIDATES,
    MAX_REFRESH_INTERVAL,
    MAX_REPEAT_WINDOW,
    MIN_RANDOM_CANDIDATES,
    MIN_REFRESH_INTERVAL,
    MIN_REPEAT_WINDOW,
)
from .models import GalleryData, GalleryImage, GallerySource, SourceKind

_LOGGER = logging.getLogger(__name__)

ERROR_API = "api_error"
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_IMAGE_TOO_LARGE = "image_too_large"
ERROR_INVALID_RESPONSE = "invalid_response"
ERROR_NO_ASSETS = "no_assets"
ERROR_RATE_LIMITED = "rate_limited"
ERROR_UNSUPPORTED_IMAGE = "unsupported_image"


type ImmichGalleryConfigEntry = ConfigEntry[ImmichGalleryCoordinator]


def _refresh_minutes(options: Mapping[str, Any]) -> int:
    """Return a bounded refresh interval."""
    try:
        value = int(options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL))
    except TypeError, ValueError:
        value = DEFAULT_REFRESH_INTERVAL
    return min(max(value, MIN_REFRESH_INTERVAL), MAX_REFRESH_INTERVAL)


def _repeat_window(options: Mapping[str, Any]) -> int:
    """Return the bounded number of recently displayed images to remember."""
    try:
        value = int(options.get(CONF_REPEAT_WINDOW, DEFAULT_REPEAT_WINDOW))
    except TypeError, ValueError:
        value = DEFAULT_REPEAT_WINDOW
    return min(max(value, MIN_REPEAT_WINDOW), MAX_REPEAT_WINDOW)


def _candidate_count(repeat_window: int) -> int:
    """Return a bounded candidate count with room beyond recent history."""
    return min(
        max(MIN_RANDOM_CANDIDATES, repeat_window + MIN_RANDOM_CANDIDATES),
        MAX_RANDOM_CANDIDATES,
    )


class ImmichGalleryCoordinator(DataUpdateCoordinator[GalleryData]):
    """Fetch one preview for every configured source."""

    config_entry: ImmichGalleryConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ImmichGalleryConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.api = ImmichApiClient(
            async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL]),
            entry.data[CONF_URL],
            entry.data[CONF_API_KEY],
        )
        self.sources: tuple[GallerySource, ...] = ()
        self.server_version: str | None = None
        self._semaphore = asyncio.Semaphore(3)
        self._repeat_window = _repeat_window(entry.options)
        self._candidate_count = _candidate_count(self._repeat_window)
        self._recent_assets: dict[str, deque[str]] = {}

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=_refresh_minutes(entry.options)),
        )

    def _build_sources(
        self,
        album_names: Mapping[str, str],
    ) -> tuple[GallerySource, ...]:
        """Build stable source definitions from config-entry options."""
        options = self.config_entry.options
        sources: list[GallerySource] = []

        if options.get(CONF_INCLUDE_LIBRARY, DEFAULT_INCLUDE_LIBRARY):
            sources.append(
                GallerySource(
                    key="library",
                    kind=SourceKind.LIBRARY,
                    name="Random library",
                )
            )
        if options.get(CONF_INCLUDE_FAVORITES, DEFAULT_INCLUDE_FAVORITES):
            sources.append(
                GallerySource(
                    key="favorites",
                    kind=SourceKind.FAVORITES,
                    name="Random favorites",
                )
            )

        album_ids = options.get(CONF_ALBUM_IDS, [])
        if isinstance(album_ids, list):
            for album_id in album_ids:
                if not isinstance(album_id, str):
                    continue
                sources.append(
                    GallerySource(
                        key=f"album:{album_id}",
                        kind=SourceKind.ALBUM,
                        name=album_names.get(album_id, f"Album {album_id[:8]}"),
                        album_id=album_id,
                    )
                )

        return tuple(sources)

    async def _async_setup(self) -> None:
        """Validate credentials, permissions, and configured source metadata."""
        try:
            validation = await self.api.async_validate()
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed("Immich API key is invalid") from err
        except MissingPermission as err:
            raise ConfigEntryAuthFailed(
                f"Immich API key is missing {err.permission}"
            ) from err
        except RateLimited as err:
            raise UpdateFailed(
                "Immich rate limit reached",
                retry_after=err.retry_after,
            ) from err
        except (CannotConnect, ApiError, InvalidResponse) as err:
            raise UpdateFailed("Unable to validate the Immich server") from err

        self.server_version = validation.server_version
        album_names = {album.album_id: album.name for album in validation.albums}
        self.sources = self._build_sources(album_names)

    async def _async_fetch_source(
        self,
        source: GallerySource,
        previous: GalleryImage | None,
    ) -> GalleryImage:
        """Fetch a single source under the entry-wide concurrency limit."""
        async with self._semaphore:
            history = self._recent_assets.setdefault(
                source.key,
                deque(maxlen=self._repeat_window),
            )
            if previous is not None and previous.asset_id not in history:
                history.append(previous.asset_id)

            asset = await self.api.async_get_random_asset(
                source,
                recent_asset_ids=tuple(history),
                candidate_count=self._candidate_count,
            )
            content, content_type = await self.api.async_download_preview(
                asset.asset_id
            )
            history.append(asset.asset_id)
            image = GalleryImage(
                asset_id=asset.asset_id,
                content=content,
                content_type=content_type,
                fetched_at=datetime.now(UTC),
            )
            return image

    @staticmethod
    def _error_code(error: BaseException) -> str:
        """Map exceptions to privacy-safe diagnostic codes."""
        if isinstance(error, NoAssets):
            return ERROR_NO_ASSETS
        if isinstance(error, CannotConnect):
            return ERROR_CANNOT_CONNECT
        if isinstance(error, RateLimited):
            return ERROR_RATE_LIMITED
        if isinstance(error, ImageTooLarge):
            return ERROR_IMAGE_TOO_LARGE
        if isinstance(error, UnsupportedImage):
            return ERROR_UNSUPPORTED_IMAGE
        if isinstance(error, InvalidResponse):
            return ERROR_INVALID_RESPONSE
        return ERROR_API

    async def _async_update_data(self) -> GalleryData:
        """Fetch new images and preserve the last good image on partial failure."""
        previous_data = self.data if self.data is not None else GalleryData()
        previous_images = dict(previous_data.images)

        results = await asyncio.gather(
            *(
                self._async_fetch_source(source, previous_images.get(source.key))
                for source in self.sources
            ),
            return_exceptions=True,
        )

        images = previous_images
        errors: dict[str, str] = {}
        successful = 0
        retry_after: float | None = None
        transient_error: BaseException | None = None

        for source, result in zip(self.sources, results, strict=True):
            if isinstance(result, InvalidAuth):
                raise ConfigEntryAuthFailed("Immich API key is invalid") from result
            if isinstance(result, MissingPermission):
                raise ConfigEntryAuthFailed(
                    f"Immich API key is missing {result.permission}"
                ) from result
            if isinstance(result, BaseException):
                errors[source.key] = self._error_code(result)
                if isinstance(result, RateLimited):
                    retry_after = max(retry_after or 0, result.retry_after)
                    transient_error = result
                elif isinstance(
                    result,
                    CannotConnect | ApiError | InvalidResponse,
                ):
                    transient_error = result
                continue

            images[source.key] = result
            successful += 1

        if self.sources and successful == 0 and transient_error is not None:
            raise UpdateFailed(
                "Unable to update images from Immich",
                retry_after=retry_after,
            ) from transient_error

        return GalleryData(images=images, errors=errors)
