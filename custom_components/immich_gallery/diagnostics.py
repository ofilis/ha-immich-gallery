"""Privacy-preserving diagnostics for Immich Gallery."""

from __future__ import annotations

from collections import Counter
from typing import Any

from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ALBUM_IDS,
    CONF_INCLUDE_FAVORITES,
    CONF_INCLUDE_LIBRARY,
    CONF_REFRESH_INTERVAL,
    CONF_REPEAT_WINDOW,
)
from .coordinator import ImmichGalleryConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ImmichGalleryConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics without personal media or server identifiers."""
    coordinator = entry.runtime_data
    errors = Counter(coordinator.data.errors.values())
    options = entry.options
    album_ids = options.get(CONF_ALBUM_IDS, [])
    available_sources = sum(
        source.key in coordinator.data.images
        and source.key not in coordinator.data.errors
        for source in coordinator.sources
    )

    return {
        "configuration": {
            "include_library": bool(options.get(CONF_INCLUDE_LIBRARY)),
            "include_favorites": bool(options.get(CONF_INCLUDE_FAVORITES)),
            "verify_ssl": bool(entry.data.get(CONF_VERIFY_SSL)),
            "selected_album_count": len(album_ids)
            if isinstance(album_ids, list)
            else 0,
            "repeat_window": options.get(CONF_REPEAT_WINDOW),
            "refresh_interval": options.get(CONF_REFRESH_INTERVAL),
        },
        "server_version": coordinator.server_version,
        "configured_source_count": len(coordinator.sources),
        "available_source_count": available_sources,
        "error_code_counts": dict(errors),
        "last_update_success": coordinator.last_update_success,
    }
