"""Tests for user-editable Immich Gallery settings."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL

from custom_components.immich_gallery.config_flow import (
    _settings_schema,
    _source_schema,
)
from custom_components.immich_gallery.const import (
    CONF_ALBUM_IDS,
    CONF_INCLUDE_FAVORITES,
    CONF_INCLUDE_LIBRARY,
    CONF_REFRESH_INTERVAL,
    CONF_REPEAT_WINDOW,
)
from custom_components.immich_gallery.models import Album

ALBUM_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def test_new_sources_require_explicit_selection() -> None:
    """No broad image source is enabled without an explicit user choice."""
    schema = _source_schema((Album(album_id=ALBUM_ID, name="Family"),))

    result = schema({})

    assert result[CONF_INCLUDE_LIBRARY] is False
    assert result[CONF_INCLUDE_FAVORITES] is False
    assert result[CONF_ALBUM_IDS] == []
    assert result[CONF_REPEAT_WINDOW] == 20
    assert result[CONF_REFRESH_INTERVAL] == 5


def test_configure_schema_allows_connection_and_rotation_changes() -> None:
    """The integration Configure form exposes all important mutable settings."""
    connection = {
        CONF_URL: "https://immich.example.com",
        CONF_API_KEY: "stored-secret",
        CONF_VERIFY_SSL: True,
    }
    schema = _settings_schema(
        connection,
        (Album(album_id=ALBUM_ID, name="Family"),),
        {
            **connection,
            CONF_INCLUDE_LIBRARY: True,
            CONF_INCLUDE_FAVORITES: True,
            CONF_ALBUM_IDS: [ALBUM_ID],
            CONF_REPEAT_WINDOW: 20,
            CONF_REFRESH_INTERVAL: 5,
        },
    )

    result = schema(
        {
            CONF_URL: "http://100.64.12.34:2283",
            CONF_API_KEY: "",
            CONF_VERIFY_SSL: False,
            CONF_INCLUDE_LIBRARY: True,
            CONF_INCLUDE_FAVORITES: False,
            CONF_ALBUM_IDS: [ALBUM_ID],
            CONF_REPEAT_WINDOW: 40,
            CONF_REFRESH_INTERVAL: 10,
        }
    )

    assert result[CONF_URL] == "http://100.64.12.34:2283"
    assert result[CONF_API_KEY] == ""
    assert result[CONF_VERIFY_SSL] is False
    assert result[CONF_ALBUM_IDS] == [ALBUM_ID]
    assert result[CONF_REPEAT_WINDOW] == 40
    assert result[CONF_REFRESH_INTERVAL] == 10
