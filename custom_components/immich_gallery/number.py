"""Live slideshow interval control."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import MAX_REFRESH_INTERVAL, MIN_REFRESH_INTERVAL
from .coordinator import ImmichGalleryConfigEntry, ImmichGalleryCoordinator
from .entity import GalleryControl


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImmichGalleryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the entry-wide interval slider."""
    async_add_entities([RefreshIntervalNumber(entry.runtime_data)])


class RefreshIntervalNumber(GalleryControl, NumberEntity):
    """Persist the slideshow interval in the same options as Configure."""

    _attr_translation_key = "refresh_interval"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = MIN_REFRESH_INTERVAL
    _attr_native_max_value = MAX_REFRESH_INTERVAL
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator: ImmichGalleryCoordinator) -> None:
        """Initialize the slider."""
        super().__init__(coordinator, "refresh_interval")

    @property
    def native_value(self) -> float:
        """Read the current persisted interval."""
        return self.coordinator.refresh_minutes

    async def async_set_native_value(self, value: float) -> None:
        """Set a new interval without reloading the integration."""
        self.coordinator.async_set_refresh_minutes(value)
