"""Tests for privacy-preserving diagnostics."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, cast

import pytest
from homeassistant.const import CONF_VERIFY_SSL

from custom_components.immich_gallery.const import (
    CONF_ALBUM_IDS,
    CONF_INCLUDE_FAVORITES,
    CONF_INCLUDE_LIBRARY,
    CONF_REFRESH_INTERVAL,
    CONF_REPEAT_WINDOW,
)
from custom_components.immich_gallery.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.immich_gallery.models import (
    GalleryData,
    GallerySource,
    SourceKind,
)


@pytest.mark.asyncio
async def test_diagnostics_omit_connection_and_media_identifiers() -> None:
    """Diagnostics expose counts and flags, never private identifiers."""
    coordinator = SimpleNamespace(
        data=GalleryData(errors={"album:private-album-id": "no_assets"}),
        server_version="2.3.4",
        sources=(
            GallerySource(
                key="album:private-album-id",
                kind=SourceKind.ALBUM,
                name="Private family album",
                album_id="private-album-id",
            ),
        ),
        last_update_success=True,
    )
    entry = SimpleNamespace(
        data={
            "url": "https://private-immich.example.com",
            "api_key": "super-secret-key",
            CONF_VERIFY_SSL: True,
        },
        unique_id="private-user-id",
        options={
            CONF_INCLUDE_LIBRARY: False,
            CONF_INCLUDE_FAVORITES: False,
            CONF_ALBUM_IDS: ["private-album-id"],
            CONF_REPEAT_WINDOW: 20,
            CONF_REFRESH_INTERVAL: 5,
        },
        runtime_data=coordinator,
    )

    diagnostics = await async_get_config_entry_diagnostics(
        cast(Any, None),
        cast(Any, entry),
    )
    serialized = json.dumps(diagnostics)

    assert diagnostics["configuration"]["selected_album_count"] == 1
    assert diagnostics["configuration"]["repeat_window"] == 20
    assert diagnostics["configuration"]["verify_ssl"] is True
    assert diagnostics["available_source_count"] == 0
    assert diagnostics["error_code_counts"] == {"no_assets": 1}
    for sensitive_value in (
        "private-immich.example.com",
        "super-secret-key",
        "private-user-id",
        "private-album-id",
        "Private family album",
    ):
        assert sensitive_value not in serialized
