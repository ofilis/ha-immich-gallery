"""The Immich Gallery integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_AUTOMATIC_SLIDESHOW, CONF_REFRESH_INTERVAL, DOMAIN
from .coordinator import ImmichGalleryConfigEntry, ImmichGalleryCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS: list[Platform] = [
    Platform.IMAGE,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Immich Gallery."""
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImmichGalleryConfigEntry,
) -> bool:
    """Set up Immich Gallery from a config entry."""
    coordinator = ImmichGalleryCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    initial_data = dict(entry.data)
    initial_options = {
        key: value
        for key, value in entry.options.items()
        if key not in (CONF_REFRESH_INTERVAL, CONF_AUTOMATIC_SLIDESHOW)
    }
    reload_pending = False

    async def async_update_options(hass: HomeAssistant, updated: ConfigEntry) -> None:
        """Apply playback controls live, and reload connection/source changes."""
        nonlocal reload_pending
        options = {
            key: value
            for key, value in updated.options.items()
            if key not in (CONF_REFRESH_INTERVAL, CONF_AUTOMATIC_SLIDESHOW)
        }
        if dict(updated.data) != initial_data or options != initial_options:
            if not reload_pending:
                reload_pending = True
                await hass.config_entries.async_reload(updated.entry_id)
            return
        coordinator.async_apply_playback_options()

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload an Immich Gallery config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
