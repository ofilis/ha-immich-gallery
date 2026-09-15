"""Behavioral tests for manual navigation and live slideshow controls."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components import immich_gallery as integration
from custom_components.immich_gallery import coordinator as coordinator_module
from custom_components.immich_gallery.api import CannotConnect, InvalidAuth, RateLimited
from custom_components.immich_gallery.button import NextImageButton
from custom_components.immich_gallery.config_flow import (
    _normalize_options,
    _source_schema,
)
from custom_components.immich_gallery.const import (
    CONF_AUTOMATIC_SLIDESHOW,
    CONF_REFRESH_INTERVAL,
)
from custom_components.immich_gallery.coordinator import ImmichGalleryCoordinator
from custom_components.immich_gallery.models import (
    AssetMetadata,
    GalleryData,
    GalleryImage,
    GallerySource,
    SourceKind,
)
from custom_components.immich_gallery.number import RefreshIntervalNumber
from custom_components.immich_gallery.switch import AutomaticSlideshowSwitch

LIBRARY = GallerySource("library", SourceKind.LIBRARY, "Random library")
FAVORITES = GallerySource("favorites", SourceKind.FAVORITES, "Random favorites")


def make_image(asset_id: str) -> GalleryImage:
    """Create a synthetic preview without accessing personal media."""
    return GalleryImage(asset_id, b"preview", "image/jpeg", datetime.now(UTC))


@pytest.fixture
async def gallery(tmp_path, monkeypatch):
    """Run the real HA coordinator scheduler with an isolated, mocked API."""
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = Mock()
    entry = SimpleNamespace(
        data={
            "url": "https://immich.example.com",
            "api_key": "test",
            "verify_ssl": True,
        },
        options={"refresh_interval": 5, "repeat_window": 20, "include_library": True},
        unique_id="test-user",
        entry_id="test-entry",
        title="Immich Gallery",
        pref_disable_polling=False,
        async_on_unload=Mock(),
        async_start_reauth=Mock(),
    )

    def update_entry(updated, *, options):
        updated.options = options

    hass.config_entries.async_update_entry.side_effect = update_entry
    monkeypatch.setattr(coordinator_module, "async_get_clientsession", Mock())
    coordinator = ImmichGalleryCoordinator(hass, entry)
    coordinator.sources = (LIBRARY, FAVORITES)
    coordinator.data = GalleryData(
        images={
            "library": make_image("old-library"),
            "favorites": make_image("old-favorites"),
        }
    )
    coordinator.api = SimpleNamespace(
        async_get_random_asset=AsyncMock(return_value=AssetMetadata("next")),
        async_download_preview=AsyncMock(return_value=(b"new-preview", "image/jpeg")),
    )
    yield coordinator
    await coordinator.async_shutdown()


async def test_button_changes_only_its_source_and_preserves_timer(gallery):
    """A button updates exactly one preview and preserves the shared schedule."""
    changed = Mock()
    remove = gallery.async_add_listener(changed)
    timer = gallery._unsub_refresh
    other_image = gallery.data.images["favorites"]
    await NextImageButton(gallery, LIBRARY).async_press()
    assert gallery.data.images["library"].asset_id == "next"
    assert gallery.data.images["favorites"] is other_image
    assert gallery._unsub_refresh is timer
    gallery.api.async_get_random_asset.assert_awaited_once_with(
        LIBRARY, recent_asset_ids=("old-library",), candidate_count=30
    )
    changed.assert_called_once()
    remove()


async def test_pause_stops_timer_but_manual_navigation_works(gallery):
    """Pausing holds images, including when a queued automatic refresh runs."""
    remove = gallery.async_add_listener(Mock())
    switch = AutomaticSlideshowSwitch(gallery)
    before = gallery.data
    await switch.async_turn_off()
    assert switch.is_on is False
    assert gallery.update_interval is None
    assert gallery._unsub_refresh is None
    assert await gallery._async_update_data() is before
    gallery.api.async_get_random_asset.assert_not_awaited()
    await NextImageButton(gallery, LIBRARY).async_press()
    assert gallery.data.images["library"].asset_id == "next"
    assert gallery._unsub_refresh is None
    await switch.async_turn_on()
    assert gallery._unsub_refresh is not None
    assert gallery.update_interval == timedelta(minutes=5)
    remove()


async def test_slider_persists_reschedules_and_matches_configure(gallery):
    """Changing the interval does not fetch media or reset selection history."""
    remove = gallery.async_add_listener(Mock())
    timer = gallery._unsub_refresh
    before = gallery.data
    number = RefreshIntervalNumber(gallery)
    await number.async_set_native_value(12)
    assert number.native_value == 12
    assert gallery.update_interval == timedelta(minutes=12)
    assert gallery._unsub_refresh is not timer
    assert gallery.data is before
    assert (
        _source_schema((), gallery.config_entry.options)({})[CONF_REFRESH_INTERVAL]
        == 12
    )
    gallery.api.async_get_random_asset.assert_not_awaited()
    # Mimic saving Configure: the same options feed the live entity.
    gallery.config_entry.options = {
        **gallery.config_entry.options,
        CONF_REFRESH_INTERVAL: 7,
    }
    gallery.async_apply_playback_options()
    assert number.native_value == 7
    assert gallery.update_interval == timedelta(minutes=7)
    remove()


@pytest.mark.parametrize("value", [0, 61, 1.5, float("nan"), float("inf")])
async def test_slider_rejects_invalid_automation_values(gallery, value):
    """Service calls cannot bypass whole-minute bounds."""
    with pytest.raises(HomeAssistantError):
        await RefreshIntervalNumber(gallery).async_set_native_value(value)
    assert gallery.refresh_minutes == 5


async def test_paused_settings_survive_coordinator_recreation(gallery):
    """Saved options restore the switch and interval after a restart."""
    gallery.async_set_automatic_slideshow(False)
    gallery.async_set_refresh_minutes(60)
    restored = ImmichGalleryCoordinator(gallery.hass, gallery.config_entry)
    assert restored.automatic_slideshow is False
    assert restored.refresh_minutes == 60
    assert restored.update_interval is None
    # A paused entry still fetches an initial frame after restarting.
    restored.sources = (LIBRARY,)
    restored.api = gallery.api
    data = await restored._async_update_data()
    assert data.images["library"].asset_id == "next"
    await restored.async_shutdown()


async def test_manual_failure_keeps_last_good_image(gallery):
    """A transient error fails the action without blanking the visible image."""
    before = gallery.data
    gallery.api.async_download_preview.side_effect = CannotConnect()
    with pytest.raises(HomeAssistantError, match="Unable to load"):
        await gallery.async_next_image(LIBRARY)
    assert gallery.data is before
    assert gallery.last_update_success is True


async def test_manual_retry_recovers_only_target_after_global_failure(gallery):
    """Recovering one source must not mark other failed sources as healthy."""
    gallery.last_update_success = False
    assert RefreshIntervalNumber(gallery).available
    await gallery.async_next_image(LIBRARY)
    assert gallery.last_update_success
    assert "library" not in gallery.data.errors
    assert "favorites" in gallery.data.errors


async def test_manual_rate_limit_blocks_followup_requests(gallery):
    """Buttons honor the server retry delay instead of flooding the API."""
    gallery.api.async_get_random_asset.side_effect = RateLimited(60)
    with pytest.raises(HomeAssistantError, match="Unable to load"):
        await gallery.async_next_image(LIBRARY)
    with pytest.raises(HomeAssistantError, match="retry delay"):
        await gallery.async_next_image(LIBRARY)
    assert gallery.api.async_get_random_asset.await_count == 1


async def test_manual_auth_failure_starts_reauthentication(gallery):
    """An expired API key opens HA's normal reauthentication path."""
    gallery.api.async_get_random_asset.side_effect = InvalidAuth()
    with pytest.raises(HomeAssistantError, match="credentials"):
        await gallery.async_next_image(LIBRARY)
    gallery.config_entry.async_start_reauth.assert_called_once_with(gallery.hass)


async def test_overlapping_button_presses_do_not_queue_downloads(gallery):
    """A second press fails clearly while an update is in flight."""
    entered, finish = asyncio.Event(), asyncio.Event()

    async def download(_asset_id):
        entered.set()
        await finish.wait()
        return b"next", "image/jpeg"

    gallery.api.async_download_preview.side_effect = download
    first = asyncio.create_task(gallery.async_next_image(LIBRARY))
    await entered.wait()
    try:
        with pytest.raises(HomeAssistantError, match="already in progress"):
            await gallery.async_next_image(LIBRARY)
    finally:
        finish.set()
        await first
    assert gallery.api.async_download_preview.await_count == 1


async def test_pausing_during_automatic_download_keeps_current_frame(gallery):
    """An in-flight timer update must not replace an image after pausing."""
    before = gallery.data

    async def download(_asset_id):
        gallery.async_set_automatic_slideshow(False)
        return b"next", "image/jpeg"

    gallery.api.async_download_preview.side_effect = download
    assert await gallery._async_update_data() is before


async def test_interval_change_during_download_holds_current_frame(gallery):
    """Changing the interval starts a fresh wait instead of publishing old work."""
    before = gallery.data

    async def download(_asset_id):
        gallery.async_set_refresh_minutes(10)
        return b"next", "image/jpeg"

    gallery.api.async_download_preview.side_effect = download
    assert await gallery._async_update_data() is before


async def test_unload_cancels_timer_and_rejects_manual_requests(gallery):
    """Reloads leave neither a running timer nor usable obsolete controls."""
    gallery.async_add_listener(Mock())
    assert gallery._unsub_refresh is not None
    await gallery.async_shutdown()
    assert gallery._unsub_refresh is None
    with pytest.raises(HomeAssistantError, match="no longer available"):
        await gallery.async_next_image(LIBRARY)


@pytest.mark.parametrize("change", ["interval", "playback", "sources", "host"])
async def test_entry_update_listener_reloads_only_structural_changes(
    gallery, monkeypatch, change
):
    """Real entry setup registers all platforms and routes option changes."""
    entry = gallery.config_entry
    entry.add_update_listener = Mock(return_value=Mock())
    gallery.async_config_entry_first_refresh = AsyncMock()
    manager = gallery.hass.config_entries
    manager.async_forward_entry_setups = AsyncMock()
    manager.async_reload = AsyncMock()
    monkeypatch.setattr(
        integration, "ImmichGalleryCoordinator", Mock(return_value=gallery)
    )
    assert await integration.async_setup_entry(gallery.hass, entry)
    assert {str(p) for p in manager.async_forward_entry_setups.call_args.args[1]} == {
        "image",
        "button",
        "number",
        "switch",
    }
    listener = entry.add_update_listener.call_args.args[0]
    if change == "interval":
        entry.options = {**entry.options, CONF_REFRESH_INTERVAL: 23}
    elif change == "playback":
        entry.options = {**entry.options, CONF_AUTOMATIC_SLIDESHOW: False}
    elif change == "sources":
        entry.options = {**entry.options, "include_favorites": True}
    else:
        entry.data = {**entry.data, "url": "https://new.example.com"}
    await listener(gallery.hass, entry)
    if change in ("sources", "host"):
        manager.async_reload.assert_awaited_once_with(entry.entry_id)
        # Coalesced connection and options notifications must not reload twice.
        await listener(gallery.hass, entry)
        assert manager.async_reload.await_count == 1
    else:
        manager.async_reload.assert_not_awaited()
        if change == "interval":
            assert gallery.update_interval == timedelta(minutes=23)
        else:
            assert gallery.update_interval is None


async def test_button_setup_removes_only_obsolete_gallery_buttons(gallery, monkeypatch):
    """Deselecting an album removes its button without removing unrelated entities."""
    from custom_components.immich_gallery import button

    entry = gallery.config_entry
    entry.runtime_data = gallery
    registry = Mock()
    monkeypatch.setattr(button.er, "async_get", Mock(return_value=registry))
    monkeypatch.setattr(
        button.er,
        "async_entries_for_config_entry",
        Mock(
            return_value=[
                SimpleNamespace(
                    domain="button",
                    platform="immich_gallery",
                    unique_id="test-user:library:next_image",
                    entity_id="button.keep",
                ),
                SimpleNamespace(
                    domain="button",
                    platform="immich_gallery",
                    unique_id="test-user:album:removed:next_image",
                    entity_id="button.remove",
                ),
                SimpleNamespace(
                    domain="image",
                    platform="immich_gallery",
                    unique_id="test-user:library",
                    entity_id="image.keep",
                ),
            ]
        ),
    )
    entities = []
    await button.async_setup_entry(gallery.hass, entry, entities.extend)
    assert len(entities) == 2
    registry.async_remove.assert_called_once_with("button.remove")


def test_configure_preserves_disabled_slideshow():
    """Saving Configure must not silently resume a paused slideshow."""
    result = _source_schema((), {CONF_AUTOMATIC_SLIDESHOW: False})({})
    assert _normalize_options(result)[CONF_AUTOMATIC_SLIDESHOW] is False
