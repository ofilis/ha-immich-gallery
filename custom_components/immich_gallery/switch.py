"""Automatic slideshow playback control."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ImmichGalleryConfigEntry, ImmichGalleryCoordinator
from .entity import GalleryControl


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImmichGalleryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the entry-wide playback switch."""
    async_add_entities([AutomaticSlideshowSwitch(entry.runtime_data)])


class AutomaticSlideshowSwitch(GalleryControl, SwitchEntity):
    """Pause scheduled image changes while leaving manual navigation available."""

    _attr_translation_key = "automatic_slideshow"

    def __init__(self, coordinator: ImmichGalleryCoordinator) -> None:
        """Initialize playback control."""
        super().__init__(coordinator, "automatic_slideshow")

    @property
    def is_on(self) -> bool:
        """Return the persisted playback setting."""
        return self.coordinator.automatic_slideshow

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Resume after the configured interval."""
        self.coordinator.async_set_automatic_slideshow(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Hold the current images until manually advanced or resumed."""
        self.coordinator.async_set_automatic_slideshow(False)
