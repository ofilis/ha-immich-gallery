"""Tests for Immich Gallery image entities."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er

from custom_components.immich_gallery.const import DOMAIN
from custom_components.immich_gallery.image import _remove_stale_entities
from custom_components.immich_gallery.models import GallerySource, SourceKind


def test_remove_stale_entities_keeps_only_selected_gallery_images(
    monkeypatch,
) -> None:
    """Registry entries for deselected sources are removed during reload."""
    hass = Mock()
    config_entry = SimpleNamespace(entry_id="entry-id", unique_id="user-id")
    album_source = GallerySource(
        key="album:album-id",
        kind=SourceKind.ALBUM,
        name="Family",
        album_id="album-id",
    )
    registry = Mock()
    registry_entries = (
        SimpleNamespace(
            domain=Platform.IMAGE,
            platform=DOMAIN,
            unique_id="user-id:album:album-id",
            entity_id="image.family",
        ),
        SimpleNamespace(
            domain=Platform.IMAGE,
            platform=DOMAIN,
            unique_id="user-id:library",
            entity_id="image.random_library",
        ),
        SimpleNamespace(
            domain=Platform.SENSOR,
            platform=DOMAIN,
            unique_id="user-id:diagnostic",
            entity_id="sensor.diagnostic",
        ),
        SimpleNamespace(
            domain=Platform.IMAGE,
            platform="another_integration",
            unique_id="another:image",
            entity_id="image.another",
        ),
    )
    monkeypatch.setattr(er, "async_get", Mock(return_value=registry))
    entries_for_config_entry = Mock(return_value=registry_entries)
    monkeypatch.setattr(
        er,
        "async_entries_for_config_entry",
        entries_for_config_entry,
    )

    _remove_stale_entities(hass, config_entry, (album_source,))

    entries_for_config_entry.assert_called_once_with(registry, "entry-id")
    registry.async_remove.assert_called_once_with("image.random_library")
