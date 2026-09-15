"""Data coordinator for Immich Gallery."""

from __future__ import annotations

import asyncio
import logging
import math
from collections import deque
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
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
    CONF_AUTOMATIC_SLIDESHOW,
    CONF_INCLUDE_FAVORITES,
    CONF_INCLUDE_LIBRARY,
    CONF_REFRESH_INTERVAL,
    CONF_REPEAT_WINDOW,
    DEFAULT_AUTOMATIC_SLIDESHOW,
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
        self._update_lock = asyncio.Lock()
        self._retry_until = 0.0
        self._playback_options: tuple[int, bool] | None = None
        self._playback_revision = 0

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=(
                timedelta(minutes=_refresh_minutes(entry.options))
                if entry.options.get(
                    CONF_AUTOMATIC_SLIDESHOW, DEFAULT_AUTOMATIC_SLIDESHOW
                )
                else None
            ),
        )

    @property
    def refresh_minutes(self) -> int:
        """Return the persisted interval shared by all sources."""
        return _refresh_minutes(self.config_entry.options)

    @property
    def automatic_slideshow(self) -> bool:
        """Return whether timed image changes are enabled."""
        return bool(
            self.config_entry.options.get(
                CONF_AUTOMATIC_SLIDESHOW, DEFAULT_AUTOMATIC_SLIDESHOW
            )
        )

    @callback
    def async_apply_playback_options(self) -> None:
        """Reschedule playback without fetching images or discarding history."""
        settings = (self.refresh_minutes, self.automatic_slideshow)
        if settings == self._playback_options:
            return
        self._playback_options = settings
        self._playback_revision += 1
        self.update_interval = timedelta(minutes=settings[0]) if settings[1] else None
        self._unschedule_refresh()
        if self._listeners and settings[1]:
            self._schedule_refresh()
        self.async_update_listeners()

    @callback
    def async_set_refresh_minutes(self, value: float) -> None:
        """Persist a validated whole-minute interval and apply it immediately."""
        if (
            not math.isfinite(value)
            or value != int(value)
            or not MIN_REFRESH_INTERVAL <= value <= MAX_REFRESH_INTERVAL
        ):
            raise HomeAssistantError(
                "Refresh interval must be a whole number from 1 to 60"
            )
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options={**self.config_entry.options, CONF_REFRESH_INTERVAL: int(value)},
        )
        self.async_apply_playback_options()

    @callback
    def async_set_automatic_slideshow(self, enabled: bool) -> None:
        """Persist the playback switch without changing the current image."""
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options={**self.config_entry.options, CONF_AUTOMATIC_SLIDESHOW: enabled},
        )
        self.async_apply_playback_options()

    async def async_next_image(self, source: GallerySource) -> None:
        """Refresh just one source, preserving the shared automatic schedule."""
        if self._shutdown_requested or source not in self.sources:
            raise HomeAssistantError("This image source is no longer available")
        if self._update_lock.locked():
            raise HomeAssistantError(
                "An image update is already in progress; try again shortly"
            )
        if self.hass.loop.time() < self._retry_until:
            raise HomeAssistantError("Immich requested a retry delay; try again later")
        async with self._update_lock:
            try:
                image = await self._async_fetch_source(
                    source, self.data.images.get(source.key)
                )
            except (InvalidAuth, MissingPermission) as err:
                self.config_entry.async_start_reauth(self.hass)
                raise HomeAssistantError("Immich credentials need attention") from err
            except (
                ApiError,
                CannotConnect,
                InvalidResponse,
                NoAssets,
                RateLimited,
                ImageTooLarge,
                UnsupportedImage,
            ) as err:
                if isinstance(err, RateLimited):
                    self._retry_until = self.hass.loop.time() + err.retry_after
                raise HomeAssistantError(
                    "Unable to load the next image from Immich"
                ) from err
            errors = dict(self.data.errors)
            if not self.last_update_success:
                errors.update(
                    {s.key: ERROR_API for s in self.sources if s.key != source.key}
                )
            errors.pop(source.key, None)
            self.data = GalleryData(
                images={**self.data.images, source.key: image}, errors=errors
            )
            self.last_update_success = True
            self.last_exception = None
            self.async_update_listeners()

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
        """Serialize timer and manual requests and honor the playback switch."""
        async with self._update_lock:
            revision = self._playback_revision
            if self.data is not None and not self.automatic_slideshow:
                return self.data
            if self.hass.loop.time() < self._retry_until:
                raise UpdateFailed(
                    "Immich requested a retry delay",
                    retry_after=self._retry_until - self.hass.loop.time(),
                )
            updated = await self._async_fetch_all_sources()
            # Turning playback off during a download must keep the visible frame.
            if self.data is not None and (
                not self.automatic_slideshow or revision != self._playback_revision
            ):
                return self.data
            return updated

    async def _async_fetch_all_sources(self) -> GalleryData:
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
                    self._retry_until = self.hass.loop.time() + retry_after
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
