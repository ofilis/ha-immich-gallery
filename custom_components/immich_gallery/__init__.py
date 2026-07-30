"""The Immich Gallery integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import ImmichGalleryConfigEntry, ImmichGalleryCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS: list[Platform] = [Platform.IMAGE]


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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload an Immich Gallery config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
