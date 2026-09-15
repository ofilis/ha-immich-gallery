"""Shared device identity for gallery controls."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ImmichGalleryCoordinator


class GalleryControl(CoordinatorEntity[ImmichGalleryCoordinator]):
    """A local control that stays usable when Immich is temporarily offline."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ImmichGalleryCoordinator, key: str) -> None:
        """Attach the control to the existing gallery device."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id}:{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        )

    @property
    def available(self) -> bool:
        """Local settings and manual retry do not require a successful last poll."""
        return True
