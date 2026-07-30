"""Image entities for Immich Gallery."""

from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ImmichGalleryConfigEntry, ImmichGalleryCoordinator
from .models import GallerySource, SourceKind


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImmichGalleryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one image entity per configured gallery source."""
    coordinator = entry.runtime_data
    _remove_stale_entities(hass, entry, coordinator.sources)
    async_add_entities(
        ImmichGalleryImage(hass, entry, coordinator, source)
        for source in coordinator.sources
    )


@callback
def _remove_stale_entities(
    hass: HomeAssistant,
    entry: ImmichGalleryConfigEntry,
    sources: tuple[GallerySource, ...],
) -> None:
    """Remove image entities for sources no longer selected by the user."""
    active_unique_ids = {f"{entry.unique_id}:{source.key}" for source in sources}
    registry = er.async_get(hass)

    for registry_entry in er.async_entries_for_config_entry(
        registry,
        entry.entry_id,
    ):
        if (
            registry_entry.domain == Platform.IMAGE
            and registry_entry.platform == DOMAIN
            and registry_entry.unique_id not in active_unique_ids
        ):
            registry.async_remove(registry_entry.entity_id)


class ImmichGalleryImage(ImageEntity):
    """A cached Immich preview served by Home Assistant."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ImmichGalleryConfigEntry,
        coordinator: ImmichGalleryCoordinator,
        source: GallerySource,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(hass, verify_ssl=True)
        self._entry = entry
        self._coordinator = coordinator
        self._source = source
        self._attr_unique_id = f"{entry.unique_id}:{source.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            manufacturer="ofilis",
            model="Immich Gallery community integration",
            name=entry.title,
            configuration_url=coordinator.api.base_url,
        )

        if source.kind is SourceKind.ALBUM:
            self._attr_name = source.name
        elif source.kind is SourceKind.FAVORITES:
            self._attr_translation_key = "random_favorites"
        else:
            self._attr_translation_key = "random_library"

        self._apply_coordinator_data()

    @property
    def available(self) -> bool:
        """Return whether this source has a current successful preview."""
        return bool(
            self._coordinator.last_update_success
            and self._source.key in self._coordinator.data.images
            and self._source.key not in self._coordinator.data.errors
        )

    async def async_image(self) -> bytes | None:
        """Return the already-cached preview without network I/O."""
        image = self._coordinator.data.images.get(self._source.key)
        return image.content if image else None

    @callback
    def _apply_coordinator_data(self) -> None:
        """Copy the current coordinator data into entity properties."""
        image = self._coordinator.data.images.get(self._source.key)
        if image is None:
            self._attr_extra_state_attributes = {
                "source_type": self._source.kind.value,
            }
            return

        self._attr_content_type = image.content_type
        self._attr_image_last_updated = image.fetched_at
        self._attr_extra_state_attributes = {
            "source_type": self._source.kind.value,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle a coordinator refresh."""
        self._apply_coordinator_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe only while the entity is enabled and added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )
