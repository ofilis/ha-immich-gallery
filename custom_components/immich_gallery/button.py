"""Per-source next-image buttons."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ImmichGalleryConfigEntry, ImmichGalleryCoordinator
from .entity import GalleryControl
from .models import GallerySource


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImmichGalleryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a button for each selected source and remove obsolete buttons."""
    coordinator = entry.runtime_data
    active_ids = {
        f"{entry.unique_id}:{source.key}:next_image" for source in coordinator.sources
    }
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            entity.domain == Platform.BUTTON
            and entity.platform == DOMAIN
            and entity.unique_id not in active_ids
        ):
            registry.async_remove(entity.entity_id)
    async_add_entities(
        NextImageButton(coordinator, source) for source in coordinator.sources
    )


class NextImageButton(GalleryControl, ButtonEntity):
    """Advance one source without advancing any of the others."""

    _attr_translation_key = "next_image"

    def __init__(
        self, coordinator: ImmichGalleryCoordinator, source: GallerySource
    ) -> None:
        """Initialize the per-source button."""
        super().__init__(coordinator, f"{source.key}:next_image")
        self._source = source
        self._attr_translation_placeholders = {"source": source.name}

    async def async_press(self) -> None:
        """Request the next random image, including while playback is paused."""
        await self.coordinator.async_next_image(self._source)
